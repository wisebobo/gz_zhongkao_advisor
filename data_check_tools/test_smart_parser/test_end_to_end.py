# -*- coding: utf-8 -*-
"""
简化版端到端测试
使用已完成的3个模块处理完整PDF
DocumentLayoutAnalyzer + ElementClassifier + TableStructureExtractor
"""

import sys
from pathlib import Path
import numpy as np
import fitz
import pandas as pd

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from smart_parser.layout_analyzer import DocumentLayoutAnalyzer
from smart_parser.element_classifier import ElementClassifier
from smart_parser.table_extractor import TableStructureExtractor
from paddleocr import PaddleOCR


def process_pdf_simple(pdf_path, output_dir=None):
    """
    简化版PDF处理流程
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        
    Returns:
        dict: 处理结果统计
    """
    print("=" * 80)
    print("简化版端到端测试")
    print("=" * 80)
    
    if not Path(pdf_path).exists():
        print(f"[ERROR] PDF文件不存在: {pdf_path}")
        return None
    
    print(f"\n输入文件: {pdf_path}")
    
    # 设置输出目录
    if output_dir is None:
        output_dir = Path(pdf_path).parent / "ocr_output_smart"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"输出目录: {output_dir}")
    
    # 初始化模块
    print("\n[INIT] 初始化模块...")
    analyzer = DocumentLayoutAnalyzer(use_gpu=False, lang='ch')
    classifier = ElementClassifier(confidence_threshold=0.5)
    extractor = TableStructureExtractor()
    
    # 初始化PaddleOCR用于表格区域二次识别
    print("[INIT] 初始化 PaddleOCR (用于表格区域OCR)...")
    ocr_engine = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False, show_log=False)
    
    # 打开PDF
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"PDF总页数: {total_pages}")
    
    # 存储所有表格
    all_tables = []
    total_tables_found = 0
    
    # 逐页处理
    print(f"\n开始处理 {total_pages} 页...\n")
    
    for page_num in range(total_pages):
        page = doc[page_num]
        
        try:
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
            
            # 步骤1: 版面分析
            raw_elements = analyzer.analyze_page(img_array)
            
            # 步骤2: 元素分类
            classified = classifier.classify_elements(raw_elements)
            
            # 步骤3: 提取表格
            page_tables = []
            for table_elem in classified['tables']:
                # 关键修改：对表格区域进行二次OCR
                table_bbox = table_elem['bbox']
                x1, y1, x2, y2 = [int(coord) for coord in table_bbox]
                
                # 裁剪表格区域
                table_img = img_array[y1:y2, x1:x2, :]
                
                if table_img.size == 0:
                    print(f"第 {page_num + 1:2d} 页: [WARN] 表格区域为空")
                    continue
                
                # 对表格区域进行OCR识别
                ocr_result = ocr_engine.ocr(table_img, cls=True)
                
                # 将OCR结果转换为TableStructureExtractor需要的格式
                table_text_elements = []
                if ocr_result and ocr_result[0]:
                    for line in ocr_result[0]:
                        box, (text, confidence) = line
                        # box是4个点的坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        # 转换为 [x1, y1, x2, y2] 格式
                        x_coords = [point[0] for point in box]
                        y_coords = [point[1] for point in box]
                        bbox = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
                        
                        table_text_elements.append({
                            'type': 'text',
                            'bbox': bbox,
                            'res': {'text': text},
                            'confidence': confidence
                        })
                
                # 使用TableStructureExtractor提取结构
                if table_text_elements:
                    df = extractor.extract_table_structure_from_elements(table_text_elements)
                    
                    if df is not None and not df.empty:
                        page_tables.append({
                            'page': page_num + 1,
                            'table_index': len(page_tables) + 1,
                            'dataframe': df,
                            'shape': df.shape
                        })
                        
                        print(f"第 {page_num + 1:2d} 页: 检测到 {len(classified['tables'])} 个表格 | "
                              f"提取成功: {df.shape[0]}行 x {df.shape[1]}列")
                    else:
                        print(f"第 {page_num + 1:2d} 页: 检测到 {len(classified['tables'])} 个表格 | "
                              f"[WARN] 提取失败或为空")
                else:
                    print(f"第 {page_num + 1:2d} 页: 检测到 {len(classified['tables'])} 个表格 | "
                          f"[WARN] OCR未识别到文本")
            
            all_tables.extend(page_tables)
            total_tables_found += len(page_tables)
            
        except Exception as e:
            print(f"第 {page_num + 1} 页处理失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 关闭PDF
    doc.close()
    
    # 保存结果
    print("\n" + "=" * 80)
    print("保存结果...")
    print("=" * 80)
    
    # 保存所有表格到一个Excel文件（每个表格一个Sheet）
    if all_tables:
        excel_path = output_dir / "tables.xlsx"
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for table_info in all_tables:
                sheet_name = f"Page_{table_info['page']}_Table_{table_info['table_index']}"
                
                # Sheet名称不能超过31个字符
                if len(sheet_name) > 31:
                    sheet_name = sheet_name[:31]
                
                table_info['dataframe'].to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False
                )
        
        print(f"[OK] 表格已保存: {excel_path}")
        print(f"     共 {len(all_tables)} 个表格")
    
    # 打印统计
    print("\n" + "=" * 80)
    print("处理完成 - 统计结果")
    print("=" * 80)
    print(f"总页数: {total_pages}")
    print(f"检测到的表格数: {total_tables_found}")
    
    if all_tables:
        print(f"\n表格详情:")
        for i, table_info in enumerate(all_tables[:10], 1):  # 只显示前10个
            print(f"  {i}. 第{table_info['page']}页第{table_info['table_index']}个表格: "
                  f"{table_info['shape'][0]}行 x {table_info['shape'][1]}列")
        
        if len(all_tables) > 10:
            print(f"  ... 还有 {len(all_tables) - 10} 个表格")
    
    print("=" * 80)
    
    return {
        'total_pages': total_pages,
        'total_tables': total_tables_found,
        'tables': all_tables,
        'output_dir': output_dir
    }


if __name__ == "__main__":
    try:
        pdf_path = Path(__file__).parent.parent.parent / "data" / "2023名额分配结果.pdf"
        
        result = process_pdf_simple(str(pdf_path))
        
        if result:
            print("\n[OK] 测试成功完成！")
            sys.exit(0)
        else:
            print("\n[ERROR] 测试失败")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n[ERROR] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
