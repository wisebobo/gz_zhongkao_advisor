# -*- coding: utf-8 -*-
"""
元素分类器
对 PP-Structure 检测到的元素进行分类、过滤和组织
"""

from typing import List, Dict


class ElementClassifier:
    """
    元素分类器
    
    功能：
    1. 按类型分组元素（tables/articles/titles/figures）
    2. 过滤低质量元素
    3. 合并相邻的同类型元素（如连续段落）
    4. 检测并标记页眉页脚
    """
    
    def __init__(self, confidence_threshold: float = 0.5):
        """
        初始化分类器
        
        Args:
            confidence_threshold: 置信度阈值，低于此值的元素将被过滤
        """
        self.confidence_threshold = confidence_threshold
    
    def classify_elements(self, raw_elements: List[Dict]) -> Dict[str, List]:
        """
        分类元素
        
        Args:
            raw_elements: DocumentLayoutAnalyzer 输出的原始元素列表
            
        Returns:
            分类后的元素字典：
            {
                'tables': [...],      # 表格元素
                'articles': [...],    # 文章段落
                'titles': [...],      # 标题
                'figures': [...],     # 图片
                'headers': [...],     # 页眉
                'footers': [...]      # 页脚
            }
        """
        classified = {
            'tables': [],
            'articles': [],
            'titles': [],
            'figures': [],
            'headers': [],
            'footers': []
        }
        
        for elem in raw_elements:
            # 1. 置信度过滤（PaddleOCR 2.7.3默认confidence=1.0）
            if elem.get('confidence', 1.0) < self.confidence_threshold:
                continue
            
            # 2. 类型映射和分类
            elem_type = elem.get('type', 'text')
            
            if elem_type == 'table':
                classified['tables'].append(elem)
            
            elif elem_type in ['text', 'paragraph']:
                # 判断是否为页眉/页脚
                if self._is_header_or_footer(elem):
                    if 'header' in elem.get('type', '').lower() or self._is_likely_header(elem):
                        classified['headers'].append(elem)
                    else:
                        classified['footers'].append(elem)
                else:
                    classified['articles'].append(elem)
            
            elif elem_type == 'title':
                classified['titles'].append(elem)
            
            elif elem_type in ['figure', 'image']:
                classified['figures'].append(elem)
            
            elif elem_type == 'header':
                classified['headers'].append(elem)
            
            elif elem_type == 'footer':
                classified['footers'].append(elem)
            
            else:
                # 未知类型，归类为文章
                classified['articles'].append(elem)
        
        return classified
    
    def _is_header_or_footer(self, elem: Dict) -> bool:
        """
        判断元素是否可能是页眉或页脚
        
        Args:
            elem: 元素字典
            
        Returns:
            bool: 是否为页眉/页脚
        """
        bbox = elem.get('bbox', [])
        if not bbox or len(bbox) != 4:
            return False
        
        # 简单的启发式规则：
        # - 页眉：Y坐标很小（页面顶部）
        # - 页脚：Y坐标很大（页面底部）
        y_top = bbox[1]
        y_bottom = bbox[3]
        
        # 假设A4纸300DPI约为3500像素高度
        page_height_estimate = 3500
        
        # 页眉：顶部5%区域
        if y_top < page_height_estimate * 0.05:
            return True
        
        # 页脚：底部5%区域
        if y_bottom > page_height_estimate * 0.95:
            return True
        
        return False
    
    def _is_likely_header(self, elem: Dict) -> bool:
        """
        判断文本是否可能是页眉
        
        Args:
            elem: 元素字典
            
        Returns:
            bool: 是否可能是页眉
        """
        text = elem.get('res', {}).get('text', '')
        
        # 页眉常见模式
        header_patterns = [
            '第', '页', '共',  # "第X页共Y页"
            '2023', '2024', '2025',  # 年份
            ':', '-',  # 时间戳格式
        ]
        
        text_lower = text.lower()
        for pattern in header_patterns:
            if pattern in text:
                return True
        
        return False
    
    def merge_adjacent_articles(self, articles: List[Dict], y_tolerance: float = 20) -> List[Dict]:
        """
        合并相邻的文章段落
        
        Args:
            articles: 文章元素列表
            y_tolerance: Y坐标容差（像素）
            
        Returns:
            合并后的文章列表
        """
        if not articles:
            return []
        
        # 按Y坐标排序
        sorted_articles = sorted(articles, key=lambda x: x['bbox'][1] if x.get('bbox') else 0)
        
        merged = []
        current_group = [sorted_articles[0]]
        
        for i in range(1, len(sorted_articles)):
            prev_elem = current_group[-1]
            curr_elem = sorted_articles[i]
            
            # 计算Y坐标距离
            prev_y_bottom = prev_elem['bbox'][3] if prev_elem.get('bbox') else 0
            curr_y_top = curr_elem['bbox'][1] if curr_elem.get('bbox') else 0
            
            y_distance = curr_y_top - prev_y_bottom
            
            # 如果距离很近，合并到同一组
            if y_distance < y_tolerance:
                current_group.append(curr_elem)
            else:
                # 保存当前组合并结果
                merged_elem = self._merge_article_group(current_group)
                merged.append(merged_elem)
                
                # 开始新组
                current_group = [curr_elem]
        
        # 处理最后一组
        if current_group:
            merged_elem = self._merge_article_group(current_group)
            merged.append(merged_elem)
        
        return merged
    
    def _merge_article_group(self, group: List[Dict]) -> Dict:
        """
        合并一组文章段落为一个元素
        
        Args:
            group: 文章元素组
            
        Returns:
            合并后的元素
        """
        if len(group) == 1:
            return group[0]
        
        # 合并文本
        texts = [elem.get('res', {}).get('text', '') for elem in group]
        merged_text = '\n'.join(texts)
        
        # 使用第一个元素的边界框（或计算包围盒）
        first_elem = group[0]
        merged_bbox = first_elem.get('bbox', [0, 0, 0, 0])
        
        # 如果有多个元素，计算包围盒
        if len(group) > 1:
            all_bboxes = [elem.get('bbox', [0, 0, 0, 0]) for elem in group]
            x_min = min(b[0] for b in all_bboxes)
            y_min = min(b[1] for b in all_bboxes)
            x_max = max(b[2] for b in all_bboxes)
            y_max = max(b[3] for b in all_bboxes)
            merged_bbox = [x_min, y_min, x_max, y_max]
        
        merged_elem = {
            'type': 'text',
            'bbox': merged_bbox,
            'res': {
                'text': merged_text,
                'html': ''
            },
            'confidence': 1.0
        }
        
        return merged_elem
    
    def filter_empty_elements(self, elements: List[Dict]) -> List[Dict]:
        """
        过滤空元素
        
        Args:
            elements: 元素列表
            
        Returns:
            非空元素列表
        """
        filtered = []
        for elem in elements:
            text = elem.get('res', {}).get('text', '')
            if text.strip():  # 非空文本
                filtered.append(elem)
        
        return filtered
    
    def get_classification_summary(self, classified: Dict[str, List]) -> Dict[str, int]:
        """
        获取分类统计摘要
        
        Args:
            classified: 分类后的元素字典
            
        Returns:
            统计字典
        """
        summary = {}
        for elem_type, elems in classified.items():
            if elems:  # 只包含非空类型
                summary[elem_type] = len(elems)
        
        return summary
    
    def __repr__(self) -> str:
        return f"ElementClassifier(threshold={self.confidence_threshold})"


def main():
    """测试函数"""
    print("=" * 80)
    print("ElementClassifier 测试")
    print("=" * 80)
    
    # 创建分类器
    classifier = ElementClassifier(confidence_threshold=0.5)
    
    # 模拟一些测试数据
    test_elements = [
        {
            'type': 'table',
            'bbox': [100, 200, 800, 600],
            'res': {'text': '', 'html': '<table>...</table>'},
            'confidence': 1.0
        },
        {
            'type': 'text',
            'bbox': [100, 100, 500, 150],
            'res': {'text': '2023年广州市普通高中名额分配结果', 'html': ''},
            'confidence': 1.0
        },
        {
            'type': 'text',
            'bbox': [100, 700, 300, 720],
            'res': {'text': '第1页共2页', 'html': ''},
            'confidence': 1.0
        },
        {
            'type': 'text',
            'bbox': [100, 300, 600, 350],
            'res': {'text': '根据市教育局规定...', 'html': ''},
            'confidence': 1.0
        },
    ]
    
    print(f"\n输入: {len(test_elements)} 个原始元素")
    
    # 分类
    classified = classifier.classify_elements(test_elements)
    
    # 打印分类结果
    print("\n分类结果:")
    summary = classifier.get_classification_summary(classified)
    for elem_type, count in summary.items():
        print(f"  {elem_type}: {count} 个")
    
    # 打印详细信息
    print("\n详细分类:")
    for elem_type, elems in classified.items():
        if elems:
            print(f"\n{elem_type.upper()} ({len(elems)}个):")
            for i, elem in enumerate(elems, 1):
                text = elem['res'].get('text', '')[:50]
                print(f"  {i}. {text}...")
    
    print("\n" + "=" * 80)
    print("[OK] 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
