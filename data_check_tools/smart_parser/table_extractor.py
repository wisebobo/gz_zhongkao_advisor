# -*- coding: utf-8 -*-
"""
表格结构提取器
从检测到的表格区域提取结构化数据
使用坐标-based方法重构表格结构
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


class TableStructureExtractor:
    """
    表格结构提取器
    
    功能：
    1. 从表格区域的OCR文本块重构表格结构
    2. 按Y坐标分组（行），按X坐标排序（列）
    3. 处理单元格内换行（垂直proximity合并）
    4. 对齐列数（最大列数填充）
    5. 输出DataFrame格式
    """
    
    def __init__(
        self,
        y_tolerance: float = 15,      # Y坐标容差（同一行）
        x_gap_threshold: float = 20,   # X坐标间隙阈值（判断是否同列）
        vertical_merge_threshold: float = 20  # 垂直合并阈值（换行检测）
    ):
        """
        初始化表格提取器
        
        Args:
            y_tolerance: Y坐标容差，小于此值视为同一行
            x_gap_threshold: X坐标间隙，用于判断列边界
            vertical_merge_threshold: 垂直距离阈值，用于检测单元格换行
        """
        self.y_tolerance = y_tolerance
        self.x_gap_threshold = x_gap_threshold
        self.vertical_merge_threshold = vertical_merge_threshold
    
    def extract_table_structure(
        self, 
        table_element: Dict,
        all_elements: List[Dict]
    ) -> Optional[pd.DataFrame]:
        """
        从表格元素提取结构化数据
        
        Args:
            table_element: 表格元素（来自ElementClassifier）
            all_elements: 页面所有元素列表
            
        Returns:
            DataFrame: 结构化表格数据，失败返回None
        """
        if not table_element or 'bbox' not in table_element:
            return None
        
        table_bbox = table_element['bbox']
        
        # 步骤1: 提取表格区域内的所有文本元素
        text_elements = self._extract_text_in_table_region(table_bbox, all_elements)
        
        if not text_elements:
            return None
        
        # 步骤2: 检测并合并垂直相邻的单元格（换行）
        merged_elements = self._merge_vertical_cells(text_elements)
        
        # 步骤3: 按Y坐标分组（行）
        row_groups = self._group_by_rows(merged_elements)
        
        if not row_groups:
            return None
        
        # 步骤4: 每行内按X坐标排序（列）
        sorted_rows = []
        for y_key in sorted(row_groups.keys()):
            row_elements = row_groups[y_key]
            sorted_row = sorted(row_elements, key=lambda x: x['bbox'][0])
            sorted_rows.append(sorted_row)
        
        # 步骤5: 构建二维表格
        table_data = self._build_table_matrix(sorted_rows)
        
        if not table_data:
            return None
        
        # 步骤6: 转换为DataFrame
        df = pd.DataFrame(table_data)
        
        # 清理空值
        df = df.fillna('')
        
        return df
    
    def _extract_text_in_table_region(
        self, 
        table_bbox: List[float],
        all_elements: List[Dict]
    ) -> List[Dict]:
        """
        提取表格区域内的所有文本元素
        
        Args:
            table_bbox: 表格边界框 [x1, y1, x2, y2]
            all_elements: 所有元素列表
            
        Returns:
            表格区域内的文本元素列表
        """
        x1, y1, x2, y2 = table_bbox
        
        text_elements = []
        for elem in all_elements:
            # 只处理text类型
            if elem.get('type') not in ['text', 'paragraph']:
                continue
            
            bbox = elem.get('bbox', [])
            if not bbox or len(bbox) != 4:
                continue
            
            elem_x1, elem_y1, elem_x2, elem_y2 = bbox
            
            # 判断元素是否在表格区域内（允许一定边距）
            margin = 10
            if (elem_x1 >= x1 - margin and elem_x2 <= x2 + margin and
                elem_y1 >= y1 - margin and elem_y2 <= y2 + margin):
                
                text = elem.get('res', {}).get('text', '').strip()
                if text:  # 非空文本
                    text_elements.append(elem)
        
        return text_elements
    
    def _merge_vertical_cells(self, elements: List[Dict]) -> List[Dict]:
        """
        合并垂直相邻的单元格（处理单元格内换行）
        
        Args:
            elements: 文本元素列表
            
        Returns:
            合并后的元素列表
        """
        if not elements:
            return []
        
        # 按Y坐标排序
        sorted_elems = sorted(elements, key=lambda x: x['bbox'][1])
        
        merged = []
        skip_indices = set()
        
        for i in range(len(sorted_elems)):
            if i in skip_indices:
                continue
            
            current = sorted_elems[i]
            current_text = current['res'].get('text', '')
            current_bbox = current['bbox']
            
            # 检查是否有后续元素需要合并
            texts_to_merge = [current_text]
            final_bbox = list(current_bbox)
            
            for j in range(i + 1, len(sorted_elems)):
                if j in skip_indices:
                    continue
                
                next_elem = sorted_elems[j]
                next_bbox = next_elem['bbox']
                
                # 计算垂直距离
                vertical_gap = next_bbox[1] - current_bbox[3]
                
                # 检查X坐标重叠
                x_overlap = self._calculate_x_overlap(current_bbox, next_bbox)
                
                # 如果垂直距离近且X坐标重叠，可能是同一单元格的换行
                if (vertical_gap > 0 and vertical_gap < self.vertical_merge_threshold and
                    x_overlap > 0.5):
                    
                    next_text = next_elem['res'].get('text', '')
                    texts_to_merge.append(next_text)
                    
                    # 更新包围盒
                    final_bbox[2] = max(final_bbox[2], next_bbox[2])
                    final_bbox[3] = next_bbox[3]
                    
                    skip_indices.add(j)
                else:
                    break
            
            # 创建合并后的元素
            merged_text = '\n'.join(texts_to_merge)
            merged_elem = {
                'type': 'text',
                'bbox': final_bbox,
                'res': {
                    'text': merged_text,
                    'html': ''
                },
                'confidence': current.get('confidence', 1.0)
            }
            merged.append(merged_elem)
        
        return merged
    
    def _calculate_x_overlap(self, bbox1: List[float], bbox2: List[float]) -> float:
        """
        计算两个边界框的X坐标重叠度
        
        Args:
            bbox1: [x1, y1, x2, y2]
            bbox2: [x1, y1, x2, y2]
            
        Returns:
            重叠度 (0-1)
        """
        x1_start, _, x1_end, _ = bbox1
        x2_start, _, x2_end, _ = bbox2
        
        # 计算重叠区间
        overlap_start = max(x1_start, x2_start)
        overlap_end = min(x1_end, x2_end)
        
        if overlap_start >= overlap_end:
            return 0.0
        
        overlap_width = overlap_end - overlap_start
        
        # 计算较小的宽度
        width1 = x1_end - x1_start
        width2 = x2_end - x2_start
        min_width = min(width1, width2)
        
        if min_width == 0:
            return 0.0
        
        return overlap_width / min_width
    
    def _group_by_rows(self, elements: List[Dict]) -> Dict[float, List[Dict]]:
        """
        按Y坐标将元素分组为行
        
        Args:
            elements: 元素列表
            
        Returns:
            {y_center: [elements]}
        """
        if not elements:
            return {}
        
        # 计算每个元素的中心Y坐标
        elems_with_y = []
        for elem in elements:
            bbox = elem['bbox']
            y_center = (bbox[1] + bbox[3]) / 2
            elems_with_y.append((y_center, elem))
        
        # 按Y坐标排序
        elems_with_y.sort(key=lambda x: x[0])
        
        # 分组
        groups = defaultdict(list)
        current_group_y = None
        
        for y_center, elem in elems_with_y:
            if current_group_y is None or abs(y_center - current_group_y) > self.y_tolerance:
                # 新组
                current_group_y = y_center
            
            groups[current_group_y].append(elem)
        
        return dict(groups)
    
    def _build_table_matrix(self, sorted_rows: List[List[Dict]]) -> List[List[str]]:
        """
        构建二维表格矩阵
        
        Args:
            sorted_rows: 已排序的行列表，每行是元素列表
            
        Returns:
            二维字符串矩阵
        """
        if not sorted_rows:
            return []
        
        # 找出最大列数
        max_cols = max(len(row) for row in sorted_rows)
        
        if max_cols == 0:
            return []
        
        # 构建矩阵
        matrix = []
        for row_elements in sorted_rows:
            row_texts = [elem['res'].get('text', '') for elem in row_elements]
            
            # 填充到最大列数
            while len(row_texts) < max_cols:
                row_texts.append('')
            
            matrix.append(row_texts)
        
        return matrix
    
    def detect_merged_cells(self, df: pd.DataFrame) -> List[Tuple[int, int, int, int]]:
        """
        检测DataFrame中的合并单元格（简单启发式）
        
        Args:
            df: DataFrame
            
        Returns:
            [(row, col, rowspan, colspan), ...]
        """
        # 简化版本：暂时不实现复杂的合并单元格检测
        # 可以在后续版本中通过分析空值模式来实现
        return []
    
    def html_to_dataframe(self, html_content: str) -> Optional[pd.DataFrame]:
        """
        将HTML表格转换为DataFrame（备用方法）
        
        Args:
            html_content: HTML字符串
            
        Returns:
            DataFrame或None
        """
        try:
            dfs = pd.read_html(html_content)
            if dfs:
                df = dfs[0]
                df = df.fillna('')
                return df
        except Exception as e:
            print(f"[WARN] HTML解析失败: {e}")
        
        return None
    
    def __repr__(self) -> str:
        return (
            f"TableStructureExtractor("
            f"y_tol={self.y_tolerance}, "
            f"x_gap={self.x_gap_threshold}, "
            f"v_merge={self.vertical_merge_threshold})"
        )


def main():
    """测试函数"""
    print("=" * 80)
    print("TableStructureExtractor 测试")
    print("=" * 80)
    
    # 创建提取器
    extractor = TableStructureExtractor()
    
    # 模拟测试数据
    table_element = {
        'type': 'table',
        'bbox': [100, 200, 800, 600],
        'res': {'text': '', 'html': ''},
        'confidence': 1.0
    }
    
    # 模拟表格内的文本元素
    all_elements = [
        # 第1行
        {'type': 'text', 'bbox': [110, 210, 200, 240], 'res': {'text': '序号', 'html': ''}, 'confidence': 1.0},
        {'type': 'text', 'bbox': [220, 210, 400, 240], 'res': {'text': '学校名称', 'html': ''}, 'confidence': 1.0},
        {'type': 'text', 'bbox': [420, 210, 500, 240], 'res': {'text': '名额', 'html': ''}, 'confidence': 1.0},
        
        # 第2行
        {'type': 'text', 'bbox': [110, 260, 200, 290], 'res': {'text': '1', 'html': ''}, 'confidence': 1.0},
        {'type': 'text', 'bbox': [220, 260, 400, 290], 'res': {'text': '广州市第一中学', 'html': ''}, 'confidence': 1.0},
        {'type': 'text', 'bbox': [420, 260, 500, 290], 'res': {'text': '100', 'html': ''}, 'confidence': 1.0},
        
        # 第3行
        {'type': 'text', 'bbox': [110, 310, 200, 340], 'res': {'text': '2', 'html': ''}, 'confidence': 1.0},
        {'type': 'text', 'bbox': [220, 310, 400, 340], 'res': {'text': '广州市第二中学', 'html': ''}, 'confidence': 1.0},
        {'type': 'text', 'bbox': [420, 310, 500, 340], 'res': {'text': '150', 'html': ''}, 'confidence': 1.0},
    ]
    
    print(f"\n输入: {len(all_elements)} 个文本元素")
    
    # 提取表格结构
    df = extractor.extract_table_structure(table_element, all_elements)
    
    if df is not None:
        print(f"\n提取成功！")
        print(f"表格尺寸: {df.shape[0]}行 x {df.shape[1]}列")
        print(f"\n表格内容:")
        print(df.to_string(index=False))
    else:
        print("\n[ERROR] 提取失败")
    
    print("\n" + "=" * 80)
    print("[OK] 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
