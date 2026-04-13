# 02_utils/prompt_parser.py

import re

def parse_agent_prompt(file_path):
    """将包含 REASONING, ACT, SELF_CHECK 的 Markdown 文件拆分"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return {'reasoning': 'Error: Prompt file not found.', 'act': '', 'self_check': ''}
    
    # 使用正则表达式按分隔符切分
    parts = {}
    
    # 匹配 Reasoning 部分
    reasoning_match = re.search(r'# ===REASONING_PROMPT===\n(.*?)(?=# ===ACT_PROMPT===|$)', content, re.DOTALL)
    # 匹配 Act 部分
    act_match = re.search(r'# ===ACT_PROMPT===\n(.*?)(?=# ===SELF_CHECK_PROMPT===|$)', content, re.DOTALL)
    # 匹配 Self-Check 部分 (到文件末尾)
    check_match = re.search(r'# ===SELF_CHECK_PROMPT===\n(.*?)$', content, re.DOTALL)
    
    # 赋值，确保匹配失败时返回空字符串而不是 None
    parts['reasoning'] = reasoning_match.group(1).strip() if reasoning_match else ""
    parts['act'] = act_match.group(1).strip() if act_match else content # Fallback for act
    parts['self_check'] = check_match.group(1).strip() if check_match else ""
    
    return parts