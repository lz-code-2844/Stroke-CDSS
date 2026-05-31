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
        Initialize Agent

        Args:
            prompt_file: Absolute path or filename relative to prompts directory
            model_key: Model key (optional, e.g. 'qwen_vl', 'gpt_oss')
                      If not specified, auto-selected based on agent name
        """
        self.model_key = model_key

        # Use absolute path directly, otherwise join with prompts directory
        if os.path.isabs(prompt_file):
            self.prompt_path = prompt_file
        else:
            self.prompt_path = os.path.join("prompts", prompt_file)

        self.name = os.path.basename(prompt_file).replace('.md', '')
        self.prompts = parse_agent_prompt(self.prompt_path)
        self.history = []  # Record each interaction (input/output/timestamp)

    def _safe_format(self, template, context):
        """
        Safe formatting that prevents KeyError
        """
        keys = re.findall(r'\{([a-zA-Z0-9_]+)\}', template)
        
        formatted_text = template
        for key in set(keys):
            val = str(context.get(key, "N/A"))
            formatted_text = formatted_text.replace(f"{{{key}}}", val)
        return formatted_text

    def _parse_check(self, text):
        """Parse Self-Check JSON"""
        try:
            clean_text = text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            return data.get("status", "FAIL").upper(), data.get("feedback", "")
        except:
            if "PASS" in text.upper(): return "PASS", ""
            return "FAIL", "JSON Parse Error"

    def run(self, video_paths, context, logger=None, max_retries=3):
        """
        Main method: Run agent and fully record input/output/timestamp for each call
        Returns the output from the act phase
        """
        # Determine input video paths
        vid = None
        
        # 1. Text-only Agents (no video needed)
        # [Improved] Explicitly include 'summary'
        if any(k in self.name for k in ['triage', 'time_calc', 'thrombolysis', 'indication', 'thrombectomy', 'summary']):
            vid = None 
            
        # 2. NCCT type
        elif 'hemorrhage' in self.name or 'ncct_imaging' in self.name: 
            vid = video_paths.get('ncct_path')
            
        # 3. CTA type
        elif 'aneurysm' in self.name or 'lvo' in self.name or 'cta_imaging' in self.name: 
            vid = video_paths.get('cta_path')
            
        # 4. CTP type
        elif 'ctp_imaging' in self.name:
            vid = video_paths.get('ctp_path')
            
        # 5. Legacy compatibility (fallback)
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
            
            # Call model (using new config system)
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
                    "video_path": str(vid) if vid else "None", # Record path string instead of list object
                    "context": {k:v for k, v in context.items()}
                },
                "output": r_res
            }
            self.history.append(reason_log)
            step_logs.append(reason_log)
            
            # [Improved] Fast-fail mechanism: If Reasoning errors, stop immediately without Act
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

            # === Step 3: Self-Check (optional) ===
            if not self.prompts.get('self_check'): # Use get to prevent KeyError
                return a_res

            context.update({'input_context': ctx_str, 'act_result': a_res})
            safe_c_prompt = self._safe_format(self.prompts['self_check'], context)
            c_start_ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            
            # [Improved] Self-check does not pass video (vid=None) to improve speed and reduce timeout risk
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
                    "video_path": "None (Optimization)", # Explicitly record no video passed
                    "context": {k:v for k, v in context.items()}
                },
                "output": c_res
            }
            self.history.append(check_log)
            step_logs.append(check_log)

            status, feedback = self._parse_check(c_res)

            if status == "PASS":
                return a_res  # Success

        return f"[WARNING: Max Retries Exceeded] {last_act}"