import pandas as pd
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

def check_date_coverage(df: pd.DataFrame, date_field: str, min_days: int = 5, max_gap_days: int = 7) -> Tuple[bool, str]:
    """检查日期覆盖情况
    
    Args:
        df: 数据框
        date_field: 日期字段名
        min_days: 最小要求天数
        max_gap_days: 最大允许的连续缺失天数
    
    Returns:
        (是否通过, 原因说明)
    """
    if date_field not in df.columns:
        return False, f"DATE_FIELD_MISSING_{date_field}"
    
    # 先处理日期列，移除空值
    df[date_field] = pd.to_datetime(df[date_field], errors='coerce')
    df = df[df[date_field].notna()]  # 移除NaT值
    
    if df.empty:
        return False, f"NO_VALID_DATES_IN_{date_field}"
    
    unique_days = df[date_field].dt.date.nunique()
    
    if unique_days < min_days:
        return False, f"NOT_ENOUGH_DAYS_{unique_days}_OF_{min_days}"
    
    # 检查日期断档情况
    dates = sorted(df[df[date_field].notna()][date_field].dt.date.unique())
    if not dates:
        return False, f"NO_VALID_DATES_AFTER_FILTERING_{date_field}"
        
    date_gaps = [(dates[i+1] - dates[i]).days - 1 for i in range(len(dates)-1)]
    
    if max(date_gaps, default=0) > max_gap_days:
        return False, f"DATE_GAP_TOO_LARGE_{max(date_gaps)}_DAYS"
        
    return True, "DATE_COVERAGE_OK"

def check_missing_ratio(df: pd.DataFrame, required_fields: List[str], threshold: float = 0.5) -> Tuple[bool, str]:
    """检查关键字段的缺失率
    
    Args:
        df: 数据框
        required_fields: 必需字段列表
        threshold: 缺失率阈值
    
    Returns:
        (是否通过, 原因说明)
    """
    for field in required_fields:
        if field not in df.columns:
            return False, f"REQUIRED_FIELD_MISSING_{field}"
        
        missing_ratio = df[field].isna().mean()
        if missing_ratio > threshold:
            return False, f"MISSING_RATIO_TOO_HIGH_{field}_{missing_ratio:.2f}"
    
    return True, "MISSING_CHECK_OK"

def check_data_feasibility(
    records: List[Dict],
    min_days: int = 5,
    required_fields: List[str] = None,
    date_field: Optional[str] = None,
    missing_threshold: float = 0.5,
    max_gap_days: int = 7
) -> Tuple[bool, str]:
    """数据可行性检查主函数
    
    Args:
        records: 原始数据记录列表
        min_days: 最小要求天数
        required_fields: 必需字段列表
        date_field: 日期字段名，如果为None则不检查日期
        missing_threshold: 缺失率阈值
        max_gap_days: 最大允许的连续缺失天数
    
    Returns:
        (是否可以继续处理, 原因说明)
    """
    if not records:
        return False, "RECORDS_EMPTY"

    df = pd.DataFrame(records)
    
    # 1. 基础检查
    if df.empty:
        return False, "DATAFRAME_EMPTY"
    
    # 2. 检查字段缺失情况
    if required_fields:
        missing_check_ok, missing_msg = check_missing_ratio(df, required_fields, missing_threshold)
        if not missing_check_ok:
            return False, missing_msg
    
    # 3. 如果指定了日期字段，则检查日期覆盖
    if date_field:
        date_check_ok, date_msg = check_date_coverage(df, date_field, min_days, max_gap_days)
        if not date_check_ok:
            return False, date_msg
    
    # 所有检查都通过
    return True, "OK" 