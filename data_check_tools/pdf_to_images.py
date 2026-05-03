# -*- coding: utf-8 -*-
"""
PDF转图片工具
将PDF文件的每一页转换为高分辨率图片并保存
"""

import sys
from pathlib import Path
import fitz  # PyMuPDF


def pdf_to_images(pdf_path: str, output_dir: str = None, dpi: int = 300):
    """
    将PDF转换为图片
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录（默认为PDF同目录下的images文件夹）
        dpi: 图片分辨率（默认300 DPI）
    
    Returns:
        list: 生成的图片路径列表
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"[ERROR] PDF文件不存在: {pdf_path}")
        return []
    
    # 创建输出目录
    if output_dir is None:
        output_dir = pdf_path.parent / "images"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("PDF转图片工具")
    print("=" * 80)
    print(f"\n输入文件: {pdf_path}")
    print(f"输出目录: {output_dir}")
    print(f"分辨率: {dpi} DPI")
    
    # 打开PDF
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"总页数: {total_pages}\n")
    
    image_paths = []
    
    # 逐页转换
    for page_num in range(total_pages):
        page = doc[page_num]
        
        try:
            # 计算缩放比例
            zoom = dpi / 72  # 72是PDF的默认DPI
            mat = fitz.Matrix(zoom, zoom)
            
            # 渲染页面为图片
            pix = page.get_pixmap(matrix=mat)
            
            # 保存图片
            image_filename = f"page_{page_num + 1:03d}.png"
            image_path = output_dir / image_filename
            pix.save(str(image_path))
            
            image_paths.append(image_path)
            
            print(f"[{page_num + 1:3d}/{total_pages}] 已保存: {image_filename} "
                  f"({pix.width}x{pix.height})")
            
        except Exception as e:
            print(f"[{page_num + 1:3d}/{total_pages}] [ERROR] 转换失败: {e}")
    
    doc.close()
    
    print("\n" + "=" * 80)
    print(f"转换完成！共生成 {len(image_paths)} 张图片")
    print(f"保存位置: {output_dir}")
    print("=" * 80)
    
    return image_paths


if __name__ == "__main__":
    # 测试文件
    pdf_file = "e:/Python/gz_zhongkao_advisor/data/2023名额分配结果.pdf"
    
    # 执行转换
    images = pdf_to_images(pdf_file, dpi=300)
    
    if images:
        print(f"\n[OK] 成功转换 {len(images)} 页")
        print(f"\n前3张图片:")
        for img in images[:3]:
            print(f"  - {img}")
    else:
        print("\n[ERROR] 转换失败")
