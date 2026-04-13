# 02_utils/data_loader.py

import pandas as pd
import os
from .column_config import EXCEL_COL_MAPPING

def load_experiment_data(excel_path):
    """
    读取Excel文件，并使用 column_config 进行列名映射。
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")
    
    df = pd.read_excel(excel_path)
    
    # 创建映射字典：{Excel原始列名: 代码变量名}
    # 注意：EXCEL_COL_MAPPING 中可能有多个 code_var_name 对应同一个 excel_col_name
    # 例如 "admission_record" 和 "time_calc_source" 都对应 "入院记录修改"
    # 这种情况下，我们需要复制该列而不是简单重命名
    
    rename_cols = {}
    duplicate_cols = {}  # 用于记录需要复制的列 {code_var_name: excel_col_name}
    
    # 记录已经被映射的 Excel 列名
    mapped_excel_cols = set()
    
    for code_var_name, excel_col_name in EXCEL_COL_MAPPING.items():
        if excel_col_name in df.columns:
            if excel_col_name in mapped_excel_cols:
                # 该 Excel 列已经被映射过，需要复制而不是重命名
                duplicate_cols[code_var_name] = excel_col_name
            else:
                # 首次映射，使用 rename
                rename_cols[excel_col_name] = code_var_name
                mapped_excel_cols.add(excel_col_name)
        else:
            # 列不存在，打印警告
            print(f"[WARNING] Column '{excel_col_name}' for '{code_var_name}' not found in Excel.")
    
    # 先执行 rename
    df.rename(columns=rename_cols, inplace=True)
    
    # 再处理需要复制的列（在 rename 之后，需要使用已重命名后的列名）
    for code_var_name, excel_col_name in duplicate_cols.items():
        # 找到该 excel_col_name 被重命名成了什么
        renamed_col = rename_cols.get(excel_col_name)
        if renamed_col and renamed_col in df.columns:
            df[code_var_name] = df[renamed_col]
        elif excel_col_name in df.columns:
            df[code_var_name] = df[excel_col_name]
    
    # 校验关键路径列是否存在
    required_path_cols = ['ncct_path', 'cta_path', 'ctp_path']
    for col in required_path_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required path column: '{col}'. Please check your Excel headers and update column_config.py.")
            
    df = df.fillna("")
    return df