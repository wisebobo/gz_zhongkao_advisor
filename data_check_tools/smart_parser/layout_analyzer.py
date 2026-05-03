# -*- coding: utf-8 -*-
"""
文档版面分析器
使用 PaddleOCR PP-Structure 进行页面元素检测和分类
"""

import os
# 禁用 OneDNN/MKLDNN 以避免兼容性问题（必须在导入 paddle 之前设置）
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['MKLDNN_VERBOSE'] = '0'
os.environ['FLAGS_cudnn_exhaustive_search'] = '0'
os.environ['CPU_NUM'] = '1'

import numpy as np
from typing import List, Dict, Optional
from pathlib import Path

try:
    from paddleocr import PPStructure
except ImportError:
    raise ImportError(
        "未安装 PaddleOCR，请运行:\n"
        "  pip install paddlepaddle==2.6.2 paddleocr==2.10.0"
    )


class DocumentLayoutAnalyzer:
    """
    文档版面分析器
    
    使用 PP-Structure 自动检测 PDF 页面中的不同元素类型：
    - text: 文章段落
    - title: 标题
    - table: 表格
    - figure: 图片
    - header/footer: 页眉页脚
    
    每个元素包含边界框坐标、识别文本和置信度信息。
    """
    
    def __init__(
        self, 
        use_gpu: bool = False, 
        lang: str = 'ch',
        confidence_threshold: float = 0.6
    ):
        """
        初始化版面分析器
        
        Args:
            use_gpu: 是否使用 GPU 加速（默认 False）
            lang: 识别语言 ('ch'中文, 'en'英文, 'multi'多语言)
            confidence_threshold: 置信度阈值，低于此值的元素将被过滤
        """
        print("[INIT] 正在初始化 PP-Structure 版面分析器...")
        
        try:
            self.engine = PPStructure(
                show_log=False,
                recovery=True,      # 启用recovery以获取完整结果
                lang=lang,
                use_gpu=use_gpu,
                table=False,        # 禁用内置表格识别（避免兼容性问题）
                ocr=True            # 启用 OCR
            )
            print("[OK] PP-Structure 初始化完成")
            
        except Exception as e:
            print(f"[ERROR] PP-Structure 初始化失败: {e}")
            raise
        
        self.confidence_threshold = confidence_threshold
        self.use_gpu = use_gpu
        self.lang = lang
    
    def analyze_page(self, image: np.ndarray) -> List[Dict]:
        """
        分析单页布局
        
        Args:
            image: RGB 图像数组，形状为 (H, W, 3)，值范围 0-255
            
        Returns:
            elements: 元素列表，每个元素包含：
                {
                    'type': 'text' | 'title' | 'table' | 'figure',
                    'bbox': [x1, y1, x2, y2],  # 边界框坐标
                    'res': {
                        'text': str,           # 识别的文本内容
                        'html': str            # 表格 HTML（仅 table 类型有）
                    },
                    'confidence': float        # 置信度 (0-1)
                }
        
        Example:
            >>> analyzer = DocumentLayoutAnalyzer()
            >>> import fitz
            >>> doc = fitz.open("test.pdf")
            >>> page = doc[0]
            >>> pix = page.get_pixmap()
            >>> img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)
            >>> elements = analyzer.analyze_page(img)
            >>> print(f"检测到 {len(elements)} 个元素")
        """
        if image is None or image.size == 0:
            raise ValueError("输入图像为空")
        
        if len(image.shape) != 3 or image.shape[2] != 3:
            raise ValueError(f"图像格式错误，期望 (H, W, 3)，实际 {image.shape}")
        
        try:
            # 调用 PP-Structure 进行分析
            result = self.engine(image)
            
            # 后处理结果
            elements = []
            for item in result:
                # 提取元素信息
                element = self._process_element(item)
                
                # 过滤低置信度元素
                if element['confidence'] >= self.confidence_threshold:
                    elements.append(element)
            
            return elements
            
        except Exception as e:
            print(f"[ERROR] 页面分析失败: {e}")
            raise
    
    def _process_element(self, item: Dict) -> Dict:
        """
        处理单个元素，标准化格式
        
        Args:
            item: PP-Structure 原始输出
            
        Returns:
            标准化后的元素字典
        """
        # 提取类型
        elem_type = item.get('type', 'text')
        
        # 映射类型名称（统一格式）
        type_mapping = {
            'text': 'text',
            'paragraph': 'text',
            'title': 'title',
            'table': 'table',
            'figure': 'figure',
            'image': 'figure',
            'header': 'header',
            'footer': 'footer'
        }
        mapped_type = type_mapping.get(elem_type, 'text')
        
        # 提取边界框
        bbox = item.get('bbox', [])
        if not bbox or len(bbox) != 4:
            # 如果没有 bbox，尝试从其他字段获取
            bbox = item.get('box', [0, 0, 0, 0])
        
        # 提取识别结果
        res = item.get('res', {})
        
        # 提取文本内容
        text = ''
        html = ''
        
        if isinstance(res, dict):
            text = res.get('text', '')
            html = res.get('html', '')
        elif isinstance(res, list):
            # 某些情况下 res 是列表
            text_parts = []
            for r in res:
                if isinstance(r, dict):
                    text_parts.append(r.get('text', ''))
            text = '\n'.join(text_parts)
        
        # 提取置信度
        confidence = item.get('score', 1.0)  # PaddleOCR 2.7.3可能没有score字段，默认1.0
        if confidence == 0.0 and isinstance(res, dict):
            confidence = res.get('score', 1.0)
        
        # 构建标准化元素
        element = {
            'type': mapped_type,
            'bbox': bbox,
            'res': {
                'text': text,
                'html': html
            },
            'confidence': confidence
        }
        
        return element
    
    def get_element_summary(self, elements: List[Dict]) -> Dict[str, int]:
        """
        获取元素类型统计摘要
        
        Args:
            elements: 元素列表
            
        Returns:
            统计字典，如 {'text': 5, 'table': 2, 'title': 1}
        """
        summary = {}
        for elem in elements:
            elem_type = elem['type']
            summary[elem_type] = summary.get(elem_type, 0) + 1
        
        return summary
    
    def filter_by_type(self, elements: List[Dict], elem_type: str) -> List[Dict]:
        """
        按类型过滤元素
        
        Args:
            elements: 元素列表
            elem_type: 要过滤的类型 ('text', 'table', 'title', 'figure')
            
        Returns:
            过滤后的元素列表
        """
        return [elem for elem in elements if elem['type'] == elem_type]
    
    def __repr__(self) -> str:
        return (
            f"DocumentLayoutAnalyzer("
            f"use_gpu={self.use_gpu}, "
            f"lang='{self.lang}', "
            f"threshold={self.confidence_threshold})"
        )


def main():
    """测试函数"""
    print("=" * 80)
    print("DocumentLayoutAnalyzer 测试")
    print("=" * 80)
    
    # 创建分析器
    analyzer = DocumentLayoutAnalyzer(use_gpu=False, lang='ch')
    
    # 测试：加载一个示例图片（如果有的话）
    test_image_path = Path(__file__).parent.parent.parent / "data" / "test_page.png"
    
    if test_image_path.exists():
        print(f"\n加载测试图片: {test_image_path}")
        from PIL import Image
        img = Image.open(test_image_path)
        img_array = np.array(img.convert('RGB'))
        
        # 分析页面
        elements = analyzer.analyze_page(img_array)
        
        # 打印结果
        print(f"\n检测到 {len(elements)} 个元素:")
        summary = analyzer.get_element_summary(elements)
        for elem_type, count in summary.items():
            print(f"  {elem_type}: {count} 个")
        
        # 打印前3个元素的详细信息
        print("\n前3个元素详情:")
        for i, elem in enumerate(elements[:3], 1):
            print(f"\n元素 {i}:")
            print(f"  类型: {elem['type']}")
            print(f"  置信度: {elem['confidence']:.3f}")
            print(f"  边界框: {elem['bbox']}")
            print(f"  文本: {elem['res']['text'][:50]}..." if len(elem['res']['text']) > 50 else f"  文本: {elem['res']['text']}")
            if elem['res']['html']:
                print(f"  HTML: {elem['res']['html'][:100]}...")
    else:
        print(f"\n[WARN] 未找到测试图片: {test_image_path}")
        print("提示：请先将一个 PDF 页面保存为 PNG 图片进行测试")
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
