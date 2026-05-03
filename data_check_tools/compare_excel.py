# -*- coding: utf-8 -*-
"""
Excel文件对比工具
对比两个Excel文件的每一个sheet，逐行逐列比较数据差异
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple


def compare_excel_files(old_file: str, new_file: str, output_file: str = None):
    """
    对比两个Excel文件
    
    Args:
        old_file: 旧文件路径
        new_file: 新文件路径
        output_file: 差异报告输出文件（可选）
    
    Returns:
        list: 差异列表
    """
    old_path = Path(old_file)
    new_path = Path(new_file)
    
    if not old_path.exists():
        print(f"[ERROR] 旧文件不存在: {old_path}")
        return []
    
    if not new_path.exists():
        print(f"[ERROR] 新文件不存在: {new_path}")
        return []
    
    print("=" * 80)
    print("Excel文件对比工具")
    print("=" * 80)
    print(f"\n旧文件: {old_path}")
    print(f"新文件: {new_path}\n")
    
    # 读取Excel文件的所有sheet
    old_sheets = pd.read_excel(old_path, sheet_name=None)
    new_sheets = pd.read_excel(new_path, sheet_name=None)
    
    # 获取共同的sheet名称
    common_sheets = set(old_sheets.keys()) & set(new_sheets.keys())
    
    if not common_sheets:
        print("[WARN] 没有共同的sheet名称")
        return []
    
    print(f"共同sheet数量: {len(common_sheets)}")
    print(f"Sheet列表: {', '.join(sorted(common_sheets))}\n")
    
    all_differences = []
    
    # 逐个sheet对比
    for sheet_name in sorted(common_sheets):
        print(f"\n{'='*80}")
        print(f"正在对比 Sheet: {sheet_name}")
        print(f"{'='*80}")
        
        old_df = old_sheets[sheet_name]
        new_df = new_sheets[sheet_name]
        
        print(f"旧数据: {old_df.shape[0]} 行 x {old_df.shape[1]} 列")
        print(f"新数据: {new_df.shape[0]} 行 x {new_df.shape[1]} 列")
        
        # 查找学校代码列
        school_code_col = find_school_code_column(old_df)
        
        if school_code_col is None:
            print(f"[WARN] 未找到学校代码列，跳过此sheet")
            continue
        
        print(f"学校代码列: '{school_code_col}'")
        
        # 对比数据
        differences = compare_sheet_data(
            sheet_name, 
            old_df, 
            new_df, 
            school_code_col
        )
        
        if differences:
            print(f"[INFO] 发现 {len(differences)} 处差异")
            all_differences.extend(differences)
        else:
            print(f"[OK] 无差异")
    
    # 输出总结
    print("\n" + "=" * 80)
    print("对比完成 - 总结")
    print("=" * 80)
    print(f"总差异数: {len(all_differences)}")
    
    if all_differences:
        # 按sheet分组统计
        sheet_stats = {}
        for diff in all_differences:
            sheet = diff['sheet_name']
            if sheet not in sheet_stats:
                sheet_stats[sheet] = 0
            sheet_stats[sheet] += 1
        
        print("\n各Sheet差异统计:")
        for sheet, count in sorted(sheet_stats.items()):
            print(f"  {sheet}: {count} 处差异")
        
        # 保存差异报告
        if output_file is None:
            output_file = old_path.parent / f"对比报告_{old_path.stem}_vs_{new_path.stem}.xlsx"
        
        save_differences_report(all_differences, output_file)
        
        # 显示前10个差异示例
        print(f"\n差异示例（前10个）:")
        for i, diff in enumerate(all_differences[:10], 1):
            print(f"\n{i}. Sheet: {diff['sheet_name']}")
            print(f"   学校代码: {diff['school_code']}")
            print(f"   列名: {diff['column_name']}")
            print(f"   旧值: {diff['old_value']}")
            print(f"   新值: {diff['new_value']}")
        
        if len(all_differences) > 10:
            print(f"\n... 还有 {len(all_differences) - 10} 个差异，详见报告文件")
    else:
        print("\n[OK] 两个文件完全一致！")
    
    return all_differences


def find_school_code_column(df: pd.DataFrame) -> str:
    """
    查找学校代码列
    
    Args:
        df: DataFrame
    
    Returns:
        学校代码列名，未找到返回None
    """
    # 常见的学校代码列名
    possible_names = [
        '学校代码', '代码', 'school_code', 'code', 
        '学校编号', '编号', 'ID', 'id'
    ]
    
    # 精确匹配
    for name in possible_names:
        if name in df.columns:
            return name
    
    # 模糊匹配（包含"代码"或"code"）
    for col in df.columns:
        col_lower = str(col).lower()
        if '代码' in str(col) or 'code' in col_lower:
            return col
    
    return None


def compare_sheet_data(
    sheet_name: str,
    old_df: pd.DataFrame,
    new_df: pd.DataFrame,
    school_code_col: str
) -> List[Dict]:
    """
    对比单个sheet的数据
    
    Args:
        sheet_name: sheet名称
        old_df: 旧数据
        new_df: 新数据
        school_code_col: 学校代码列名
    
    Returns:
        差异列表
    """
    differences = []
    
    # 将学校代码设为索引
    old_df_indexed = old_df.set_index(school_code_col)
    new_df_indexed = new_df.set_index(school_code_col)
    
    # 获取共同的学校代码
    common_codes = set(old_df_indexed.index) & set(new_df_indexed.index)
    
    # 获取共同的列
    common_cols = set(old_df_indexed.columns) & set(new_df_indexed.columns)
    
    print(f"共同学校代码数: {len(common_codes)}")
    print(f"共同列数: {len(common_cols)}")
    
    # 逐个学校代码对比
    for code in sorted(common_codes, key=lambda x: str(x)):
        old_row = old_df_indexed.loc[code]
        new_row = new_df_indexed.loc[code]
        
        # 逐列对比
        for col in sorted(common_cols, key=lambda x: str(x)):
            old_val = old_row[col]
            new_val = new_row[col]
            
            # 处理NaN值
            old_is_nan = pd.isna(old_val)
            new_is_nan = pd.isna(new_val)
            
            if old_is_nan and new_is_nan:
                continue  # 都是空值，不算差异
            
            if old_is_nan != new_is_nan:
                # 一个为空，一个不为空
                differences.append({
                    'sheet_name': sheet_name,
                    'school_code': code,
                    'column_name': col,
                    'old_value': '' if old_is_nan else old_val,
                    'new_value': '' if new_is_nan else new_val
                })
            elif old_val != new_val:
                # 值不同
                differences.append({
                    'sheet_name': sheet_name,
                    'school_code': code,
                    'column_name': col,
                    'old_value': old_val,
                    'new_value': new_val
                })
    
    return differences


def save_differences_report(differences: List[Dict], output_file: Path):
    """
    保存差异报告到Excel
    
    Args:
        differences: 差异列表
        output_file: 输出文件路径
    """
    if not differences:
        print("\n[INFO] 无差异，不生成报告文件")
        return
    
    # 转换为DataFrame
    df = pd.DataFrame(differences)
    
    # 重新排列列顺序
    column_order = ['sheet_name', 'school_code', 'column_name', 'old_value', 'new_value']
    df = df[column_order]
    
    # 设置中文列名
    df.columns = ['Sheet名称', '学校代码', '列名', '旧值', '新值']
    
    # 保存到Excel
    df.to_excel(output_file, index=False, engine='openpyxl')
    
    print(f"\n[OK] 差异报告已保存: {output_file}")
    print(f"   共 {len(df)} 条差异记录")


if __name__ == "__main__":
    # 文件路径
    old_file = "e:/Python/gz_zhongkao_advisor/data/2023 年广州市普通高中名额分配结果.xlsx"
    new_file = "e:/Python/gz_zhongkao_advisor/data/2023 年广州市普通高中名额分配结果 - 新.xlsx"
    
    # 执行对比
    differences = compare_excel_files(old_file, new_file)
