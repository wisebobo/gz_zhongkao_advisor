"""
PDF OCR 智能文档解析系统
基于 PaddleOCR PP-Structure 的文档版面分析和表格识别
"""

# 逐步导入已完成的模块
from .layout_analyzer import DocumentLayoutAnalyzer

# TODO: 后续添加其他模块
# from .element_classifier import ElementClassifier
# from .table_extractor import TableStructureExtractor
# from .article_extractor import ArticleTextExtractor
# from .output_manager import SeparatedOutputManager
# from .smart_parser import SmartPDFParser

__version__ = "1.0.0"
__all__ = [
    "DocumentLayoutAnalyzer",
    # "ElementClassifier", 
    # "TableStructureExtractor",
    # "ArticleTextExtractor",
    # "SeparatedOutputManager",
    # "SmartPDFParser"
]
