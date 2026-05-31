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
# Auto-select the strongest RAG version
RAG_COORDINATOR = None
RAG_AVAILABLE = False
RAG_VERSION = "None"

# Priority 1: Hybrid Retrieval RAG (strongest)
try:
    from rag.hybrid_coordinator import HybridRAGCoordinator
    RAG_COORDINATOR = None  # Lazy initialization
    RAG_AVAILABLE = True
    RAG_VERSION = "Hybrid (Semantic + BM25 + Reranking)"
    # Silent loading, no terminal output
except ImportError:
    pass

# Priority 2: Simple RAG (TF-IDF)
if not RAG_AVAILABLE:
    try:
        from rag.simple_coordinator import RAGCoordinator
        RAG_COORDINATOR = None
        RAG_AVAILABLE = True
        RAG_VERSION = "Simple (TF-IDF)"
        # Silent loading
    except ImportError as e:
        RAG_AVAILABLE = False
        # Silent handling, no terminal output

# ================= CONFIGURATION =================
EXCEL_PATH = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6/data/experiment_data1.xlsx"
OUTPUT_PATH = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6/results_v6_data1/final_results.xlsx"
JSON_OUTPUT_PATH = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6/results_v6_data1/final_results.xlsx"
DETAILED_LOGS_DIR = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6/results_v6_data1/detailed_logs"
ROOT_DIR = "/data/qunhui_21T/Yan-20250730/code/agent_project_v6"
# Parallel configuration
MAX_WORKERS = 10  # Maximum number of parallel worker processes

# ================= LOGGING SETUP =================

def get_patient_logger(patient_id, logs_dir):
    """
    Create an independent logger for each patient, outputting to patient_id.log file.
    """
    safe_pid = str(patient_id).replace('/', '_').replace('\\', '_').replace(' ', '_')
    log_file = os.path.join(logs_dir, f"{safe_pid}.log")
    
    logger = logging.getLogger(f"patient_{safe_pid}")
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers to avoid duplication
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
    """Create Agent instances (each process needs its own instances).
    See prompts/README.md for the paper agent name mapping (Supplementary Table S1).
    """
    return {
        # --- Step 0 & 1: Triage/Hemorrhage (Common) ---
        'triage': ReActClinicalAgent(f"{ROOT_DIR}/prompts/01_triage_agent.md"),
        'time_calc': ReActClinicalAgent(f"{ROOT_DIR}/prompts/03_time_calc_agent.md"),
        'hemorrhage': ReActClinicalAgent(f"{ROOT_DIR}/prompts/02_hemorrhage_agent.md"),

        # --- Branch A: Hemorrhage Pathway ---
        'aneurysm': ReActClinicalAgent(f"{ROOT_DIR}/prompts/04_aneurysm_agent.md"),

        # --- Branch B: Ischemic Pathway ---
        'lvo': ReActClinicalAgent(f"{ROOT_DIR}/prompts/05_lvo_agent.md"),
        'ncct_imaging': ReActClinicalAgent(f"{ROOT_DIR}/prompts/07a_ncct_imaging_agent.md"),
        'cta_imaging': ReActClinicalAgent(f"{ROOT_DIR}/prompts/07b_cta_imaging_agent.md"),
        'ctp_imaging': ReActClinicalAgent(f"{ROOT_DIR}/prompts/07c_ctp_imaging_agent.md"),
        'imaging_validation': ReActClinicalAgent(f"{ROOT_DIR}/prompts/07_imaging_agent.md"),  # Imaging integration
        'nihss_scorer': ReActClinicalAgent(f"{ROOT_DIR}/prompts/11_nihss_scorer.md"),
        'fact_extractor': ReActClinicalAgent(f"{ROOT_DIR}/prompts/12_fact_extractor.md"),
        'consistency_check': ReActClinicalAgent(f"{ROOT_DIR}/prompts/13_consistency_check.md"),
        'indication': ReActClinicalAgent(f"{ROOT_DIR}/prompts/08_indication_agent.md"),

        # --- Step 4: Director (Common Exit) ---
        'director': ReActClinicalAgent(f"{ROOT_DIR}/prompts/14_director_agent.md"),
    }

def parse_json_from_output(text):
    """Extract JSON-formatted decision results from Agent output."""
    if not isinstance(text, str):
        return None
    
    # Try extracting markdown JSON code block
    json_pattern = re.compile(r'```json\s*([\s\S]*?)\s*```', re.IGNORECASE)
    match = json_pattern.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try direct parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try extracting {}
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
    
    return None

def parse_agent_decision(text, target_q="Q2"):
    """[Enhanced Parser] Attempt to extract Yes/No answers from JSON or text"""
    if not isinstance(text, str):
        return False
    
    # 1. Try JSON first
    json_result = parse_json_from_output(text)
    if json_result and target_q in json_result:
        answer = str(json_result[target_q]).lower()
        if "是" in answer or "yes" in answer or answer == "true":
            return True
        if "否" in answer or "no" in answer or answer == "false":
            return False

    # 2. Regex match "Q2.....(Yes/No)"
    pattern = re.compile(rf"{target_q}.*?([YesNo是否])", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)

    if match:
        answer = match.group(1).lower()
        if "是" in answer or "y" in answer: return True
        if "否" in answer or "n" in answer: return False

    # 3. Text-based fuzzy matching
    try:
        if target_q in text:
            part = text.split(target_q)[1]
            if "是" in part or "yes" in part.lower() or "推荐" in part or "符合" in part:
                return True
    except:
        pass

    # 4. Fallback
    if "是" in text or "yes" in text.lower():
        return True

    return False

def parse_numeric_value(text, target_q):
    """Extract numeric answer from Agent output"""
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
    """Parse A/B/C/D/E options for Director (E is special handling for arterial dissection)"""
    json_res = parse_json_from_output(text)
    if json_res and "closed_outcome" in json_res:
        return json_res["closed_outcome"].get("best_option_code", "N/A")
    return "N/A"

def parse_string_value(text, target_q):
    """Extract string answer from Agent output"""
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
    """Parse CTP tool output string"""
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
    Build context matching the prompt template for each Agent type.
    """
    ctx = {}
    previous_outputs = previous_outputs or {}
    
    # 1. Pre-extract data
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
    
    # === Branch A: Hemorrhage Pathway ===
    elif agent_name == 'aneurysm':
        ctx['hemorrhage_output'] = previous_outputs.get('hemorrhage', 'N/A')
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['chief_complaint'] = chief_complaint_text

    # === Branch B: Ischemic Pathway ===
    elif agent_name == 'lvo':
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['cta_tool_findings'] = row_data.get('cta_tool_findings', 'No record available')
        ctx['cta_imaging_output'] = previous_outputs.get('cta_imaging', 'CTA imaging analysis not executed or failed')
        ctx['admission_record'] = full_record
        
    elif agent_name == 'ncct_imaging':
        ctx['tool_aspects'] = row_data.get('tool_aspects', 'N/A')
        
    elif agent_name == 'cta_imaging':
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['cta_tool_findings'] = row_data.get('cta_tool_findings', 'No record available')
        ctx['ctp_feedback'] = previous_outputs.get('ctp_imaging', 'CTP not executed or no result')
        
    elif agent_name == 'ctp_imaging':
        ctx['ctp_tool_raw'] = row_data.get('ctp_tool_raw', 'N/A')
        ctx['ctp_tool_findings'] = row_data.get('ctp_tool_findings', 'No record available')

    # === Imaging Integration Agent: Merge 07a/07b/07c conclusions ===
    elif agent_name == 'imaging_validation':
        ctx['ncct_result'] = previous_outputs.get('ncct_imaging', 'NCCT analysis not executed')
        ctx['cta_result'] = previous_outputs.get('cta_imaging', 'CTA analysis not executed')
        ctx['ctp_result'] = previous_outputs.get('ctp_imaging', 'CTP analysis not executed')
        ctx['tool_aspects'] = row_data.get('tool_aspects', 'N/A')
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['ctp_tool_raw'] = row_data.get('ctp_tool_raw', 'N/A')

    elif agent_name == 'nihss_scorer':
        # [Modified] Prioritize specialized columns, vitals mapped to original text
        ctx['neuro_exam'] = row_data.get('neuro_exam', 'N/A')
        ctx['vitals'] = row_data.get('vitals', full_record)
        ctx['admission_record'] = full_record
        
    elif agent_name == 'fact_extractor':
        # [Modified] vitals and labs_and_meds mapped to original text per config
        ctx['admission_record'] = full_record
        ctx['labs_and_meds'] = row_data.get('labs_and_meds', full_record)
        ctx['vitals'] = row_data.get('vitals', full_record)
        
    elif agent_name == 'consistency_check':
        ctx['vlm_findings'] = previous_outputs.get('vlm_findings', 'Imaging analysis not executed (possibly stopped due to hemorrhage)')
        ctx['admission_record'] = full_record
        ctx['neuro_exam'] = row_data.get('neuro_exam', full_record)
        ctx['rag_context'] = previous_outputs.get('rag_context', '')
        ctx['tool_aspects'] = row_data.get('tool_aspects', 'N/A')
        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['ctp_tool_raw'] = row_data.get('ctp_tool_raw', 'N/A')
    
    # [New] 08 Indication screening
    elif agent_name == 'indication':
        ctx['admission_record'] = full_record
        ctx['rag_context'] = previous_outputs.get('rag_context', '')

    # === Step 4: Director Decision ===
    elif agent_name == 'director':
        # [Modified] Use condensed Fact content instead of admission_record
        ctx['fact_content'] = row_data.get('fact_content', 'N/A')
        ctx['tool_aspects'] = row_data.get('tool_aspects', 'N/A')
        ctx['nihss_result'] = previous_outputs.get('nihss_scorer', 'Not executed')
        ctx['imaging_consistency_result'] = previous_outputs.get('lvo', 'LVO determination not executed')
        ctx['antithrombotic_facts'] = previous_outputs.get('fact_extractor', 'Not executed')
        ctx['indication_result'] = previous_outputs.get('indication', 'Indication screening not executed')

        # [New] Pass consistency check result to Director
        ctx['consistency_check_result'] = previous_outputs.get('consistency_check', 'Consistency check not executed')
        ctx['imaging_validation_result'] = previous_outputs.get('imaging_validation', 'Imaging integration not executed')  # Imaging integration conclusion

        ctx['cta_tool_raw'] = row_data.get('cta_tool_raw', 'N/A')
        ctx['is_in_ivt_window'] = previous_outputs.get('is_in_ivt_window', 'No')
        ctx['is_in_evt_window'] = previous_outputs.get('is_in_evt_window', 'No')
        ctx['hemorrhage_result'] = previous_outputs.get('hemorrhage', 'N/A')
        ctx['aneurysm_result'] = previous_outputs.get('aneurysm', 'N/A')
        ctx['rag_context'] = previous_outputs.get('rag_context', '')
        ctx['onset_hours'] = previous_outputs.get('onset_hours', 'N/A')
        ctx['tool_core_vol'] = row_data.get('tool_core_vol', 'N/A')
        ctx['tool_mismatch'] = row_data.get('tool_mismatch', 'N/A')
    
    return ctx

def get_video_paths_for_agent(agent_name, all_video_paths):
    """
    Return video paths needed by the Agent based on its type.
    """
    # NCCT type
    if agent_name == 'hemorrhage' or agent_name == 'ncct_imaging':
        return {'ncct_path': all_video_paths.get('ncct_path', []), 'cta_path': [], 'ctp_path': []}
    
    # CTA type
    elif agent_name in ['aneurysm', 'cta_imaging']:
        return {'ncct_path': [], 'cta_path': all_video_paths.get('cta_path', []), 'ctp_path': []}
    
    # CTP type
    elif agent_name == 'ctp_imaging':
        return {'ncct_path': [], 'cta_path': [], 'ctp_path': all_video_paths.get('ctp_path', [])}
        
    # All others are text-only Agents
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
    Enhance context for the specified Agent using advanced RAG (literature-based retrieval)

    Args:
        agent_name: Agent name
        ctx: Context dictionary (modified in-place)
        rag_coordinator: RAGCoordinator instance
        top_k: Number of literature results to return
        logger: Logger instance
        log: Patient log dictionary (for saving RAG results to Excel)

    Returns:
        Whether literature was successfully retrieved
    """
    if not RAG_AVAILABLE or rag_coordinator is None:
        return False

    try:
        # Map agent name to RAG system recognized name
        agent_mapping = {
            'indication': 'thrombolysis_agent',  # Indication screening uses thrombolysis KB
            'ncct_imaging': 'ncct_imaging',      # Use directly, let coordinator map
            'cta_imaging': 'cta_imaging',        # Use directly, let coordinator map
            'ctp_imaging': 'ctp_imaging',        # Use directly, let coordinator map
            'nihss_scorer': 'nihss_scorer',      # Use directly, let coordinator map
        }

        # For thrombectomy and thrombolysis, use original name
        rag_agent_name = agent_mapping.get(agent_name, agent_name + '_agent')

        # Execute retrieval
        literature = rag_coordinator.retrieve(rag_agent_name, ctx, top_k)

        if literature:
            ctx[f'rag_literature_{agent_name}'] = literature
            # Save RAG results to log for Excel output
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
    """Save a single patient's results to JSON and Excel files."""
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
    New architecture: Conditional Workflow + RAG Enhancement
    """
    # ========== Checkpoint resume check ==========
    pid = row_data_dict.get('patient_id')
    if pid:
        json_file = os.path.join(detailed_logs_dir, f"{pid}.json")
        if os.path.exists(json_file):
            # Read existing results and return (silent skip, no terminal output)
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_record = json.load(f)
                    return existing_record.get('log', {}), existing_record, pid
            except:
                pass  # If read fails, continue to reprocess

    agents = get_agents()
    rag_engine = SimpleRAG()  # Basic RAG (preserves original functionality)

    # Initialize advanced RAG coordinator (independent per process)
    rag_coordinator = None
    if RAG_AVAILABLE:
        try:
            # Auto-select the strongest RAG version
            if RAG_VERSION.startswith("Hybrid"):
                from rag.hybrid_coordinator import HybridRAGCoordinator
                rag_coordinator = HybridRAGCoordinator()
            else:
                from rag.simple_coordinator import RAGCoordinator
                rag_coordinator = RAGCoordinator()
        except Exception as e:
            # Silent handling, log internally
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
    logger.info(f"   [Data] Video detection: NCCT={len(all_video_paths['ncct_path'])}, CTA={len(all_video_paths['cta_path'])}, CTP={len(all_video_paths['ctp_path'])}")

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
        # === Step 0: Mandatory Checks (Triage & Time) ===
        logger.info("▶ Step 0: Triage & Time Calculation...")
        
        t_out = agent_call_with_log('triage', agents['triage'], get_video_paths_for_agent('triage', all_video_paths), build_agent_context(raw_data, 'triage', previous_outputs), workflow_record["agent_step_records"], logger)
        log['Res_01_Triage'] = t_out
        previous_outputs['triage'] = t_out
        
        time_out = agent_call_with_log('time_calc', agents['time_calc'], get_video_paths_for_agent('time_calc', all_video_paths), build_agent_context(raw_data, 'time_calc', previous_outputs), workflow_record["agent_step_records"], logger)
        log['Res_03_Time'] = time_out
        
        onset_h = parse_numeric_value(time_out, "Q1")
        is_ivt_win = parse_agent_decision(time_out, "Q2")
        is_evt_win = parse_agent_decision(time_out, "Q3")

        previous_outputs['onset_hours'] = onset_h if onset_h is not None else "Unknown"
        previous_outputs['is_in_ivt_window'] = "Yes" if is_ivt_win else "No"
        previous_outputs['is_in_evt_window'] = "Yes" if is_evt_win else "No"

        # === Step 1: Hemorrhage Screening ===
        logger.info("▶ Step 1: Hemorrhage Check...")
        h_out = agent_call_with_log('hemorrhage', agents['hemorrhage'], get_video_paths_for_agent('hemorrhage', all_video_paths), build_agent_context(raw_data, 'hemorrhage', previous_outputs), workflow_record["agent_step_records"], logger)
        log['Res_02_Hemorrhage'] = h_out
        previous_outputs['hemorrhage'] = h_out

        is_bleeding = parse_agent_decision(h_out, "Q2")
        
        if is_bleeding:
            # Branch A: Hemorrhage Pathway
            logger.info("   🚨 [CRITICAL] Hemorrhage detected! Entering Hemorrhage Pathway...")
            log['Clinical_Pathway'] = 'Hemorrhage'
            
            aneurysm_out = agent_call_with_log('aneurysm', agents['aneurysm'], get_video_paths_for_agent('aneurysm', all_video_paths), build_agent_context(raw_data, 'aneurysm', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_04_Aneurysm'] = aneurysm_out
            previous_outputs['aneurysm'] = aneurysm_out
            
            fact_out = agent_call_with_log('fact_extractor', agents['fact_extractor'], {}, build_agent_context(raw_data, 'fact_extractor', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_12_Facts'] = fact_out
            previous_outputs['fact_extractor'] = fact_out

            # [New] Hemorrhage branch also runs indication screening for Director reference
            rag_text = rag_engine.retrieve("thrombolysis") + "\n" + rag_engine.retrieve("thrombectomy")
            previous_outputs['rag_context'] = rag_text

            # [RAG Enhancement] Enhance context for indication
            ctx_indication = build_agent_context(raw_data, 'indication', previous_outputs)
            enhance_context_with_advanced_rag('indication', ctx_indication, rag_coordinator, top_k=2, logger=logger, log=log)

            logger.info("   ▶ Sub-Step: Indication Screening (Hemorrhage)...")
            ind_out = agent_call_with_log('indication', agents['indication'], {}, ctx_indication, workflow_record["agent_step_records"], logger)
            log['Res_08_Indication'] = ind_out
            previous_outputs['indication'] = ind_out

        else:
            # Branch B: Ischemic Pathway
            logger.info("   ✅ No hemorrhage. Entering Ischemic Pathway...")
            log['Clinical_Pathway'] = 'Ischemic'
            
            # 1. Full ischemic imaging suite
            logger.info("   ▶ Sub-Step: Ischemic Imaging Suite...")

            # [RAG Enhancement] Enhance context for imaging Agents
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

            # Imaging integration
            logger.info("   ▶ Sub-Step: Imaging Integration...")
            ctx_validation = build_agent_context(raw_data, 'imaging_validation', previous_outputs)
            validation_out = agent_call_with_log('imaging_validation', agents['imaging_validation'], get_video_paths_for_agent('imaging_validation', all_video_paths), ctx_validation, workflow_record["agent_step_records"], logger)
            log['Res_07d_Integration'] = validation_out
            previous_outputs['imaging_validation'] = validation_out

            # Integrate conclusions from all imaging Agents
            vlm_findings = f"[Hemorrhage]:{h_out}\n[NCCT]:{ncct_out}\n[CTP]:{ctp_out}\n[CTA]:{cta_out}\n[LVO]:{lvo_out}\n[Imaging Conclusion]:{validation_out}"
            previous_outputs['vlm_findings'] = vlm_findings
            log['Res_07_Imaging_Summary'] = vlm_findings[:3000]

            # 2. Text analysis Agents
            logger.info("   ▶ Sub-Step: Text Analysis...")
            nihss_out = agent_call_with_log('nihss_scorer', agents['nihss_scorer'], {}, build_agent_context(raw_data, 'nihss_scorer', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_11_NIHSS'] = nihss_out
            previous_outputs['nihss_scorer'] = nihss_out

            fact_out = agent_call_with_log('fact_extractor', agents['fact_extractor'], {}, build_agent_context(raw_data, 'fact_extractor', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_12_Facts'] = fact_out
            previous_outputs['fact_extractor'] = fact_out

            # 3. Consistency check and indication screening
            logger.info("   ▶ Sub-Step: Consistency & Indication Check...")
            rag_text = rag_engine.retrieve("thrombolysis") + "\n" + rag_engine.retrieve("thrombectomy")
            previous_outputs['rag_context'] = rag_text

            cons_out = agent_call_with_log('consistency_check', agents['consistency_check'], {}, build_agent_context(raw_data, 'consistency_check', previous_outputs), workflow_record["agent_step_records"], logger)
            log['Res_13_Consistency'] = cons_out
            previous_outputs['consistency_check'] = cons_out

            # [New+RAG Enhancement] Ischemic branch runs indication screening
            ctx_indication = build_agent_context(raw_data, 'indication', previous_outputs)
            enhance_context_with_advanced_rag('indication', ctx_indication, rag_coordinator, top_k=3, logger=logger, log=log)
            ind_out = agent_call_with_log('indication', agents['indication'], {}, ctx_indication, workflow_record["agent_step_records"], logger)
            log['Res_08_Indication'] = ind_out
            previous_outputs['indication'] = ind_out
            previous_outputs['indication'] = ind_out

        # === Step 4: Director Decision ===
        logger.info("▶ Step 4: Director Final Decision...")
        
        dir_out = agent_call_with_log('director', agents['director'], {}, build_agent_context(raw_data, 'director', previous_outputs), workflow_record["agent_step_records"], logger)
        log['Res_14_Director'] = dir_out
        
        try:
            dir_json = parse_json_from_output(dir_out)
            if dir_json and "sign_off" in dir_json and "final_statement" in dir_json["sign_off"]:
                 rec = dir_json["sign_off"]["final_statement"]
            elif "final_statement" in dir_out:
                match = re.search(r'"final_statement":\s*"(.*?)"', dir_out)
                rec = match.group(1) if match else "See detailed report"
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
                    mapping = {"A": "Thrombolysis (IVT)", "B": "Thrombectomy or Bridging", "C": "Conservative Management", "D": "Other Disease"}
                    sec_text = mapping.get(sec_code, "")

                reason = closed_data.get("reasoning", "")
                parts = []
                if code != "N/A": parts.append(f"Primary [{code}] {text}")
                if sec_code in ["A", "B", "C", "D"]: parts.append(f"Secondary [{sec_code}] {sec_text}")
                if reason: parts.append(f"Reason: {reason}")
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
        logger.error(f"   ❌ Error processing patient {pid}: {str(e)}")
        log['Final_Recommendation'] = f"Processing error: {str(e)}"
        workflow_record["error"] = str(e)
        save_patient_results(pid, log, workflow_record, detailed_logs_dir)
    
    return log, workflow_record, pid

def process_patient_wrapper(args):
    row_data_dict, case_index, total_cases, detailed_logs_dir = args
    return process_single_patient(row_data_dict, case_index, total_cases, detailed_logs_dir)

# ================= MAIN WORKFLOW =================

def run_experiment(parallel=True, max_workers=MAX_WORKERS, output_path=None):
    # Use default output path if not specified
    if output_path is None:
        output_path = OUTPUT_PATH

    df = load_experiment_data(EXCEL_PATH)
    os.makedirs(DETAILED_LOGS_DIR, exist_ok=True)

    all_results = []
    all_workflow_records = []
    total_cases = len(df)

    # Display startup info
    print("="*60)
    print(f"🚀 Medical Imaging AI Analysis System")
    print(f"   Total cases: {total_cases}")
    print(f"   Parallel: {'Yes' if parallel and max_workers > 1 else 'No'} (workers={max_workers if parallel else 1})")
    print(f"   RAG Mode: {RAG_VERSION if RAG_AVAILABLE else 'Disabled'}")
    print(f"   Log directory: {DETAILED_LOGS_DIR}")
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
            
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
                pid = futures[future]
                try:
                    log, workflow_record, _ = future.result()
                    all_results.append(log)
                    all_workflow_records.append(workflow_record)
                except Exception as e:
                    all_results.append({
                        'Patient_ID': pid,
                        'Final_Recommendation': f'Processing failed: {str(e)}'
                    })
    else:
        for task in tqdm(tasks, desc="Processing"):
            log, workflow_record, pid = process_patient_wrapper(task)
            all_results.append(log)
            all_workflow_records.append(workflow_record)

    pd.DataFrame(all_results).to_excel(output_path, index=False)
    print(f"\n{'='*60}")
    print(f"✅ Processing complete!")
    print(f"   Total cases: {total_cases}")
    print(f"   Results file: {output_path}")
    print(f"   Log directory: {DETAILED_LOGS_DIR}")
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
    parser = argparse.ArgumentParser(description='CDSS Clinical Decision Workflow')
    parser.add_argument('--single', type=str, default=None,
                       help='Process a single patient (specify patient_id or index)')
    parser.add_argument('--parallel', action='store_true', default=True,
                       help='Enable parallel processing')
    parser.add_argument('--no-parallel', action='store_false', dest='parallel',
                       help='Disable parallel processing')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS,
                       help=f'Max number of parallel worker processes (default: {MAX_WORKERS})')
    parser.add_argument('--output', type=str, default=None,
                       help='Custom output Excel file path (default: logs/final_experiment_results.xlsx)')
    args = parser.parse_args()
    
    if args.single:
        try:
            patient_id_or_index = int(args.single)
        except ValueError:
            patient_id_or_index = args.single
        run_single_patient(patient_id_or_index)
    else:
        run_experiment(parallel=args.parallel, max_workers=args.workers, output_path=args.output)