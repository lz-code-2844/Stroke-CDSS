# agent/main_flow.py

import pandas as pd
import re
import os
import time
import json
import logging
import sys
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from utils.data_loader import load_experiment_data
from utils.rag_engine import SimpleRAG
from agents.react_agent import ReActClinicalAgent

# ================= RAG ENHANCEMENT (New) =================
# 自动选择最强的 RAG 版本
RAG_COORDINATOR = None
RAG_AVAILABLE = False
RAG_VERSION = "None"

# 优先级1: 混合检索 RAG (最强)
try:
    from rag.hybrid_coordinator import HybridRAGCoordinator
    RAG_COORDINATOR = None  # 延迟初始化
    RAG_AVAILABLE = True
    RAG_VERSION = "Hybrid (Semantic + BM25 + Reranking)"
    # 静默加载，不在终端显示
except ImportError:
    pass

# 优先级2: Simple RAG (TF-IDF)
if not RAG_AVAILABLE:
    try:
        from rag.simple_coordinator import RAGCoordinator
        RAG_COORDINATOR = None
        RAG_AVAILABLE = True
        RAG_VERSION = "Simple (TF-IDF)"
        # 静默加载
    except ImportError as e:
        RAG_AVAILABLE = False
        # 静默处理，不在终端显示

# ================= CONFIGURATION =================
EXCEL_PATH = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6/data/experiment_data1.xlsx"
OUTPUT_PATH = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6/results_v6_data1/final_results.xlsx"
JSON_OUTPUT_PATH = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6/results_v6_data1/final_results.xlsx"
DETAILED_LOGS_DIR = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6/results_v6_data1/detailed_logs"
ROOT_DIR = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6"
# 并行配置
MAX_WORKERS = 10  # 并行处理的最大进程数

# ================= LOGGING SETUP =================

def get_patient_logger(patient_id, logs_dir):
    """
    为每个患者创建独立的日志记录器，输出到 patient_id.log 文件。
    """
    safe_pid = str(patient_id).replace('/', '_').replace('\\', '_').replace(' ', '_')
    log_file = os.path.join(logs_dir, f"{safe_pid}.log")
    
    logger = logging.getLogger(f"patient_{safe_pid}")
    logger.setLevel(logging.INFO)
    
    # 清除已有的handlers，避免重复
    logger.handlers = []
    
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.propagate = False
    
    return logger

# ================= HELPER FUNCTIONS =================

def get_agents():
    """创建Agent实例（每个进程需要独立创建）"""
    return {
        # --- Step 0 & 1: 基础/分诊/出血 (Common) ---
        'triage': ReActClinicalAgent(f"{ROOT_DIR}/prompts/01_triage_agent.md"),
        'time_calc': ReActClinicalAgent(f"{ROOT_DIR}/prompts/03_time_calc_agent.md"),
        'hemorrhage': ReActClinicalAgent(f"{ROOT_DIR}/prompts/02_hemorrhage_agent.md"),
        
        # --- Branch A: 出血路径专用 ---
        'aneurysm': ReActClinicalAgent(f"{ROOT_DIR}/prompts/04_aneurysm_agent.md"),
        
        # --- Branch B: 缺血路径专用 (Ischemic) ---
        'lvo': ReActClinicalAgent(f"{ROOT_DIR}/prompts/05_lvo_agent.md"),
        'ncct_imaging': ReActClinicalAgent(f"{ROOT_DIR}/prompts/07a_ncct_imaging_agent.md"),
        'cta_imaging': ReActClinicalAgent(f"{ROOT_DIR}/prompts/07b_cta_imaging_agent.md"),
        'ctp_imaging': ReActClinicalAgent(f"{ROOT_DIR}/prompts/07c_ctp_imaging_agent.md"),
        'imaging_validation': ReActClinicalAgent(f"{ROOT_DIR}/prompts/07_imaging_agent.md"),  # 影像综合整合
        'nihss_scorer': ReActClinicalAgent(f"{ROOT_DIR}/prompts/11_nihss_scorer.md"),
        'fact_extractor': ReActClinicalAgent(f"{ROOT_DIR}/prompts/12_fact_extractor.md"),
        'consistency_check': ReActClinicalAgent(f"{ROOT_DIR}/prompts/13_consistency_check.md"),
        'indication': ReActClinicalAgent(f"{ROOT_DIR}/prompts/08_indication_agent.md"), # [新增] 指征筛查Agent
        
        # --- Step 4: 总控 (Common Exit) ---
        'director': ReActClinicalAgent(f"{ROOT_DIR}/prompts/14_director_agent.md"),
    }

def parse_json_from_output(text):
    """从Agent输出中提取JSON格式的决策结果。"""
    if not isinstance(text, str):
        return None
    
    # 尝试提取 markdown json 代码块
    json_pattern = re.compile(r'```json\s*([\s\S]*?)\s*```', re.IGNORECASE)
    match = json_pattern.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试截取 {}
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
    
    return None

def parse_agent_decision(text, target_q="Q2"):
    """[升级版解析器] 尝试从JSON或文本中提取 Yes/No 答案"""
    if not isinstance(text, str):
        return False
    
    # 1. 优先尝试 JSON
    json_result = parse_json_from_output(text)
    if json_result and target_q in json_result:
        answer = str(json_result[target_q]).lower()
        if "是" in answer or "yes" in answer or answer == "true":
            return True
        if "否" in answer or "no" in answer or answer == "false":
            return False

    # 2. 正则匹配 "Q2.....(是/否)"
    pattern = re.compile(rf"{target_q}.*?([是否YesNo])", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)

    if match:
        answer = match.group(1).lower()
        if "是" in answer or "y" in answer: return True
        if "否" in answer or "n" in answer: return False

    # 3. 文本截取模糊匹配
    try:
        if target_q in text:
            part = text.split(target_q)[1]
            if "是" in part or "yes" in part.lower() or "推荐" in part or "符合" in part:
                return True
    except:
        pass

    # 4. 兜底
    if "是" in text or "yes" in text.lower():
        return True

    return False

def parse_numeric_value(text, target_q):
    """从Agent输出中提取数值型答案"""
    if not isinstance(text, str):
        return None
    
    json_result = parse_json_from_output(text)
    if json_result and target_q in json_result:
        try:
            return float(json_result[target_q])
        except (ValueError, TypeError):
            pass
    
    pattern = re.compile(rf"{target_q}.*?(\d+\.?\d*)", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None

def parse_standard_choices(text):
    """专门为Director解析A/B/C/D/E选项（E为动脉夹层特殊处理）"""
    json_res = parse_json_from_output(text)
    if json_res and "closed_outcome" in json_res:
        return json_res["closed_outcome"].get("best_option_code", "N/A")
    return "N/A"

def parse_string_value(text, target_q):
    """从Agent输出中提取字符串型答案"""
    if not isinstance(text, str):
        return None
    
    json_result = parse_json_from_output(text)
    if json_result and target_q in json_result:
        return str(json_result[target_q])
    return None

def split_video_paths(path_str):
    if not isinstance(path_str, str) or not path_str:
        return []
    path_str = path_str.replace("'", "").replace('"', "")
    return [p.strip() for p in path_str.split(';') if p.strip()]

def parse_ctp_tool_string(tool_str):
    """解析CTP工具输出字符串"""
    data = {'tool_core_vol': 'N/A', 'tool_penumbra': 'N/A', 'tool_mismatch': 'N/A'}
    if not isinstance(tool_str, str):
        return data
    core_match = re.search(r'CBF<30%.*?volume\s*=\s*(\d+\.?\d*)', tool_str)
    if core_match: data['tool_core_vol'] = core_match.group(1)
    penumbra_match = re.search(r'Tmax>6s.*?volume\s*=\s*(\d+\.?\d*)', tool_str)
    if penumbra_match: data['tool_penumbra'] = penumbra_match.group(1)
    ratio_match = re.search(r'Mismatch.*?ratio\s*=\s*(\d+\.?\d*)', tool_str)
    if ratio_match: data['tool_mismatch'] = ratio_match.group(1)
    return data

def build_agent_context(row_data, agent_name, previous_outputs=None):
    """
    根据不同Agent的需求，构建符合其prompt模板的上下文。
    """
    ctx = {}
    previous_outputs = previous_outputs or {}
    
    # 1. 预先提取数据
    full_record = row_data.get('admission_record', 'N/A')
    chief_complaint_text = row_data.get('time_calc_source', 'N/A')
    
    # === Step 0 & 1 ===
    if agent_name == 'triage':
        ctx['admission_record'] = full_record
        
    elif agent_name == 'hemorrhage':
        ctx['tool_aspects'] = row_data.get('tool_aspects', 'N/A')
        ctx['chief_complaint'] = chief_complaint_text
        
    elif agent_name == 'time_calc':
        ctx['time_source_text'] = chief_complaint_text
    
    # === Branch A: 出血路径 ===
    elif agent_name == 'aneurysm':
        ctx['hemorrhage_output'] = previous_outputs.get('hemorrhage', 'N/A')
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['chief_complaint'] = chief_complaint_text

    # === Branch B: 缺血路径 ===
    elif agent_name == 'lvo':
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['cta_tool_findings'] = row_data.get('cta_tool_findings', '无记录')
        ctx['cta_imaging_output'] = previous_outputs.get('cta_imaging', 'CTA影像分析尚未执行或失败')
        ctx['admission_record'] = full_record
        
    elif agent_name == 'ncct_imaging':
        ctx['tool_aspects'] = row_data.get('tool_aspects', 'N/A')
        
    elif agent_name == 'cta_imaging':
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['cta_tool_findings'] = row_data.get('cta_tool_findings', '无记录')
        ctx['ctp_feedback'] = previous_outputs.get('ctp_imaging', 'CTP尚未执行或无结果')
        
    elif agent_name == 'ctp_imaging':
        ctx['ctp_tool_raw'] = row_data.get('ctp_tool_raw', 'N/A')
        ctx['ctp_tool_findings'] = row_data.get('ctp_tool_findings', '无记录')

    # === 影像综合整合Agent: 整合07a/07b/07c结论 ===
    elif agent_name == 'imaging_validation':
        ctx['ncct_result'] = previous_outputs.get('ncct_imaging', 'NCCT分析未执行')
        ctx['cta_result'] = previous_outputs.get('cta_imaging', 'CTA分析未执行')
        ctx['ctp_result'] = previous_outputs.get('ctp_imaging', 'CTP分析未执行')
        ctx['tool_aspects'] = row_data.get('tool_aspects', 'N/A')
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['ctp_tool_raw'] = row_data.get('ctp_tool_raw', 'N/A')

    elif agent_name == 'nihss_scorer':
        # [修改] 优先读取专项列，vitals 映射至原文
        ctx['neuro_exam'] = row_data.get('neuro_exam', 'N/A')
        ctx['vitals'] = row_data.get('vitals', full_record)
        ctx['admission_record'] = full_record
        
    elif agent_name == 'fact_extractor':
        # [修改] vitals 和 labs_and_meds 按配置映射至原文
        ctx['admission_record'] = full_record
        ctx['labs_and_meds'] = row_data.get('labs_and_meds', full_record)
        ctx['vitals'] = row_data.get('vitals', full_record)
        
    elif agent_name == 'consistency_check':
        ctx['vlm_findings'] = previous_outputs.get('vlm_findings', '影像分析未执行（可能因出血中止）')
        ctx['admission_record'] = full_record
        ctx['neuro_exam'] = row_data.get('neuro_exam', full_record)
        ctx['rag_context'] = previous_outputs.get('rag_context', '')
        ctx['tool_aspects'] = row_data.get('tool_aspects', 'N/A')
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['ctp_tool_raw'] = row_data.get('ctp_tool_raw', 'N/A')
    
    # [新增] 08 指征筛查
    elif agent_name == 'indication':
        ctx['admission_record'] = full_record
        ctx['rag_context'] = previous_outputs.get('rag_context', '')

    # === Step 4: 总控决策 ===
    elif agent_name == 'director':
        # [修改] 使用精简后的 Fact内容，不再使用 admission_record
        ctx['fact_content'] = row_data.get('fact_content', 'N/A')
        ctx['tool_aspects'] = row_data.get('tool_aspects', 'N/A')
        ctx['nihss_result'] = previous_outputs.get('nihss_scorer', '未执行')
        ctx['imaging_consistency_result'] = previous_outputs.get('lvo', 'LVO判定未执行')
        ctx['antithrombotic_facts'] = previous_outputs.get('fact_extractor', '未执行')
        ctx['indication_result'] = previous_outputs.get('indication', '未执行指征筛查')

        # [新增] 传递一致性检查结果给Director
        ctx['consistency_check_result'] = previous_outputs.get('consistency_check', '未执行一致性检查')
        ctx['imaging_validation_result'] = previous_outputs.get('imaging_validation', '未执行影像整合')  # 影像综合整合结论

        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['is_in_ivt_window'] = previous_outputs.get('is_in_ivt_window', '否')
        ctx['is_in_evt_window'] = previous_outputs.get('is_in_evt_window', '否')
        ctx['hemorrhage_result'] = previous_outputs.get('hemorrhage', 'N/A')
        ctx['aneurysm_result'] = previous_outputs.get('aneurysm', 'N/A')
        ctx['rag_context'] = previous_outputs.get('rag_context', '')
        ctx['onset_hours'] = previous_outputs.get('onset_hours', 'N/A')
        ctx['tool_core_vol'] = row_data.get('tool_core_vol', 'N/A')
        ctx['tool_mismatch'] = row_data.get('tool_mismatch', 'N/A')
    
    return ctx

def get_video_paths_for_agent(agent_name, all_video_paths):
    """
    根据Agent类型返回其需要的视频路径。
    """
    # NCCT 类
    if agent_name == 'hemorrhage' or agent_name == 'ncct_imaging':
        return {'ncct_path': all_video_paths.get('ncct_path', []), 'cta_path': [], 'ctp_path': []}
    
    # CTA 类
    elif agent_name in ['aneurysm', 'cta_imaging']:
        return {'ncct_path': [], 'cta_path': all_video_paths.get('cta_path', []), 'ctp_path': []}
    
    # CTP 类
    elif agent_name == 'ctp_imaging':
        return {'ncct_path': [], 'cta_path': [], 'ctp_path': all_video_paths.get('ctp_path', [])}
        
    # 其他均为纯文本 Agent
    return {'ncct_path': [], 'cta_path': [], 'ctp_path': []}

def agent_call_with_log(agent_name, agent, video_paths, ctx, record_list, logger=None):
    """Helper to run an agent and record logs."""
    input_record = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
        "agent": agent_name,
        "input": {
            "video_paths": {k: v.copy() if isinstance(v, list) else v for k, v in video_paths.items()},
            "context": {k: str(v)[:500] + "..." if len(str(v))>500 else v for k, v in ctx.items()}
        }
    }
    output = agent.run(video_paths, ctx, logger)
    input_record["output"] = output
    parsed_json = parse_json_from_output(output)
    if parsed_json:
        input_record["parsed_decision"] = parsed_json
    
    record_list.append(input_record)
    return output

def rag_retrieve_with_log(rag_engine, key, record_list):
    info = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
        "rag_key": key
    }
    result = rag_engine.retrieve(key)
    info["rag_context"] = result
    record_list.append(info)
    return result

def enhance_context_with_advanced_rag(agent_name, ctx, rag_coordinator, top_k=3, logger=None, log=None):
    """
    使用高级RAG为指定Agent增强上下文（基于文献检索）

    Args:
        agent_name: Agent名称
        ctx: 上下文字典（会被修改）
        rag_coordinator: RAGCoordinator实例
        top_k: 返回文献数量
        logger: 日志记录器
        log: 患者日志字典（用于保存RAG结果到Excel）

    Returns:
        是否成功检索到文献
    """
    if not RAG_AVAILABLE or rag_coordinator is None:
        return False

    try:
        # 映射agent名称到RAG系统识别的名称
        agent_mapping = {
            'indication': 'thrombolysis_agent',  # 指征筛查用溶栓库
            'ncct_imaging': 'ncct_imaging',      # 直接使用，让coordinator映射
            'cta_imaging': 'cta_imaging',        # 直接使用，让coordinator映射
            'ctp_imaging': 'ctp_imaging',        # 直接使用，让coordinator映射
            'nihss_scorer': 'nihss_scorer',      # 直接使用，让coordinator映射
        }

        # 对于取栓和溶栓直接使用原名
        rag_agent_name = agent_mapping.get(agent_name, agent_name + '_agent')

        # 执行检索
        literature = rag_coordinator.retrieve(rag_agent_name, ctx, top_k)

        if literature:
            ctx[f'rag_literature_{agent_name}'] = literature
            # 保存RAG结果到log，以便输出到Excel
            if log is not None:
                log[f'RAG_{agent_name}'] = literature[:2000] if len(literature) > 2000 else literature
            if logger:
                logger.info(f"   ✓ Enhanced RAG: Retrieved {top_k} literature for {agent_name}")
            return True
        else:
            if logger:
                logger.info(f"   ℹ Enhanced RAG: No literature found for {agent_name}")
            return False

    except Exception as e:
        if logger:
            logger.warning(f"   ⚠ Enhanced RAG error for {agent_name}: {e}")
        return False

def save_patient_results(pid, log, workflow_record, detailed_logs_dir):
    """保存单个患者的结果到JSON和Excel文件。"""
    os.makedirs(detailed_logs_dir, exist_ok=True)
    safe_pid = str(pid).replace('/', '_').replace('\\', '_').replace(' ', '_')
    
    json_path = os.path.join(detailed_logs_dir, f"{safe_pid}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(workflow_record, f, ensure_ascii=False, indent=2)
    
    excel_path = os.path.join(detailed_logs_dir, f"{safe_pid}.xlsx")
    df = pd.DataFrame([log])
    df.to_excel(excel_path, index=False)
    return json_path, excel_path

# ================= SINGLE PATIENT WORKFLOW =================

def process_single_patient(row_data_dict, case_index, total_cases, detailed_logs_dir):
    """
    新架构：条件工作流 (Conditional Workflow) + RAG Enhancement
    """
    # ========== 断点续跑检查 ==========
    pid = row_data_dict.get('patient_id')
    if pid:
        json_file = os.path.join(detailed_logs_dir, f"{pid}.json")
        if os.path.exists(json_file):
            # 读取已有结果并返回（静默跳过，不在终端显示）
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_record = json.load(f)
                    return existing_record.get('log', {}), existing_record, pid
            except:
                pass  # 如果读取失败，继续重新处理

    agents = get_agents()
    rag_engine = SimpleRAG()  # 基础RAG（保留原有功能）

    # 初始化高级RAG协调器（每个进程独立初始化）
    rag_coordinator = None
    if RAG_AVAILABLE:
        try:
            # 自动选择最强的 RAG 版本
            if RAG_VERSION.startswith("Hybrid"):
                from rag.hybrid_coordinator import HybridRAGCoordinator
                rag_coordinator = HybridRAGCoordinator()
            else:
                from rag.simple_coordinator import RAGCoordinator
                rag_coordinator = RAGCoordinator()
        except Exception as e:
            # 静默处理，记录到日志
            pass

    pid = row_data_dict.get('patient_id')
    logger = get_patient_logger(pid, detailed_logs_dir)

    logger.info(f"{'='*60}")
    logger.info(f"🚀 Case [{case_index}/{total_cases}]: Patient ID {pid} (Conditional Workflow + RAG)")
    if rag_coordinator:
        logger.info("   📚 Enhanced RAG: ENABLED (9013 literature papers)")
    else:
        logger.info("   📚 Enhanced RAG: DISABLED (using basic SimpleRAG)")
    logger.info(f"{'='*60}")

    raw_data = row_data_dict
    
    ctp_parsed = parse_ctp_tool_string(raw_data.get('ctp_tool_raw', ''))
    raw_data.update(ctp_parsed)
    
    all_video_paths = {
        'ncct_path': split_video_paths(raw_data.get('ncct_path')), 
        'cta_path': split_video_paths(raw_data.get('cta_path')), 
        'ctp_path': split_video_paths(raw_data.get('ctp_path'))
    }
    logger.info(f"   [Data] 视频检测: NCCT={len(all_video_paths['ncct_path'])}, CTA={len(all_video_paths['cta_path'])}, CTP={len(all_video_paths['ctp_path'])}")

    previous_outputs = {}

    workflow_record = {
        "patient_id": pid,
        "process_timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
        "initial_context": {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v 
                           for k, v in raw_data.items()},
        "video_paths": {k: v[:] if isinstance(v, list) else v for k, v in all_video_paths.items()},
        "agent_step_records": [],
        "validation_results": [],
        "final_summary": None
    }

    log = {
        'Patient_ID': pid, 
        'Final_Recommendation': 'N/A', 
        'closed_recommendation': 'N/A', 
        'Clinical_Pathway': 'Unknown',
        'Res_01_Triage': 'Skipped', 'Res_02_Hemorrhage': 'Skipped', 'Res_03_Time': 'Skipped',
        'Res_04_Aneurysm': 'Skipped', 'Res_05_LVO': 'Skipped', 'Res_06_IVT': 'Skipped',
        'Res_07a_NCCT': 'Skipped', 'Res_07b_CTA': 'Skipped', 'Res_07c_CTP': 'Skipped',
        'Res_08_Indication': 'Skipped', 'Res_09_Thrombectomy': 'Skipped',
        'Res_11_NIHSS': 'Skipped', 'Res_12_Facts': 'Skipped', 
        'Res_13_Consistency': 'Skipped', 'Res_14_Director': 'Skipped'
    }

    try:
        # === Step 0: 必查项 (Triage & Time) ===
        logger.info("▶ Step 0: Triage & Time Calculation...")
        
        t_out = agent_call_with_log('triage', agents['triage'], get_video_paths_for_agent('triage', all_video_paths), build_agent_context(raw_data, 'triage', previous_outputs), workflow_record["agent_step_records"], logger)
        log['Res_01_Triage'] = t_out
        previous_outputs['triage'] = t_out
        
        time_out = agent_call_with_log('time_calc', agents['time_calc'], get_video_paths_for_agent('time_calc', all_video_paths), build_agent_context(raw_data, 'time_calc', previous_outputs), workflow_record["agent_step_records"], logger)
        log['Res_03_Time'] = time_out
        
        onset_h = parse_numeric_value(time_out, "Q1")
        is_ivt_win = parse_agent_decision(time_out, "Q2")
        is_evt_win = parse_agent_decision(time_out, "Q3")

        previous_outputs['onset_hours'] = onset_h if onset_h is not None else "未知"
        previous_outputs['is_in_ivt_window'] = "是" if is_ivt_win else "否"
        previous_outputs['is_in_evt_window'] = "是" if is_evt_win else "否"

        # === Step 1: 出血筛查 (Hemorrhage Check) ===
        logger.info("▶ Step 1: Hemorrhage Check...")
        h_out = agent_call_with_log('hemorrhage', agents['hemorrhage'], get_video_paths_for_agent('hemorrhage', all_video_paths), build_agent_context(raw_data, 'hemorrhage', previous_outputs), workflow_record["agent_step_records"], logger)
        log['Res_02_Hemorrhage'] = h_out
        previous_outputs['hemorrhage'] = h_out

        is_bleeding = parse_agent_decision(h_out, "Q2")
        
        if is_bleeding:
            # Branch A: 出血处理流程
            logger.info("   🚨 [CRITICAL] Hemorrhage detected! Entering Hemorrhage Pathway...")
            log['Clinical_Pathway'] = 'Hemorrhage'
            
            aneurysm_out = agent_call_with_log('aneurysm', agents['aneurysm'], get_video_paths_for_agent('aneurysm', all_video_paths), build_agent_context(raw_data, 'aneurysm', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_04_Aneurysm'] = aneurysm_out
            previous_outputs['aneurysm'] = aneurysm_out
            
            fact_out = agent_call_with_log('fact_extractor', agents['fact_extractor'], {}, build_agent_context(raw_data, 'fact_extractor', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_12_Facts'] = fact_out
            previous_outputs['fact_extractor'] = fact_out

            # [新增] 出血分支也执行指征筛查供Director参考
            rag_text = rag_engine.retrieve("thrombolysis") + "\n" + rag_engine.retrieve("thrombectomy")
            previous_outputs['rag_context'] = rag_text

            # [RAG Enhancement] 为indication增强上下文
            ctx_indication = build_agent_context(raw_data, 'indication', previous_outputs)
            enhance_context_with_advanced_rag('indication', ctx_indication, rag_coordinator, top_k=2, logger=logger, log=log)

            logger.info("   ▶ Sub-Step: Indication Screening (Hemorrhage)...")
            ind_out = agent_call_with_log('indication', agents['indication'], {}, ctx_indication, workflow_record["agent_step_records"], logger)
            log['Res_08_Indication'] = ind_out
            previous_outputs['indication'] = ind_out

        else:
            # Branch B: 缺血处理流程
            logger.info("   ✅ No hemorrhage. Entering Ischemic Pathway...")
            log['Clinical_Pathway'] = 'Ischemic'
            
            # 1. 缺血影像全家桶
            logger.info("   ▶ Sub-Step: Ischemic Imaging Suite...")

            # [RAG Enhancement] 为影像Agent增强上下文
            ctx_ncct = build_agent_context(raw_data, 'ncct_imaging')
            enhance_context_with_advanced_rag('ncct_imaging', ctx_ncct, rag_coordinator, top_k=2, logger=logger, log=log)
            ncct_out = agent_call_with_log('ncct_imaging', agents['ncct_imaging'], get_video_paths_for_agent('ncct_imaging', all_video_paths), ctx_ncct, workflow_record["agent_step_records"], logger)
            log['Res_07a_NCCT'] = ncct_out

            ctx_ctp = build_agent_context(raw_data, 'ctp_imaging')
            enhance_context_with_advanced_rag('ctp_imaging', ctx_ctp, rag_coordinator, top_k=2, logger=logger, log=log)
            ctp_out = agent_call_with_log('ctp_imaging', agents['ctp_imaging'], get_video_paths_for_agent('ctp_imaging', all_video_paths), ctx_ctp, workflow_record["agent_step_records"], logger)
            log['Res_07c_CTP'] = ctp_out
            previous_outputs['ctp_imaging'] = ctp_out

            ctx_cta = build_agent_context(raw_data, 'cta_imaging', previous_outputs)
            enhance_context_with_advanced_rag('cta_imaging', ctx_cta, rag_coordinator, top_k=2, logger=logger, log=log)
            cta_out = agent_call_with_log('cta_imaging', agents['cta_imaging'], get_video_paths_for_agent('cta_imaging', all_video_paths), ctx_cta, workflow_record["agent_step_records"], logger)
            log['Res_07b_CTA'] = cta_out
            previous_outputs['cta_imaging'] = cta_out

            lvo_out = agent_call_with_log('lvo', agents['lvo'], get_video_paths_for_agent('lvo', all_video_paths), build_agent_context(raw_data, 'lvo', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_05_LVO'] = lvo_out
            previous_outputs['lvo'] = lvo_out

            # 影像综合整合
            logger.info("   ▶ Sub-Step: Imaging Integration...")
            ctx_validation = build_agent_context(raw_data, 'imaging_validation', previous_outputs)
            validation_out = agent_call_with_log('imaging_validation', agents['imaging_validation'], get_video_paths_for_agent('imaging_validation', all_video_paths), ctx_validation, workflow_record["agent_step_records"], logger)
            log['Res_07d_Integration'] = validation_out
            previous_outputs['imaging_validation'] = validation_out

            # 整合各影像Agent结论
            vlm_findings = f"【出血】:{h_out}\n【NCCT】:{ncct_out}\n【CTP】:{ctp_out}\n【CTA】:{cta_out}\n【LVO】:{lvo_out}\n【影像综合结论】:{validation_out}"
            previous_outputs['vlm_findings'] = vlm_findings
            log['Res_07_Imaging_Summary'] = vlm_findings[:3000]

            # 2. 文本专员
            logger.info("   ▶ Sub-Step: Text Analysis...")
            nihss_out = agent_call_with_log('nihss_scorer', agents['nihss_scorer'], {}, build_agent_context(raw_data, 'nihss_scorer', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_11_NIHSS'] = nihss_out
            previous_outputs['nihss_scorer'] = nihss_out

            fact_out = agent_call_with_log('fact_extractor', agents['fact_extractor'], {}, build_agent_context(raw_data, 'fact_extractor', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_12_Facts'] = fact_out
            previous_outputs['fact_extractor'] = fact_out

            # 3. 一致性校验与指征筛查
            logger.info("   ▶ Sub-Step: Consistency & Indication Check...")
            rag_text = rag_engine.retrieve("thrombolysis") + "\n" + rag_engine.retrieve("thrombectomy")
            previous_outputs['rag_context'] = rag_text

            cons_out = agent_call_with_log('consistency_check', agents['consistency_check'], {}, build_agent_context(raw_data, 'consistency_check', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_13_Consistency'] = cons_out
            previous_outputs['consistency_check'] = cons_out

            # [新增+RAG Enhancement] 缺血分支执行指征筛查
            ctx_indication = build_agent_context(raw_data, 'indication', previous_outputs)
            enhance_context_with_advanced_rag('indication', ctx_indication, rag_coordinator, top_k=3, logger=logger, log=log)
            ind_out = agent_call_with_log('indication', agents['indication'], {}, ctx_indication, workflow_record["agent_step_records"], logger)
            log['Res_08_Indication'] = ind_out
            previous_outputs['indication'] = ind_out
            previous_outputs['indication'] = ind_out

        # === Step 4: 总控决策 ===
        logger.info("▶ Step 4: Director Final Decision...")
        
        dir_out = agent_call_with_log('director', agents['director'], {}, build_agent_context(raw_data, 'director', previous_outputs), workflow_record["agent_step_records"], logger)
        log['Res_14_Director'] = dir_out
        
        try:
            dir_json = parse_json_from_output(dir_out)
            if dir_json and "sign_off" in dir_json and "final_statement" in dir_json["sign_off"]:
                 rec = dir_json["sign_off"]["final_statement"]
            elif "final_statement" in dir_out:
                match = re.search(r'"final_statement":\s*"(.*?)"', dir_out)
                rec = match.group(1) if match else "见详细报告"
            else:
                rec = "Director Output Generated"
            log['Final_Recommendation'] = rec

            closed_rec = "N/A"
            if dir_json:
                closed_data = dir_json.get("closed_outcome", {})
                code = closed_data.get("best_option_code", "N/A")
                text = closed_data.get("best_option_text", "")
                if code == "D":
                    other_diag = closed_data.get("other_disease_diagnosis", "")
                    if other_diag: text = f"{text}({other_diag})"
                
                sec_code = closed_data.get("secondary_option_code", "None")
                sec_text = ""
                if sec_code in ["A", "B", "C", "D"]:
                    mapping = {"A": "溶栓治疗", "B": "取栓治疗或桥接治疗", "C": "保守治疗", "D": "其他疾病"}
                    sec_text = mapping.get(sec_code, "")

                reason = closed_data.get("reasoning", "")
                parts = []
                if code != "N/A": parts.append(f"首选【{code}】{text}")
                if sec_code in ["A", "B", "C", "D"]: parts.append(f"次选【{sec_code}】{sec_text}")
                if reason: parts.append(f"理由：{reason}")
                closed_rec = "\n".join(parts)
            
            log['closed_recommendation'] = closed_rec
        except:
            log['Final_Recommendation'] = "Parse Error"
            log['closed_recommendation'] = "Parse Error"

        workflow_record["final_summary"] = {
            "final_recommendation": log['Final_Recommendation'],
            "closed_recommendation": log['closed_recommendation'],
            "director_full_json": parse_json_from_output(dir_out)
        }
        
        save_patient_results(pid, log, workflow_record, detailed_logs_dir)
        logger.info(f"   ✅ Done: {log['closed_recommendation'].replace(chr(10), ' ')}")

    except Exception as e:
        logger.error(f"   ❌ 处理患者 {pid} 时发生错误: {str(e)}")
        log['Final_Recommendation'] = f"处理错误: {str(e)}"
        workflow_record["error"] = str(e)
        save_patient_results(pid, log, workflow_record, detailed_logs_dir)
    
    return log, workflow_record, pid

def process_patient_wrapper(args):
    row_data_dict, case_index, total_cases, detailed_logs_dir = args
    return process_single_patient(row_data_dict, case_index, total_cases, detailed_logs_dir)

# ================= MAIN WORKFLOW =================

def run_experiment(parallel=True, max_workers=MAX_WORKERS, output_path=None):
    # 如果没有指定输出路径，使用默认路径
    if output_path is None:
        output_path = OUTPUT_PATH

    df = load_experiment_data(EXCEL_PATH)
    os.makedirs(DETAILED_LOGS_DIR, exist_ok=True)

    all_results = []
    all_workflow_records = []
    total_cases = len(df)

    # 显示启动信息
    print("="*60)
    print(f"🚀 医学影像 AI 分析系统")
    print(f"   总案例数: {total_cases}")
    print(f"   并行处理: {'是' if parallel and max_workers > 1 else '否'} (workers={max_workers if parallel else 1})")
    print(f"   RAG 模式: {RAG_VERSION if RAG_AVAILABLE else 'Disabled'}")
    print(f"   日志目录: {DETAILED_LOGS_DIR}")
    print("="*60)
    print()

    tasks = []
    for index, row in enumerate(df.iterrows()):
        _, row_data = row
        row_data_dict = row_data.to_dict()
        tasks.append((row_data_dict, index + 1, total_cases, DETAILED_LOGS_DIR))

    if parallel and max_workers > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_patient_wrapper, task): task[0].get('patient_id') 
                      for task in tasks}
            
            for future in tqdm(as_completed(futures), total=len(futures), desc="处理进度"):
                pid = futures[future]
                try:
                    log, workflow_record, _ = future.result()
                    all_results.append(log)
                    all_workflow_records.append(workflow_record)
                except Exception as e:
                    all_results.append({
                        'Patient_ID': pid,
                        'Final_Recommendation': f'处理失败: {str(e)}'
                    })
    else:
        for task in tqdm(tasks, desc="处理进度"):
            log, workflow_record, pid = process_patient_wrapper(task)
            all_results.append(log)
            all_workflow_records.append(workflow_record)

    pd.DataFrame(all_results).to_excel(output_path, index=False)
    print(f"\n{'='*60}")
    print(f"✅ 处理完成!")
    print(f"   总案例数: {total_cases}")
    print(f"   结果文件: {output_path}")
    print(f"   日志目录: {DETAILED_LOGS_DIR}")
    print(f"{'='*60}")
    with open(JSON_OUTPUT_PATH, "w", encoding="utf-8") as json_log_fp:
        for record in all_workflow_records:
            json_log_fp.write(json.dumps(record, ensure_ascii=False) + "\n")

def run_single_patient(patient_id_or_index, excel_path=EXCEL_PATH):
    df = load_experiment_data(excel_path)
    os.makedirs(DETAILED_LOGS_DIR, exist_ok=True)
    
    if isinstance(patient_id_or_index, int):
        if patient_id_or_index < len(df):
            row_data = df.iloc[patient_id_or_index].to_dict()
        else:
            return None
    else:
        matches = df[df['patient_id'] == patient_id_or_index]
        if len(matches) == 0:
            return None
        row_data = matches.iloc[0].to_dict()
    
    log, workflow_record, pid = process_single_patient(
        row_data, 1, 1, DETAILED_LOGS_DIR
    )
    return log, workflow_record

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='CDSS临床决策工作流')
    parser.add_argument('--single', type=str, default=None, 
                       help='处理单个患者（指定patient_id或索引）')
    parser.add_argument('--parallel', action='store_true', default=True,
                       help='启用并行处理')
    parser.add_argument('--no-parallel', action='store_false', dest='parallel',
                       help='禁用并行处理')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS,
                       help=f'并行处理的最大进程数 (默认: {MAX_WORKERS})')
    parser.add_argument('--output', type=str, default=None,
                       help='自定义输出Excel文件路径 (默认: logs/final_experiment_results.xlsx)')
    args = parser.parse_args()
    
    if args.single:
        try:
            patient_id_or_index = int(args.single)
        except ValueError:
            patient_id_or_index = args.single
        run_single_patient(patient_id_or_index)
    else:
        run_experiment(parallel=args.parallel, max_workers=args.workers, output_path=args.output)