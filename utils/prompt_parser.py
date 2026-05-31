# 02_utils/prompt_parser.py

import re

def parse_agent_prompt(file_path):
    """Split a Markdown file containing REASONING, ACT, SELF_CHECK sections"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return {'reasoning': 'Error: Prompt file not found.', 'act': '', 'self_check': ''}
    
    # Split by delimiters using regex
    parts = {}
    
    # Match Reasoning section
    reasoning_match = re.search(r'# ===REASONING_PROMPT===\n(.*?)(?=# ===ACT_PROMPT===|$)', content, re.DOTALL)
    # Match Act section
    act_match = re.search(r'# ===ACT_PROMPT===\n(.*?)(?=# ===SELF_CHECK_PROMPT===|$)', content, re.DOTALL)
    # Match Self-Check section (to end of file)
    check_match = re.search(r'# ===SELF_CHECK_PROMPT===\n(.*?)$', content, re.DOTALL)
    
    # Assign values, return empty string instead of None on match failure
    parts['reasoning'] = reasoning_match.group(1).strip() if reasoning_match else ""
    parts['act'] = act_match.group(1).strip() if act_match else content # Fallback for act
    parts['self_check'] = check_match.group(1).strip() if check_match else ""
    
    return parts