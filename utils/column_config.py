# utils/column_config.py

EXCEL_COL_MAPPING = {
    # --- 基础身份信息 ---
    "patient_id": "条码号",
    "admission_record": "入院记录修改_y", 
    
    # --- [关键修改] 映射到你新增的细分列 ---
    # 现在 NIHSS 专员将直接读取你提取好的评估文本
    "neuro_exam": "NIHSS评估内容",    
    
    # 事实抽取专员和总控签字专家将读取精简后的 Fact 内容
    "vitals": "入院记录修改_y",        
    "labs_and_meds": "入院记录修改_y", 
    "fact_content": "Fact内容",       # 供 14_director_agent 使用的新变量名
    
    # --- 视频路径 ---
    "ncct_path": "ncct_mp4",
    "cta_path": "cta_merge_mp4",
    "ctp_path": "ctp_merge_mp4",
    
    # --- Tool 工具数据 ---
    "tool_aspects": "ncct_tool",
    "ctp_tool_raw": "ctp_tool",
    "cta_tool_raw": "cta_tool",
    
    # --- 检查所见文本 ---
    "cta_tool_findings": "cta_检查所见",
    "ctp_tool_findings": "ctp_检查所见",
    
    # --- 辅助时间源 ---
    "time_calc_source": "主诉信息",

}