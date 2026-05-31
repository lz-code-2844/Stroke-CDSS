# utils/column_config.py

EXCEL_COL_MAPPING = {
    # --- Basic Identity Info ---
    "patient_id": "barcode_no",
    "admission_record": "admission_record_modified_y",
    
    # --- [Key Change] Map to new specialized columns ---
    # Now NIHSS Agent reads pre-extracted assessment text directly
    "neuro_exam": "NIHSS_assessment_content",
    
    # Fact extractor and Director agents read condensed Fact content
    "vitals": "admission_record_modified_y",
    "labs_and_meds": "admission_record_modified_y",
    "fact_content": "Fact_content",       # New variable for 14_director_agent
    
    # --- Video Paths ---
    "ncct_path": "ncct_mp4",
    "cta_path": "cta_merge_mp4",
    "ctp_path": "ctp_merge_mp4",
    
    # --- Tool Data ---
    "tool_aspects": "ncct_tool",
    "ctp_tool_raw": "ctp_tool",
    "cta_tool_raw": "cta_tool",
    
    # --- Exam Findings Text ---
    "cta_tool_findings": "cta_findings",
    "ctp_tool_findings": "ctp_findings",
    
    # --- Auxiliary Time Source ---
    "time_calc_source": "chief_complaint_info",

}