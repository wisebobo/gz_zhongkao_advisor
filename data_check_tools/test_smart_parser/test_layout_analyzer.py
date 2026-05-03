# -*- coding: utf-8 -*-
"""
测试 DocumentLayoutAnalyzer 模块
使用真实的 PDF 页面进行测试
"""

import sys
from pathlib import Path
import numpy as np
import fitz  # PyMuPDF

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from smart_parser.layout_analyzer import DocumentLayoutAnalyzer


def test_with_real_pdf():
    """使用真实的PDF进行测试"""
    
    print("=" * 80)
    print("DocumentLayoutAnalyzer 真实PDF测试")
    print("=" * 80)
    
    # 查找测试PDF
    pdf_path = Path(__file__).parent.parent.parent / "data" / "2023名额分配结果.pdf"
    
    if not pdf_path.exists():
        print(f"[ERROR] PDF文件不存在: {pdf_path}")
        return False
    
    print(f"\n加载PDF: {pdf_path}")
    
    # 创建分析器
    print("\n[INIT] 创建版面分析器...")
    analyzer = DocumentLayoutAnalyzer(use_gpu=False, lang='ch')
    
    # 打开PDF
    doc = fitz.open(pdf_path)
    print(f"PDF总页数: {len(doc)}")
    
    # 测试第1页
    page_num = 0
    page = doc[page_num]
    
    print(f"\n处理第 {page_num + 1} 页...")
    
    # 转换为图片
    zoom = 300 / 72  # 300 DPI
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    
    # 转换为numpy数组
    img_data = pix.tobytes("png")
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(img_data))
    img_array = np.array(img.convert('RGB'))
    
    print(f"图片尺寸: {img_array.shape}")
    
    # 分析页面
    print("\n[OCR] 开始版面分析...")
    elements = analyzer.analyze_page(img_array)
    
    print(f"\n检测到 {len(elements)} 个元素")
    
    # 统计类型
    summary = analyzer.get_element_summary(elements)
    print("\n元素类型统计:")
    for elem_type, count in summary.items():
        print(f"  {elem_type}: {count} 个")
    
    # 打印前5个元素的详细信息
    print("\n前5个元素详情:")
    for i, elem in enumerate(elements[:5], 1):
        print(f"\n元素 {i}:")
        print(f"  类型: {elem['type']}")
        print(f"  置信度: {elem['confidence']:.3f}")
        print(f"  边界框: {elem['bbox']}")
        
        text = elem['res']['text']
        if text:
            if len(text) > 80:
                print(f"  文本: {text[:80]}...")
            else:
                print(f"  文本: {text}")
        
        if elem['res']['html']:
            html_preview = elem['res']['html'][:100]
            print(f"  HTML: {html_preview}...")
    
    # 关闭PDF
    doc.close()
    
    print("\n" + "=" * 80)
    print("[OK] 测试完成！")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = test_with_real_pdf()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
