# agents/react_agent.py

import json
import os
import re
import time
from utils.llm_client import call_llm_with_config
from utils.prompt_parser import parse_agent_prompt

class ReActClinicalAgent:
    def __init__(self, prompt_file, model_key=None):
        """
        初始化 Agent

        Args:
            prompt_file: 可以是绝对路径，也可以是相对于prompts目录的文件名
            model_key: 模型键名 (可选，如 'qwen_vl', 'gpt_oss')
                      如果不指定，将根据 agent 名称自动选择
        """
        self.model_key = model_key

        # 如果是绝对路径则直接使用，否则拼接prompts目录
        if os.path.isabs(prompt_file):
            self.prompt_path = prompt_file
        else:
            self.prompt_path = os.path.join("prompts", prompt_file)

        self.name = os.path.basename(prompt_file).replace('.md', '')
        self.prompts = parse_agent_prompt(self.prompt_path)
        self.history = []  # 记录每一次交互（输入/输出/时间戳）

    def _safe_format(self, template, context):
        """
        防止 KeyError 的安全格式化
        """
        keys = re.findall(r'\{([a-zA-Z0-9_]+)\}', template)
        
        formatted_text = template
        for key in set(keys):
            val = str(context.get(key, "N/A"))
            formatted_text = formatted_text.replace(f"{{{key}}}", val)
        return formatted_text

    def _parse_check(self, text):
        """解析 Self-Check JSON"""
        try:
            clean_text = text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            return data.get("status", "FAIL").upper(), data.get("feedback", "")
        except:
            if "PASS" in text.upper(): return "PASS", ""
            return "FAIL", "JSON Parse Error"

    def run(self, video_paths, context, logger=None, max_retries=3):
        """
        主方法: 运行 agent 并完整记录每一次调用的输入/输出/时间戳
        返回 act 阶段的输出
        """
        # 确定输入视频路径
        vid = None
        
        # 1. 纯文本类 Agent (无需视频)
        # [改进] 显式加入 'summary'
        if any(k in self.name for k in ['triage', 'time_calc', 'thrombolysis', 'indication', 'thrombectomy', 'summary']):
            vid = None 
            
        # 2. NCCT 类
        elif 'hemorrhage' in self.name or 'ncct_imaging' in self.name: 
            vid = video_paths.get('ncct_path')
            
        # 3. CTA 类
        elif 'aneurysm' in self.name or 'lvo' in self.name or 'cta_imaging' in self.name: 
            vid = video_paths.get('cta_path')
            
        # 4. CTP 类
        elif 'ctp_imaging' in self.name:
            vid = video_paths.get('ctp_path')
            
        # 5. 旧版兼容 (兜底)
        elif 'imaging' in self.name: 
            vid = video_paths.get('ctp_path')

        last_act = "Error"
        feedback = ""
        self.history = []  
        
        ctx_str = json.dumps(
            {k:v for k,v in context.items() if 'path' not in k}, 
            default=str, 
            ensure_ascii=False
        )

        for attempt in range(1, max_retries + 1):
            step_logs = []

            # === Step 1: Reasoning ===
            reasoning_prompt = self.prompts['reasoning']
            if feedback:
                reasoning_prompt += f"\n\n[System Feedback]: {feedback}\nPlease correct your reasoning."
            safe_r_prompt = self._safe_format(reasoning_prompt, context)
            r_start_ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            
            # 调用模型 (使用新的配置系统)
            r_res = call_llm_with_config(
                prompt_text=safe_r_prompt,
                agent_name=self.name,
                model_key=self.model_key,
                video_path=vid,
                logger=logger
            )
            
            reason_log = {
                "timestamp": r_start_ts,
                "agent": self.name,
                "step": "reasoning",
                "input": {
                    "prompt": safe_r_prompt,
                    "video_path": str(vid) if vid else "None", # 记录路径字符串而非列表对象
                    "context": {k:v for k, v in context.items()}
                },
                "output": r_res
            }
            self.history.append(reason_log)
            step_logs.append(reason_log)
            
            # [改进] 快速失败机制: 如果 Reasoning 报错，直接停止，不进行 Act
            if "ERROR" in r_res and "500" in r_res:
                return r_res

            # === Step 2: Act ===
            context['reasoning_result'] = r_res
            safe_a_prompt = self._safe_format(self.prompts['act'], context)
            a_start_ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            
            a_res = call_llm_with_config(
                prompt_text=safe_a_prompt,
                agent_name=self.name,
                model_key=self.model_key,
                video_path=vid,
                logger=logger
            )
            last_act = a_res
            
            act_log = {
                "timestamp": a_start_ts,
                "agent": self.name,
                "step": "act",
                "input": {
                    "prompt": safe_a_prompt,
                    "video_path": str(vid) if vid else "None",
                    "context": {k:v for k, v in context.items()}
                },
                "output": a_res
            }
            self.history.append(act_log)
            step_logs.append(act_log)

            # === Step 3: Self-Check（可选）===
            if not self.prompts.get('self_check'): # 使用 get 防止 key error
                return a_res

            context.update({'input_context': ctx_str, 'act_result': a_res})
            safe_c_prompt = self._safe_format(self.prompts['self_check'], context)
            c_start_ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            
            # [改进] 自查不传视频 (vid=None)，提高速度，减少超时风险
            c_res = call_llm_with_config(
                prompt_text=safe_c_prompt,
                agent_name=self.name,
                model_key=self.model_key,
                video_path=None,
                logger=logger
            )
            
            check_log = {
                "timestamp": c_start_ts,
                "agent": self.name,
                "step": "self_check",
                "input": {
                    "prompt": safe_c_prompt,
                    "video_path": "None (Optimization)", # 明确记录未传视频
                    "context": {k:v for k, v in context.items()}
                },
                "output": c_res
            }
            self.history.append(check_log)
            step_logs.append(check_log)

            status, feedback = self._parse_check(c_res)

            if status == "PASS":
                return a_res  # 成功

        return f"[WARNING: Max Retries Exceeded] {last_act}"