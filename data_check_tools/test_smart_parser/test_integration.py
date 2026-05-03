# -*- coding: utf-8 -*-
"""
测试模块1 + 模块2的集成
DocumentLayoutAnalyzer + ElementClassifier
"""

import sys
from pathlib import Path
import numpy as np
import fitz

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from smart_parser.layout_analyzer import DocumentLayoutAnalyzer
from smart_parser.element_classifier import ElementClassifier


def test_integration():
    """测试两个模块的集成"""
    
    print("=" * 80)
    print("模块集成测试: LayoutAnalyzer + ElementClassifier")
    print("=" * 80)
    
    # PDF路径
    pdf_path = Path(__file__).parent.parent.parent / "data" / "2023名额分配结果.pdf"
    
    if not pdf_path.exists():
        print(f"[ERROR] PDF文件不存在: {pdf_path}")
        return False
    
    print(f"\n加载PDF: {pdf_path}")
    
    # 创建分析器和分类器
    print("\n[INIT] 初始化模块...")
    analyzer = DocumentLayoutAnalyzer(use_gpu=False, lang='ch')
    classifier = ElementClassifier(confidence_threshold=0.5)
    
    # 打开PDF
    doc = fitz.open(pdf_path)
    
    # 测试第1页
    page_num = 0
    page = doc[page_num]
    
    print(f"\n处理第 {page_num + 1} 页...")
    
    # 转换为图片
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    # 转换为numpy数组
    img_data = pix.tobytes("png")
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(img_data))
    img_array = np.array(img.convert('RGB'))
    
    print(f"图片尺寸: {img_array.shape}")
    
    # 步骤1: 版面分析
    print("\n[步骤1] 版面分析...")
    raw_elements = analyzer.analyze_page(img_array)
    print(f"检测到 {len(raw_elements)} 个原始元素")
    
    # 打印原始元素类型
    type_counts = {}
    for elem in raw_elements:
        elem_type = elem['type']
        type_counts[elem_type] = type_counts.get(elem_type, 0) + 1
    print(f"原始元素分布: {', '.join([f'{k}:{v}' for k, v in type_counts.items()])}")
    
    # 步骤2: 元素分类
    print("\n[步骤2] 元素分类...")
    classified = classifier.classify_elements(raw_elements)
    
    # 打印分类结果
    summary = classifier.get_classification_summary(classified)
    print(f"分类后统计:")
    for elem_type, count in summary.items():
        print(f"  {elem_type:10s}: {count} 个")
    
    # 详细展示每个类型的元素
    print("\n详细分类结果:")
    
    # 表格
    if classified['tables']:
        print(f"\n[TABLES] ({len(classified['tables'])}个):")
        for i, table in enumerate(classified['tables'], 1):
            bbox = table['bbox']
            print(f"  表格{i}: 位置 [{bbox[0]:.0f}, {bbox[1]:.0f}, {bbox[2]:.0f}, {bbox[3]:.0f}]")
    
    # 标题
    if classified['titles']:
        print(f"\n[TITLES] ({len(classified['titles'])}个):")
        for i, title in enumerate(classified['titles'], 1):
            text = title['res'].get('text', '')[:60]
            print(f"  标题{i}: {text}")
    
    # 文章
    if classified['articles']:
        print(f"\n[ARTICLES] ({len(classified['articles'])}个):")
        for i, article in enumerate(classified['articles'], 1):
            text = article['res'].get('text', '')[:60]
            print(f"  段落{i}: {text}...")
    
    # 页眉
    if classified['headers']:
        print(f"\n[HEADERS] ({len(classified['headers'])}个):")
        for i, header in enumerate(classified['headers'], 1):
            text = header['res'].get('text', '')[:60]
            print(f"  页眉{i}: {text}")
    
    # 页脚
    if classified['footers']:
        print(f"\n[FOOTERS] ({len(classified['footers'])}个):")
        for i, footer in enumerate(classified['footers'], 1):
            text = footer['res'].get('text', '')[:60]
            print(f"  页脚{i}: {text}")
    
    # 关闭PDF
    doc.close()
    
    print("\n" + "=" * 80)
    print("[OK] 集成测试完成！")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = test_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
