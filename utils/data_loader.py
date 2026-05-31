# 02_utils/data_loader.py

import pandas as pd
import os
from .column_config import EXCEL_COL_MAPPING

def load_experiment_data(excel_path):
    """
    Read Excel file and map column names using column_config.
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")
    
    df = pd.read_excel(excel_path)
    
    # Create mapping dict: {Excel original column name: code variable name}
    # Note: EXCEL_COL_MAPPING may have multiple code_var_name mapping to the same excel_col_name
    # e.g. "admission_record" and "time_calc_source" both map to the same column
    # In this case, we need to copy the column instead of simply renaming
    
    rename_cols = {}
    duplicate_cols = {}  # Columns that need copying {code_var_name: excel_col_name}
    
    # Track already-mapped Excel column names
    mapped_excel_cols = set()
    
    for code_var_name, excel_col_name in EXCEL_COL_MAPPING.items():
        if excel_col_name in df.columns:
            if excel_col_name in mapped_excel_cols:
                # This Excel column was already mapped, copy instead of rename
                duplicate_cols[code_var_name] = excel_col_name
            else:
                # First mapping, use rename
                rename_cols[excel_col_name] = code_var_name
                mapped_excel_cols.add(excel_col_name)
        else:
            # Column not found, print warning
            print(f"[WARNING] Column '{excel_col_name}' for '{code_var_name}' not found in Excel.")
    
    # Execute rename first
    df.rename(columns=rename_cols, inplace=True)
    
    # Handle columns that need copying (after rename, use renamed column name)
    for code_var_name, excel_col_name in duplicate_cols.items():
        # Find what excel_col_name was renamed to
        renamed_col = rename_cols.get(excel_col_name)
        if renamed_col and renamed_col in df.columns:
            df[code_var_name] = df[renamed_col]
        elif excel_col_name in df.columns:
            df[code_var_name] = df[excel_col_name]
    
    # Verify critical path columns exist
    required_path_cols = ['ncct_path', 'cta_path', 'ctp_path']
    for col in required_path_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required path column: '{col}'. Please check your Excel headers and update column_config.py.")
            
    df = df.fillna("")
    return df