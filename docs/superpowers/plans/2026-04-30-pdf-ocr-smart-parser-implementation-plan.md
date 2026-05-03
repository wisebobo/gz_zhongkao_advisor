# PDF OCR 智能文档解析系统实施计划

**版本**: v1.0  
**日期**: 2026-05-03  
**作者**: AI Assistant  
**状态**: 📝 待实施  
**关联设计文档**: `docs/superpowers/specs/2026-04-30-pdf-ocr-smart-parser-design.md`

---

## 📋 目录

1. [项目概述](#项目概述)
2. [前置准备](#前置准备)
3. [模块开发计划](#模块开发计划)
4. [测试策略](#测试策略)
5. [集成与迁移策略](#集成与迁移策略)
6. [风险评估与回滚方案](#风险评估与回滚方案)
7. [时间估算](#时间估算)
8. [验收标准](#验收标准)

---

## 项目概述

### 背景

当前PDF OCR识别程序（`data_check_tools/pdf_ocr_processor.py`）存在以下问题：

1. **列数不一致**：表格行单元格数量不统一，导致数据错位
2. **换行识别错误**：单元格内换行被识别为独立行
3. **混合文档处理能力弱**：无法区分文章段落和表格区域
4. **输出格式单一**：仅生成简单文本列表和Excel，未保持原始结构

### 目标

基于PaddleOCR PP-StructureV3构建智能PDF文档解析系统，实现：

- ✅ 自动检测PDF页面类型（纯文章/纯表格/混合）
- ✅ 高精度表格结构识别（支持合并单元格）
- ✅ 智能分离文章和表格内容
- ✅ 分离式输出（文章→TXT，表格→Excel，元数据→JSON）

### 核心改进点

| 维度 | 旧方案 (PDFOCRProcessor) | 新方案 (SmartPDFParser) |
|------|-------------------------|------------------------|
| 版面分析 | ❌ 无 | ✅ PP-Structure自动检测 |
| 表格识别 | ❌ 逐行OCR，无结构 | ✅ HTML结构化输出 |
| 合并单元格 | ❌ 不支持 | ✅ 原生支持 |
| 文章提取 | ❌ 无分类 | ✅ 按类型分离 |
| 输出格式 | Excel单文件 | Excel+TXT+JSON三文件 |

---

## 前置准备

### 1. 环境配置（预计耗时：1小时）

#### 1.1 Python环境验证

```bash
# 验证Python版本（需要3.8+）
D:\Tools\miniconda3\python.exe --version

# 预期输出：Python 3.x.x
```

**检查清单**：
- [ ] Python版本 ≥ 3.8
- [ ] pip可用
- [ ] 虚拟环境可选（推荐）

#### 1.2 依赖安装

**步骤1：更新requirements.txt**

在现有`requirements.txt`基础上添加PP-Structure相关依赖：

```txt
# ============================================================================
# PDF OCR Smart Parser Dependencies (新增)
# ============================================================================

# PaddlePaddle深度学习框架（CPU版本）
paddlepaddle==2.6.2

# PaddleOCR（包含PP-Structure）
paddleocr==2.10.0

# PDF处理
PyMuPDF>=1.23.0,<2.0.0

# HTML解析（已存在，无需重复添加）
# beautifulsoup4>=4.12.0,<5.0.0

# 数据处理（已存在，无需重复添加）
# pandas>=2.0.0,<3.0.0

# Excel输出（已存在，无需重复添加）
# openpyxl>=3.1.0,<4.0.0

# 图像处理
Pillow>=10.0.0,<11.0.0

# 数值计算（通常已安装）
numpy>=1.24.0,<2.0.0
```

**步骤2：安装依赖**

```bash
# 进入项目目录
cd e:\Python\gz_zhongkao_advisor

# 安装新增依赖（使用国内镜像加速）
D:\Tools\miniconda3\python.exe -m pip install paddlepaddle==2.6.2 -i https://pypi.tuna.tsinghua.edu.cn/simple
D:\Tools\miniconda3\python.exe -m pip install paddleocr==2.10.0 -i https://pypi.tuna.tsinghua.edu.cn/simple
D:\Tools\miniconda3\python.exe -m pip install PyMuPDF Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**验证安装**：

```python
# 创建测试脚本 verify_installation.py
import paddle
import paddleocr
import fitz
from bs4 import BeautifulSoup
import pandas as pd

print(f"PaddlePaddle版本: {paddle.__version__}")
print(f"PaddleOCR版本: {paddleocr.__version__}")
print("✅ 所有依赖安装成功")
```

```bash
D:\Tools\miniconda3\python.exe verify_installation.py
```

#### 1.3 PP-Structure模型预下载

**重要**：首次运行会自动下载模型文件（约500MB），建议提前下载。

```python
# 创建 download_models.py
from paddleocr import PPStructure

# 初始化并触发模型下载
table_engine = PPStructure(
    show_log=False,
    recovery=True,
    lang='ch',
    use_gpu=False,
    table=True,
    ocr=True
)

print("✅ PP-Structure模型下载完成")
```

```bash
D:\Tools\miniconda3\python.exe download_models.py
```

**预期输出**：
```
Downloading ppstructure models...
[OK] Model downloaded to ~/.paddleocr/...
```

**注意事项**：
- 模型默认下载到用户主目录下的`.paddleocr`文件夹
- 如果网络不稳定，可手动下载后放置到指定目录
- GPU版本需额外安装CUDA相关依赖（本计划默认使用CPU）

---

### 2. 项目结构规划（预计耗时：0.5小时）

#### 2.1 新模块目录结构

```
gz_zhongkao_advisor/
├── data_check_tools/
│   ├── pdf_ocr_processor.py          # 旧版处理器（保留）
│   ├── smart_pdf_parser/              # 新增：智能解析器模块
│   │   ├── __init__.py
│   │   ├── document_layout_analyzer.py   # 模块1：版面分析器
│   │   ├── element_classifier.py         # 模块2：元素分类器
│   │   ├── table_structure_extractor.py  # 模块3：表格结构提取器
│   │   ├── article_text_extractor.py     # 模块4：文章文本提取器
│   │   ├── separated_output_manager.py   # 模块5：分离式输出管理器
│   │   └── smart_pdf_parser.py           # 模块6：主控制器
│   └── test_smart_parser/               # 新增：测试目录
│       ├── __init__.py
│       ├── test_layout_analyzer.py
│       ├── test_element_classifier.py
│       ├── test_table_extractor.py
│       ├── test_article_extractor.py
│       ├── test_output_manager.py
│       └── test_integration.py
├── docs/
│   └── superpowers/
│       ├── specs/
│       │   └── 2026-04-30-pdf-ocr-smart-parser-design.md
│       └── plans/
│           └── 2026-04-30-pdf-ocr-smart-parser-implementation-plan.md  # 本文档
└── requirements.txt                    # 已更新
```

#### 2.2 文件创建顺序

按照依赖关系从底层到上层依次创建：

1. `document_layout_analyzer.py`（无内部依赖）
2. `element_classifier.py`（无内部依赖）
3. `table_structure_extractor.py`（依赖bs4, pandas）
4. `article_text_extractor.py`（无内部依赖）
5. `separated_output_manager.py`（依赖pandas, openpyxl）
6. `smart_pdf_parser.py`（依赖上述所有模块）

---

## 模块开发计划

### 模块1: DocumentLayoutAnalyzer（版面分析器）

**预计耗时**：4小时  
**优先级**：⭐⭐⭐⭐⭐（核心基础）

#### 开发步骤

**步骤1.1：创建基础类结构（1小时）**

文件：`data_check_tools/smart_pdf_parser/document_layout_analyzer.py`

```python
# -*- coding: utf-8 -*-
"""
文档版面分析器 - 基于PP-Structure
"""

import numpy as np
from typing import List, Dict
from paddleocr import PPStructure


class DocumentLayoutAnalyzer:
    """使用PP-Structure进行页面元素检测和分类"""
    
    def __init__(self, use_gpu=False, lang='ch', confidence_threshold=0.6):
        """
        Args:
            use_gpu: 是否使用GPU加速
            lang: 识别语言 ('ch'/'en'/'multi')
            confidence_threshold: 置信度阈值
        """
        self.confidence_threshold = confidence_threshold
        
        # 初始化PP-Structure引擎
        self.engine = PPStructure(
            show_log=False,
            recovery=True,      # 保留表格结构
            lang=lang,
            use_gpu=use_gpu,
            table=True,         # 启用表格识别
            ocr=True            # 同时启用OCR
        )
    
    def analyze_page(self, image: np.ndarray) -> List[Dict]:
        """
        分析单页布局
        
        Args:
            image: RGB图像数组 (H, W, 3)
            
        Returns:
            elements: 元素列表
        """
        # TODO: 实现版面分析逻辑
        pass
    
    def _post_process_results(self, raw_results) -> List[Dict]:
        """
        后处理PP-Structure输出结果
        
        Args:
            raw_results: PP-Structure原始输出
            
        Returns:
            标准化后的元素列表
        """
        # TODO: 实现后处理逻辑
        pass
```

**步骤1.2：实现核心分析逻辑（2小时）**

关键实现点：

1. **调用PP-Structure**：
```python
def analyze_page(self, image: np.ndarray) -> List[Dict]:
    # PP-Structure期望BGR格式，需要转换
    if len(image.shape) == 3 and image.shape[2] == 3:
        # RGB → BGR
        image_bgr = image[:, :, ::-1]
    else:
        image_bgr = image
    
    # 执行版面分析
    result = self.engine(image_bgr)
    
    # 后处理
    elements = self._post_process_results(result)
    
    return elements
```

2. **结果后处理**：
```python
def _post_process_results(self, raw_results) -> List[Dict]:
    elements = []
    
    for item in raw_results:
        # 提取关键字段
        elem_type = item.get('type', 'text')
        bbox = item.get('bbox', [])
        res = item.get('res', {})
        
        # 置信度过滤
        confidence = res.get('score', 1.0)
        if confidence < self.confidence_threshold:
            continue
        
        # 标准化bbox格式
        if bbox and len(bbox) == 4:
            bbox_normalized = [
                int(bbox[0]),  # x1
                int(bbox[1]),  # y1
                int(bbox[2]),  # x2
                int(bbox[3])   # y2
            ]
        else:
            bbox_normalized = []
        
        # 构建标准化元素
        element = {
            'type': elem_type,
            'bbox': bbox_normalized,
            'res': {
                'text': res.get('text', ''),
                'html': res.get('html', '')  # 表格才有HTML
            },
            'confidence': confidence
        }
        
        elements.append(element)
    
    return elements
```

**步骤1.3：编写单元测试（1小时）**

文件：`data_check_tools/test_smart_parser/test_layout_analyzer.py`

```python
import unittest
import numpy as np
from smart_pdf_parser.document_layout_analyzer import DocumentLayoutAnalyzer


class TestDocumentLayoutAnalyzer(unittest.TestCase):
    
    def setUp(self):
        """测试前初始化"""
        self.analyzer = DocumentLayoutAnalyzer(
            use_gpu=False,
            lang='ch',
            confidence_threshold=0.6
        )
    
    def test_init_success(self):
        """测试初始化成功"""
        self.assertIsNotNone(self.analyzer.engine)
    
    def test_analyze_blank_page(self):
        """测试空白页面"""
        blank_image = np.ones((800, 600, 3), dtype=np.uint8) * 255
        elements = self.analyzer.analyze_page(blank_image)
        self.assertIsInstance(elements, list)
    
    # 更多测试用例...


if __name__ == '__main__':
    unittest.main()
```

#### 验收标准

- [ ] 能正确初始化PP-Structure引擎
- [ ] 输入图片后返回标准化元素列表
- [ ] 置信度过滤生效
- [ ] bbox格式统一为[x1, y1, x2, y2]
- [ ] 单元测试通过率100%

---

### 模块2: ElementClassifier（元素分类器）

**预计耗时**：2小时  
**优先级**：⭐⭐⭐⭐

#### 开发步骤

**步骤2.1：创建分类器类（1小时）**

文件：`data_check_tools/smart_pdf_parser/element_classifier.py`

```python
# -*- coding: utf-8 -*-
"""
元素分类器 - 对PP-Structure输出进行分类和过滤
"""

from typing import List, Dict


class ElementClassifier:
    """对版面分析结果进行分类"""
    
    def __init__(self, confidence_threshold=0.6):
        self.confidence_threshold = confidence_threshold
    
    def classify_elements(self, raw_elements: List[Dict]) -> Dict[str, List]:
        """
        分类元素
        
        Args:
            raw_elements: 原始元素列表
            
        Returns:
            分类结果字典
        """
        classified = {
            'tables': [],
            'articles': [],
            'titles': [],
            'figures': []
        }
        
        for elem in raw_elements:
            # 1. 置信度过滤
            if elem.get('confidence', 0) < self.confidence_threshold:
                continue
            
            # 2. 类型映射
            elem_type = elem.get('type', '').lower()
            
            if elem_type == 'table':
                classified['tables'].append(elem)
            elif elem_type in ['text', 'paragraph']:
                classified['articles'].append(elem)
            elif elem_type == 'title':
                classified['titles'].append(elem)
            elif elem_type == 'figure':
                classified['figures'].append(elem)
        
        return classified
```

**步骤2.2：增强功能（可选，0.5小时）**

添加相邻元素合并逻辑：

```python
def merge_adjacent_articles(self, articles: List[Dict], y_threshold=20) -> List[Dict]:
    """
    合并相邻的文章段落
    
    Args:
        articles: 文章元素列表
        y_threshold: Y坐标阈值（像素）
        
    Returns:
        合并后的文章列表
    """
    if not articles:
        return []
    
    # 按Y坐标排序
    sorted_articles = sorted(articles, key=lambda x: x['bbox'][1] if x['bbox'] else 0)
    
    merged = [sorted_articles[0]]
    
    for current in sorted_articles[1:]:
        previous = merged[-1]
        
        # 判断是否相邻
        prev_y2 = previous['bbox'][3] if previous['bbox'] else 0
        curr_y1 = current['bbox'][1] if current['bbox'] else 0
        
        if curr_y1 - prev_y2 < y_threshold:
            # 合并文本
            previous['res']['text'] += '\n' + current['res']['text']
            # 更新bbox
            if previous['bbox'] and current['bbox']:
                previous['bbox'][3] = max(prev_y2, current['bbox'][3])
        else:
            merged.append(current)
    
    return merged
```

**步骤2.3：编写测试（0.5小时）**

文件：`data_check_tools/test_smart_parser/test_element_classifier.py`

```python
import unittest
from smart_pdf_parser.element_classifier import ElementClassifier


class TestElementClassifier(unittest.TestCase):
    
    def setUp(self):
        self.classifier = ElementClassifier(confidence_threshold=0.6)
    
    def test_classify_tables(self):
        """测试表格分类"""
        elements = [
            {'type': 'table', 'confidence': 0.9, 'bbox': [0, 0, 100, 100], 'res': {}},
            {'type': 'text', 'confidence': 0.8, 'bbox': [0, 0, 100, 100], 'res': {}},
        ]
        
        result = self.classifier.classify_elements(elements)
        
        self.assertEqual(len(result['tables']), 1)
        self.assertEqual(len(result['articles']), 1)
    
    def test_confidence_filter(self):
        """测试置信度过滤"""
        elements = [
            {'type': 'table', 'confidence': 0.5, 'bbox': [], 'res': {}},
            {'type': 'table', 'confidence': 0.9, 'bbox': [], 'res': {}},
        ]
        
        result = self.classifier.classify_elements(elements)
        
        self.assertEqual(len(result['tables']), 1)


if __name__ == '__main__':
    unittest.main()
```

#### 验收标准

- [ ] 能正确分类四种元素类型
- [ ] 置信度过滤生效
- [ ] 空输入不会报错
- [ ] 单元测试覆盖率≥90%

---

### 模块3: TableStructureExtractor（表格结构提取器）

**预计耗时**：3小时  
**优先级**：⭐⭐⭐⭐⭐（核心难点）

#### 开发步骤

**步骤3.1：创建基础类（1小时）**

文件：`data_check_tools/smart_pdf_parser/table_structure_extractor.py`

```python
# -*- coding: utf-8 -*-
"""
表格结构提取器 - HTML转DataFrame
"""

import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Tuple, Optional


class TableStructureExtractor:
    """将HTML表格转换为DataFrame，处理合并单元格"""
    
    def html_to_dataframe(self, html_content: str) -> Optional[pd.DataFrame]:
        """
        HTML表格转DataFrame
        
        Args:
            html_content: HTML字符串
            
        Returns:
            DataFrame或None
        """
        if not html_content or not html_content.strip():
            return None
        
        try:
            # pandas直接解析HTML表格
            dfs = pd.read_html(html_content)
            
            if not dfs:
                return None
            
            df = dfs[0]
            
            # 处理NaN（合并单元格填充）
            df = df.fillna('')
            
            # 清理空白字符
            df = df.applymap(lambda x: str(x).strip() if isinstance(x, str) else x)
            
            return df
        
        except Exception as e:
            print(f"⚠️ HTML解析失败: {e}")
            return None
    
    def detect_merged_cells(self, html_content: str) -> List[Tuple]:
        """
        检测合并单元格
        
        Args:
            html_content: HTML字符串
            
        Returns:
            [(row_idx, col_idx, rowspan, colspan), ...]
        """
        if not html_content:
            return []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            merged_info = []
            
            table = soup.find('table')
            if not table:
                return merged_info
            
            rows = table.find_all('tr')
            for row_idx, tr in enumerate(rows):
                cells = tr.find_all(['td', 'th'])
                for col_idx, cell in enumerate(cells):
                    rowspan = int(cell.get('rowspan', 1))
                    colspan = int(cell.get('colspan', 1))
                    
                    if rowspan > 1 or colspan > 1:
                        merged_info.append((row_idx, col_idx, rowspan, colspan))
            
            return merged_info
        
        except Exception as e:
            print(f"⚠️ 合并单元格检测失败: {e}")
            return []
```

**步骤3.2：增强功能（1小时）**

添加表头检测和数据清洗：

```python
def extract_with_header_detection(self, html_content: str) -> dict:
    """
    提取表格并自动检测表头
    
    Returns:
        {
            'dataframe': pd.DataFrame,
            'has_header': bool,
            'merged_cells': List[Tuple]
        }
    """
    df = self.html_to_dataframe(html_content)
    merged = self.detect_merged_cells(html_content)
    
    if df is None:
        return {
            'dataframe': None,
            'has_header': False,
            'merged_cells': []
        }
    
    # 简单启发式检测表头：第一行是否都是文本且不含数字
    has_header = False
    if len(df) > 0:
        first_row = df.iloc[0]
        # 如果第一行所有单元格都是字符串且不包含数字，可能是表头
        if all(isinstance(val, str) and not any(c.isdigit() for c in val) 
               for val in first_row if val):
            has_header = True
            # 将第一行设为列名
            df.columns = df.iloc[0]
            df = df[1:].reset_index(drop=True)
    
    return {
        'dataframe': df,
        'has_header': has_header,
        'merged_cells': merged
    }
```

**步骤3.3：编写测试（1小时）**

文件：`data_check_tools/test_smart_parser/test_table_extractor.py`

```python
import unittest
import pandas as pd
from smart_pdf_parser.table_structure_extractor import TableStructureExtractor


class TestTableStructureExtractor(unittest.TestCase):
    
    def setUp(self):
        self.extractor = TableStructureExtractor()
    
    def test_simple_table(self):
        """测试简单表格"""
        html = """
        <table>
            <tr><td>A</td><td>B</td></tr>
            <tr><td>1</td><td>2</td></tr>
        </table>
        """
        
        df = self.extractor.html_to_dataframe(html)
        
        self.assertIsNotNone(df)
        self.assertEqual(df.shape, (2, 2))
    
    def test_merged_cells(self):
        """测试合并单元格检测"""
        html = """
        <table>
            <tr><td rowspan="2">A</td><td>B</td></tr>
            <tr><td>C</td></tr>
        </table>
        """
        
        merged = self.extractor.detect_merged_cells(html)
        
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0], (0, 0, 2, 1))
    
    def test_empty_html(self):
        """测试空HTML"""
        df = self.extractor.html_to_dataframe("")
        self.assertIsNone(df)


if __name__ == '__main__':
    unittest.main()
```

#### 验收标准

- [ ] 能正确解析简单HTML表格
- [ ] 能检测合并单元格
- [ ] 空HTML不会崩溃
- [ ] pandas DataFrame格式正确
- [ ] 单元测试覆盖率≥90%

---

### 模块4: ArticleTextExtractor（文章文本提取器）

**预计耗时**：2小时  
**优先级**：⭐⭐⭐

#### 开发步骤

**步骤4.1：创建提取器类（1.5小时）**

文件：`data_check_tools/smart_pdf_parser/article_text_extractor.py`

```python
# -*- coding: utf-8 -*-
"""
文章文本提取器 - 提取和整理文章段落
"""

from typing import List, Dict


class ArticleTextExtractor:
    """提取和格式化文章段落"""
    
    def extract_articles(self, article_elements: List[Dict], page_num: int) -> str:
        """
        提取文章文本
        
        Args:
            article_elements: 文章元素列表
            page_num: 页码
            
        Returns:
            格式化文本
        """
        if not article_elements:
            return f"=== 第{page_num}页 ===\n\n（无文章内容）"
        
        # 1. 按Y坐标排序（从上到下）
        sorted_elements = sorted(
            article_elements,
            key=lambda x: x['bbox'][1] if x['bbox'] else 0
        )
        
        # 2. 提取文本
        paragraphs = []
        for elem in sorted_elements:
            text = elem.get('res', {}).get('text', '')
            if text.strip():
                paragraphs.append(text.strip())
        
        # 3. 拼接段落
        article_text = '\n\n'.join(paragraphs)
        
        # 4. 添加页码标记
        formatted_text = f"=== 第{page_num}页 ===\n\n{article_text}"
        
        return formatted_text
    
    def extract_with_titles(self, 
                           article_elements: List[Dict], 
                           title_elements: List[Dict],
                           page_num: int) -> str:
        """
        提取文章并插入标题
        
        Args:
            article_elements: 文章元素列表
            title_elements: 标题元素列表
            page_num: 页码
            
        Returns:
            带标题的格式化文本
        """
        # 合并文章和标题，按Y坐标排序
        all_elements = []
        
        for elem in article_elements:
            all_elements.append({
                'type': 'article',
                'y': elem['bbox'][1] if elem['bbox'] else 0,
                'text': elem.get('res', {}).get('text', '')
            })
        
        for elem in title_elements:
            all_elements.append({
                'type': 'title',
                'y': elem['bbox'][1] if elem['bbox'] else 0,
                'text': elem.get('res', {}).get('text', '')
            })
        
        # 按Y坐标排序
        all_elements.sort(key=lambda x: x['y'])
        
        # 构建文本
        paragraphs = []
        for elem in all_elements:
            text = elem['text'].strip()
            if not text:
                continue
            
            if elem['type'] == 'title':
                # 标题加粗标记
                paragraphs.append(f"**{text}**")
            else:
                paragraphs.append(text)
        
        article_text = '\n\n'.join(paragraphs)
        formatted_text = f"=== 第{page_num}页 ===\n\n{article_text}"
        
        return formatted_text
```

**步骤4.2：编写测试（0.5小时）**

文件：`data_check_tools/test_smart_parser/test_article_extractor.py`

```python
import unittest
from smart_pdf_parser.article_text_extractor import ArticleTextExtractor


class TestArticleTextExtractor(unittest.TestCase):
    
    def setUp(self):
        self.extractor = ArticleTextExtractor()
    
    def test_extract_simple(self):
        """测试简单文章提取"""
        elements = [
            {
                'bbox': [0, 100, 100, 120],
                'res': {'text': '第一段'}
            },
            {
                'bbox': [0, 150, 100, 170],
                'res': {'text': '第二段'}
            }
        ]
        
        result = self.extractor.extract_articles(elements, page_num=1)
        
        self.assertIn('=== 第1页 ===', result)
        self.assertIn('第一段', result)
        self.assertIn('第二段', result)
    
    def test_empty_elements(self):
        """测试空元素列表"""
        result = self.extractor.extract_articles([], page_num=1)
        self.assertIn('无文章内容', result)


if __name__ == '__main__':
    unittest.main()
```

#### 验收标准

- [ ] 能按Y坐标正确排序段落
- [ ] 页码标记格式正确
- [ ] 空输入有友好提示
- [ ] 标题插入位置正确（可选功能）

---

### 模块5: SeparatedOutputManager（分离式输出管理器）

**预计耗时**：3小时  
**优先级**：⭐⭐⭐⭐

#### 开发步骤

**步骤5.1：创建输出管理器类（2小时）**

文件：`data_check_tools/smart_pdf_parser/separated_output_manager.py`

```python
# -*- coding: utf-8 -*-
"""
分离式输出管理器 - 生成Excel、TXT、JSON文件
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict
from datetime import datetime


class SeparatedOutputManager:
    """管理三种输出格式的生成"""
    
    def __init__(self, output_dir: Path):
        """
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_tables_to_excel(self, tables_data: List[Dict], pdf_name: str) -> Path:
        """
        保存表格到Excel
        
        Args:
            tables_data: 表格数据列表
                [{
                    'page': int,
                    'table_index': int,
                    'dataframe': pd.DataFrame,
                    'merged_cells': List[Tuple]
                }, ...]
            pdf_name: PDF文件名（不含扩展名）
            
        Returns:
            Excel文件路径
        """
        excel_path = self.output_dir / f"{pdf_name}_tables.xlsx"
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for table_info in tables_data:
                page = table_info['page']
                table_idx = table_info['table_index']
                df = table_info['dataframe']
                
                if df is None or df.empty:
                    continue
                
                # Sheet命名：Page_{页码}_Table_{序号}
                sheet_name = f"Page_{page}_Table_{table_idx}"
                
                # Excel Sheet名称长度限制31字符
                if len(sheet_name) > 31:
                    sheet_name = sheet_name[:31]
                
                # 写入Sheet
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"✅ Excel已保存: {excel_path}")
        return excel_path
    
    def save_articles_to_txt(self, articles_data: List[Dict], pdf_name: str) -> Path:
        """
        保存文章到TXT
        
        Args:
            articles_data: 文章数据列表
                [{'page': int, 'text': str}, ...]
            pdf_name: PDF文件名
            
        Returns:
            TXT文件路径
        """
        txt_path = self.output_dir / f"{pdf_name}_articles.txt"
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            separator = "=" * 80
            
            for idx, article_info in enumerate(articles_data):
                if idx > 0:
                    f.write(f"\n{separator}\n\n")
                
                f.write(article_info['text'])
        
        print(f"✅ TXT已保存: {txt_path}")
        return txt_path
    
    def save_metadata(self, metadata: Dict, pdf_name: str) -> Path:
        """
        保存元数据到JSON
        
        Args:
            metadata: 元数据字典
            pdf_name: PDF文件名
            
        Returns:
            JSON文件路径
        """
        json_path = self.output_dir / f"{pdf_name}_metadata.json"
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON已保存: {json_path}")
        return json_path
    
    def generate_complete_output(self, 
                                 tables_data: List[Dict],
                                 articles_data: List[Dict],
                                 metadata: Dict,
                                 pdf_name: str) -> Dict[str, Path]:
        """
        生成完整输出
        
        Returns:
            文件路径字典
        """
        output_files = {}
        
        if tables_data:
            output_files['excel'] = self.save_tables_to_excel(tables_data, pdf_name)
        
        if articles_data:
            output_files['txt'] = self.save_articles_to_txt(articles_data, pdf_name)
        
        if metadata:
            output_files['json'] = self.save_metadata(metadata, pdf_name)
        
        return output_files
```

**步骤5.2：编写测试（1小时）**

文件：`data_check_tools/test_smart_parser/test_output_manager.py`

```python
import unittest
import tempfile
import pandas as pd
from pathlib import Path
from smart_pdf_parser.separated_output_manager import SeparatedOutputManager


class TestSeparatedOutputManager(unittest.TestCase):
    
    def setUp(self):
        """创建临时输出目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SeparatedOutputManager(Path(self.temp_dir))
    
    def test_save_excel(self):
        """测试Excel保存"""
        tables_data = [
            {
                'page': 1,
                'table_index': 1,
                'dataframe': pd.DataFrame({'A': [1, 2], 'B': [3, 4]}),
                'merged_cells': []
            }
        ]
        
        path = self.manager.save_tables_to_excel(tables_data, "test_pdf")
        
        self.assertTrue(path.exists())
        self.assertIn("test_pdf_tables.xlsx", str(path))
    
    def test_save_txt(self):
        """测试TXT保存"""
        articles_data = [
            {'page': 1, 'text': '=== 第1页 ===\n\n测试文章'}
        ]
        
        path = self.manager.save_articles_to_txt(articles_data, "test_pdf")
        
        self.assertTrue(path.exists())
        self.assertIn("test_pdf_articles.txt", str(path))
    
    def test_save_json(self):
        """测试JSON保存"""
        metadata = {
            'pdf_name': 'test',
            'total_pages': 1
        }
        
        path = self.manager.save_metadata(metadata, "test_pdf")
        
        self.assertTrue(path.exists())
        self.assertIn("test_pdf_metadata.json", str(path))


if __name__ == '__main__':
    unittest.main()
```

#### 验收标准

- [ ] Excel文件格式正确，可正常打开
- [ ] Sheet命名符合规范
- [ ] TXT编码UTF-8，分隔符正确
- [ ] JSON格式合法，缩进美观
- [ ] 空数据不会报错

---

### 模块6: SmartPDFParser（主控制器）

**预计耗时**：5小时  
**优先级**：⭐⭐⭐⭐⭐（核心集成）

#### 开发步骤

**步骤6.1：创建主控制器类（3小时）**

文件：`data_check_tools/smart_pdf_parser/smart_pdf_parser.py`

```python
# -*- coding: utf-8 -*-
"""
智能PDF解析器 - 主控制器
"""

import io
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image
import fitz  # PyMuPDF

from .document_layout_analyzer import DocumentLayoutAnalyzer
from .element_classifier import ElementClassifier
from .table_structure_extractor import TableStructureExtractor
from .article_text_extractor import ArticleTextExtractor
from .separated_output_manager import SeparatedOutputManager


class SmartPDFParser:
    """整合所有模块，协调整个处理流程"""
    
    def __init__(self, use_gpu=False, lang='ch', confidence_threshold=0.6):
        """
        Args:
            use_gpu: 是否使用GPU
            lang: 识别语言
            confidence_threshold: 置信度阈值
        """
        self.layout_analyzer = DocumentLayoutAnalyzer(
            use_gpu=use_gpu,
            lang=lang,
            confidence_threshold=confidence_threshold
        )
        self.element_classifier = ElementClassifier(
            confidence_threshold=confidence_threshold
        )
        self.table_extractor = TableStructureExtractor()
        self.article_extractor = ArticleTextExtractor()
        self.output_manager = None
    
    def process_pdf(self, pdf_path: str, output_dir: str = None) -> Dict:
        """
        处理整个PDF
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录（默认：PDF同级目录/ocr_output）
            
        Returns:
            stats: 处理统计
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        # 步骤1: 初始化输出管理器
        if output_dir is None:
            output_dir = pdf_path.parent / "ocr_output_smart"
        self.output_manager = SeparatedOutputManager(Path(output_dir))
        
        pdf_name = pdf_path.stem
        
        print(f"\n{'='*80}")
        print(f"[START] 开始智能PDF解析")
        print(f"{'='*80}")
        print(f"输入文件: {pdf_path}")
        print(f"输出目录: {output_dir}")
        print(f"{'='*80}\n")
        
        # 步骤2: PDF转图片
        images = self.pdf_to_images(str(pdf_path))
        
        # 步骤3: 逐页处理
        all_tables = []
        all_articles = []
        metadata = {
            'pdf_name': pdf_name,
            'total_pages': len(images),
            'process_time': '',
            'config': {
                'use_gpu': self.layout_analyzer.engine.use_gpu,
                'lang': self.layout_analyzer.engine.lang,
                'confidence_threshold': self.element_classifier.confidence_threshold
            },
            'pages': {}
        }
        
        for page_num, image in enumerate(images, 1):
            print(f"\n[PAGE] 正在处理第 {page_num}/{len(images)} 页...")
            
            try:
                # 3.1 版面分析
                elements = self.layout_analyzer.analyze_page(image)
                print(f"   检测到 {len(elements)} 个元素")
                
                # 3.2 元素分类
                classified = self.element_classifier.classify_elements(elements)
                print(f"   分类结果: {len(classified['tables'])}个表格, "
                      f"{len(classified['articles'])}篇文章, "
                      f"{len(classified['titles'])}个标题")
                
                # 3.3 处理表格
                page_tables = []
                for idx, table_elem in enumerate(classified['tables'], 1):
                    html = table_elem.get('res', {}).get('html', '')
                    if html:
                        df = self.table_extractor.html_to_dataframe(html)
                        merged = self.table_extractor.detect_merged_cells(html)
                        
                        if df is not None and not df.empty:
                            page_tables.append({
                                'page': page_num,
                                'table_index': idx,
                                'dataframe': df,
                                'merged_cells': merged
                            })
                
                all_tables.extend(page_tables)
                
                # 3.4 处理文章
                if classified['articles'] or classified['titles']:
                    article_text = self.article_extractor.extract_with_titles(
                        classified['articles'],
                        classified['titles'],
                        page_num
                    )
                    all_articles.append({
                        'page': page_num,
                        'text': article_text
                    })
                
                # 3.5 记录元数据
                metadata['pages'][str(page_num)] = {
                    'tables_count': len(page_tables),
                    'articles_count': len(classified['articles']),
                    'elements': [
                        {
                            'type': elem['type'],
                            'bbox': elem['bbox'],
                            'confidence': elem['confidence']
                        }
                        for elem in elements
                    ]
                }
                
                print(f"   [OK] 第 {page_num} 页处理完成")
            
            except Exception as e:
                print(f"   ⚠️ 第 {page_num} 页处理失败: {e}")
                # 继续处理下一页
        
        # 步骤4: 生成输出文件
        metadata['process_time'] = ''
        output_files = self.output_manager.generate_complete_output(
            tables_data=all_tables,
            articles_data=all_articles,
            metadata=metadata,
            pdf_name=pdf_name
        )
        
        # 步骤5: 返回统计
        stats = {
            'total_pages': len(images),
            'total_tables': len(all_tables),
            'total_articles': len(all_articles),
            'output_files': {k: str(v) for k, v in output_files.items()}
        }
        
        print(f"\n{'='*80}")
        print(f"[OK] 智能PDF解析完成！")
        print(f"{'='*80}")
        print(f"总页数: {stats['total_pages']}")
        print(f"表格数: {stats['total_tables']}")
        print(f"文章数: {stats['total_articles']}")
        print(f"{'='*80}\n")
        
        return stats
    
    def pdf_to_images(self, pdf_path: str, dpi=300) -> List[np.ndarray]:
        """
        PDF转图片
        
        Args:
            pdf_path: PDF文件路径
            dpi: 分辨率
            
        Returns:
            图片数组列表
        """
        doc = fitz.open(pdf_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为numpy数组 (RGB)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            img_array = np.array(img)
            
            images.append(img_array)
        
        doc.close()
        return images
```

**步骤6.2：创建便捷入口（1小时）**

文件：`data_check_tools/smart_pdf_parser/__init__.py`

```python
# -*- coding: utf-8 -*-
"""
智能PDF解析器模块
"""

from .smart_pdf_parser import SmartPDFParser

__all__ = ['SmartPDFParser']
```

文件：`data_check_tools/run_smart_parser.py`（命令行工具）

```python
# -*- coding: utf-8 -*-
"""
智能PDF解析器 - 命令行入口
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from smart_pdf_parser import SmartPDFParser


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python run_smart_parser.py <pdf_path> [output_dir]")
        print("\n示例:")
        print("  python run_smart_parser.py data/2023名额分配结果.pdf")
        print("  python run_smart_parser.py data/test.pdf output/my_output")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 创建解析器
    parser = SmartPDFParser(
        use_gpu=False,
        lang='ch',
        confidence_threshold=0.6
    )
    
    # 处理PDF
    try:
        stats = parser.process_pdf(pdf_path, output_dir)
        print("\n✅ 处理成功！")
        print(f"输出文件:")
        for file_type, file_path in stats['output_files'].items():
            print(f"  {file_type}: {file_path}")
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**步骤6.3：编写集成测试（1小时）**

文件：`data_check_tools/test_smart_parser/test_integration.py`

```python
import unittest
from pathlib import Path
from smart_pdf_parser import SmartPDFParser


class TestIntegration(unittest.TestCase):
    
    def test_full_pipeline(self):
        """测试完整处理流程"""
        pdf_path = Path(__file__).parent.parent.parent / "data" / "2023名额分配结果.pdf"
        
        if not pdf_path.exists():
            self.skipTest("测试PDF不存在")
        
        parser = SmartPDFParser(use_gpu=False, lang='ch')
        
        # 处理PDF
        stats = parser.process_pdf(
            str(pdf_path),
            output_dir=str(pdf_path.parent / "test_output")
        )
        
        # 验证统计
        self.assertGreater(stats['total_pages'], 0)
        self.assertIn('output_files', stats)
        
        # 验证输出文件存在
        for file_type, file_path in stats['output_files'].items():
            self.assertTrue(Path(file_path).exists())


if __name__ == '__main__':
    unittest.main()
```

#### 验收标准

- [ ] 能完整处理测试PDF
- [ ] 三个输出文件都生成
- [ ] 错误处理优雅（单页失败不影响其他页）
- [ ] 进度提示清晰
- [ ] 集成测试通过

---

## 测试策略

### 1. 单元测试（每个模块独立测试）

**测试覆盖目标**：≥85%

| 模块 | 测试文件 | 关键测试用例 |
|------|---------|------------|
| DocumentLayoutAnalyzer | test_layout_analyzer.py | 初始化、空白页、置信度过滤 |
| ElementClassifier | test_element_classifier.py | 分类准确性、置信度过滤 |
| TableStructureExtractor | test_table_extractor.py | 简单表格、合并单元格、空HTML |
| ArticleTextExtractor | test_article_extractor.py | 段落排序、页码标记、空输入 |
| SeparatedOutputManager | test_output_manager.py | Excel/TXT/JSON生成、文件存在性 |
| SmartPDFParser | test_integration.py | 端到端流程、错误处理 |

**运行测试**：

```bash
cd e:\Python\gz_zhongkao_advisor\data_check_tools

# 运行所有测试
D:\Tools\miniconda3\python.exe -m pytest test_smart_parser/ -v

# 运行单个模块测试
D:\Tools\miniconda3\python.exe -m pytest test_smart_parser/test_layout_analyzer.py -v
```

### 2. 集成测试（真实PDF测试）

**测试数据集**：

| PDF文件 | 页数 | 类型 | 用途 |
|--------|------|------|------|
| 2023名额分配结果.pdf | 30 | 纯表格 | 验证表格识别准确率 |
| 政策文件示例.pdf | 10 | 纯文章 | 验证文章提取 |
| 混合文档示例.pdf | 20 | 混合 | 验证分类能力 |

**验收指标**：

- 表格检测准确率 ≥ 90%
- 单元格识别准确率 ≥ 95%
- 文章提取准确率 ≥ 85%
- 单页处理时间 ≤ 5秒（CPU）

### 3. 性能测试

**测试脚本**：`data_check_tools/benchmark_smart_parser.py`

```python
import time
from pathlib import Path
from smart_pdf_parser import SmartPDFParser


def benchmark():
    """性能基准测试"""
    pdf_path = Path("data/2023名额分配结果.pdf")
    
    parser = SmartPDFParser(use_gpu=False, lang='ch')
    
    start_time = time.time()
    stats = parser.process_pdf(str(pdf_path))
    end_time = time.time()
    
    total_time = end_time - start_time
    avg_time_per_page = total_time / stats['total_pages']
    
    print(f"\n性能测试结果:")
    print(f"  总耗时: {total_time:.2f}秒")
    print(f"  平均每页: {avg_time_per_page:.2f}秒")
    print(f"  总页数: {stats['total_pages']}")
    
    # 验证性能指标
    assert avg_time_per_page <= 5.0, f"平均处理时间超过5秒: {avg_time_per_page:.2f}秒"


if __name__ == "__main__":
    benchmark()
```

---

## 集成与迁移策略

### 1. 渐进式迁移方案

**阶段1：并行运行（1周）**

- 保留旧版`pdf_ocr_processor.py`
- 新版`smart_pdf_parser`独立运行
- 对比两种方案的输出质量

**对比测试脚本**：`data_check_tools/compare_outputs.py`

```python
"""
对比新旧方案输出质量
"""

from pdf_ocr_processor import PDFOCRProcessor
from smart_pdf_parser import SmartPDFParser


def compare(pdf_path):
    """对比两种方案"""
    print("="*80)
    print("旧方案测试")
    print("="*80)
    
    old_processor = PDFOCRProcessor(use_gpu=False, lang='ch')
    old_result = old_processor.process_pdf(pdf_path, save_excel=True)
    
    print("\n" + "="*80)
    print("新方案测试")
    print("="*80)
    
    new_parser = SmartPDFParser(use_gpu=False, lang='ch')
    new_stats = new_parser.process_pdf(pdf_path)
    
    print("\n" + "="*80)
    print("对比总结")
    print("="*80)
    print(f"旧方案输出: ocr_result.xlsx")
    print(f"新方案输出: {new_stats['output_files']}")
    print(f"\n请人工检查输出质量差异")


if __name__ == "__main__":
    compare("data/2023名额分配结果.pdf")
```

**阶段2：逐步替换（2周）**

- 修改业务代码调用新API
- 保留旧代码作为fallback
- 收集用户反馈

**阶段3：完全迁移（1周）**

- 删除旧代码
- 更新文档
- 正式发布

### 2. API兼容性设计

**旧API**：
```python
processor = PDFOCRProcessor(use_gpu=False, lang='ch')
result = processor.process_pdf(pdf_path, output_dir, save_excel=True)
```

**新API**（保持相似接口）：
```python
parser = SmartPDFParser(use_gpu=False, lang='ch')
stats = parser.process_pdf(pdf_path, output_dir)
```

**兼容层**（可选）：
```python
class CompatiblePDFOCRProcessor:
    """兼容旧接口的包装器"""
    
    def __init__(self, use_gpu=False, lang='ch'):
        self.parser = SmartPDFParser(use_gpu=use_gpu, lang=lang)
    
    def process_pdf(self, pdf_path, output_dir=None, save_excel=True):
        """兼容旧方法签名"""
        stats = self.parser.process_pdf(pdf_path, output_dir)
        
        # 转换为旧格式（如果需要）
        return {
            'pdf_file': pdf_path,
            'total_pages': stats['total_pages'],
            'stats': stats
        }
```

### 3. 配置文件化

**配置文件**：`data_check_tools/smart_parser_config.yaml`

```yaml
# 智能PDF解析器配置

# 通用设置
general:
  use_gpu: false
  lang: 'ch'
  confidence_threshold: 0.6
  dpi: 300

# 版面分析
layout_analysis:
  enable_table_detection: true
  enable_text_detection: true
  min_table_area: 10000  # 最小表格面积（像素）

# 表格提取
table_extraction:
  auto_detect_header: true
  fill_merged_cells: true

# 输出设置
output:
  excel_format: 'xlsx'
  txt_encoding: 'utf-8'
  json_indent: 2
```

**加载配置**：
```python
import yaml

def load_config(config_path='smart_parser_config.yaml'):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
```

---

## 风险评估与回滚方案

### 风险矩阵

| 风险 | 概率 | 影响 | 等级 | 应对措施 |
|------|------|------|------|---------|
| PP-Structure模型下载失败 | 中 | 高 | 🔴 | 提供离线模型包、重试机制 |
| 复杂表格识别不准确 | 低 | 中 | 🟡 | 输出HTML供人工校验 |
| 内存溢出（大PDF） | 低 | 高 | 🔴 | 逐页处理、分批加载 |
| GPU兼容性问题 | 中 | 低 | 🟢 | 默认CPU模式、优雅降级 |
| 性能不达预期 | 中 | 中 | 🟡 | 优化批处理、异步处理 |

### 详细应对策略

#### 风险1：PP-Structure模型下载失败

**症状**：
```
ConnectionError: Failed to download model
```

**应对**：

1. **离线模型包**：
   - 提前下载模型文件
   - 打包为`paddleocr_models.zip`
   - 提供手动解压说明

2. **重试机制**：
```python
import time

def init_with_retry(max_retries=3):
    for attempt in range(max_retries):
        try:
            engine = PPStructure(...)
            return engine
        except Exception as e:
            print(f"尝试 {attempt+1}/{max_retries} 失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)  # 等待5秒后重试
            else:
                raise
```

3. **清晰的错误提示**：
```python
except ImportError:
    print("❌ PP-Structure初始化失败")
    print("解决方案:")
    print("  1. 检查网络连接")
    print("  2. 手动下载模型: https://paddleocr.bj.bcebos.com/...")
    print("  3. 放置到 ~/.paddleocr/ 目录")
```

#### 风险2：复杂表格识别不准确

**症状**：
- 合并单元格还原错误
- 列数不一致

**应对**：

1. **置信度标记**：
```python
# 在metadata.json中标记低置信度表格
{
  "page": 5,
  "table_index": 2,
  "confidence": 0.72,  # < 0.8 标记为需要人工校验
  "needs_review": true
}
```

2. **输出HTML备份**：
```python
# 同时保存原始HTML
html_backup_dir = output_dir / "html_backups"
html_backup_dir.mkdir(exist_ok=True)

for table_info in tables_data:
    html_path = html_backup_dir / f"Page_{table_info['page']}_Table_{table_info['table_index']}.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(table_info['original_html'])
```

3. **人工校验工具**（后续迭代）：
   - Web界面展示HTML和DataFrame对比
   - 支持手动修正

#### 风险3：内存溢出

**症状**：
```
MemoryError: Unable to allocate array
```

**应对**：

1. **逐页处理并及时释放**：
```python
def process_pdf_batch(self, pdf_path, batch_size=10):
    """分批处理PDF"""
    images = self.pdf_to_images(pdf_path)
    
    for i in range(0, len(images), batch_size):
        batch = images[i:i+batch_size]
        # 处理批次
        self.process_batch(batch)
        
        # 显式释放内存
        del batch
        import gc
        gc.collect()
```

2. **监控内存使用**：
```python
import psutil

def check_memory():
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    
    if memory_mb > 1500:  # 超过1.5GB告警
        print(f"⚠️ 内存使用过高: {memory_mb:.0f}MB")
```

3. **分页批处理选项**：
```python
parser = SmartPDFParser()
stats = parser.process_pdf(pdf_path, batch_size=5)  # 每批处理5页
```

#### 风险4：性能不达预期

**症状**：
- 单页处理时间 > 5秒
- 30页PDF耗时 > 150秒

**应对**：

1. **批处理优化**：
```python
# PaddleOCR支持批处理
self.ocr = PaddleOCR(
    rec_batch_num=6,  # 增加批处理数量
    ...
)
```

2. **降低分辨率**：
```python
# DPI从300降到200（速度提升30%，精度损失<5%）
images = self.pdf_to_images(pdf_path, dpi=200)
```

3. **异步处理**（高级）：
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def process_pages_async(self, images):
    """异步处理多页"""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            loop.run_in_executor(executor, self.process_single_page, img)
            for img in images
        ]
        results = await asyncio.gather(*futures)
    return results
```

### 回滚方案

**触发条件**：
- 新版本连续3次处理失败
- 准确率低于80%
- 性能下降超过50%

**回滚步骤**：

1. **代码回滚**：
```bash
git checkout HEAD~1  # 回退到上一版本
```

2. **切换回旧方案**：
```python
# 修改调用代码
from pdf_ocr_processor import PDFOCRProcessor  # 改回旧版
# from smart_pdf_parser import SmartPDFParser
```

3. **通知用户**：
   - 邮件/公告说明回滚原因
   - 提供预计修复时间

4. **问题排查**：
   - 分析日志定位问题
   - 修复后重新测试

---

## 时间估算

### 总体时间：**24.5小时**（约3个工作日）

| 阶段 | 任务 | 耗时 | 累计 |
|------|------|------|------|
| **前置准备** | 环境配置、依赖安装 | 1.5小时 | 1.5h |
| | 项目结构规划 | 0.5小时 | 2h |
| **模块开发** | 模块1: DocumentLayoutAnalyzer | 4小时 | 6h |
| | 模块2: ElementClassifier | 2小时 | 8h |
| | 模块3: TableStructureExtractor | 3小时 | 11h |
| | 模块4: ArticleTextExtractor | 2小时 | 13h |
| | 模块5: SeparatedOutputManager | 3小时 | 16h |
| | 模块6: SmartPDFParser | 5小时 | 21h |
| **测试** | 单元测试编写 | 2小时 | 23h |
| | 集成测试与性能测试 | 1.5小时 | 24.5h |

### 每日计划

**Day 1（8小时）**：
- 上午：环境配置、依赖安装（1.5h）
- 上午：模块1开发（4h）
- 下午：模块2开发（2h）
- 下午：模块1-2测试（0.5h）

**Day 2（8小时）**：
- 上午：模块3开发（3h）
- 上午：模块4开发（2h）
- 下午：模块5开发（3h）

**Day 3（8.5小时）**：
- 上午：模块6开发（5h）
- 下午：集成测试（1.5h）
- 下午：单元测试补充（2h）

### 缓冲时间

建议预留**20%缓冲时间**（约5小时）用于：
- 调试和问题修复
- 文档编写
- 代码审查

**总计**：24.5 + 5 = **29.5小时**（约4个工作日）

---

## 验收标准

### 功能验收

- [ ] 能正确处理30页测试PDF（2023名额分配结果.pdf）
- [ ] 生成三个输出文件（.xlsx, .txt, .json）
- [ ] Excel中每个表格单独一个Sheet，命名规范
- [ ] TXT文件中段落顺序正确，页码标记清晰
- [ ] JSON包含完整的元数据和元素位置信息
- [ ] 表格列数对齐，无错位现象
- [ ] 合并单元格正确还原

### 性能验收

- [ ] 单页处理时间 ≤ 5秒（CPU, Intel i5）
- [ ] 30页PDF总处理时间 ≤ 150秒
- [ ] 内存峰值 ≤ 2GB
- [ ] 支持批量处理（≥ 100页）

### 质量验收

- [ ] 表格检测准确率 ≥ 90%
- [ ] 单元格识别准确率 ≥ 95%
- [ ] 文章提取准确率 ≥ 85%
- [ ] 单元测试覆盖率 ≥ 85%
- [ ] 无Critical级别Bug

### 文档验收

- [ ] 每个模块有完整的docstring
- [ ] 关键函数有使用示例
- [ ] README包含安装和使用说明
- [ ] 常见问题FAQ文档

### 代码规范验收

- [ ] 遵循PEP 8编码规范
- [ ] 变量命名有意义
- [ ] 无硬编码魔法数字
- [ ] 异常处理完善
- [ ] 日志记录清晰

---

## 附录

### A. 快速开始命令

```bash
# 1. 安装依赖
cd e:\Python\gz_zhongkao_advisor
D:\Tools\miniconda3\python.exe -m pip install -r requirements.txt

# 2. 运行测试
cd data_check_tools
D:\Tools\miniconda3\python.exe -m pytest test_smart_parser/ -v

# 3. 处理PDF
D:\Tools\miniconda3\python.exe run_smart_parser.py ../data/2023名额分配结果.pdf

# 4. 查看输出
ls ../data/ocr_output_smart/
```

### B. 常见问题

**Q1: 模型下载太慢怎么办？**

A: 使用国内镜像或手动下载：
```bash
# 清华大学镜像
pip install paddlepaddle -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**Q2: 如何处理超大PDF（>100页）？**

A: 使用分批处理：
```python
parser = SmartPDFParser()
stats = parser.process_pdf(pdf_path, batch_size=10)
```

**Q3: 表格识别不准确怎么办？**

A: 
1. 检查置信度阈值（降低到0.5）
2. 查看HTML备份文件
3. 人工校验后反馈

### C. 参考资源

1. [PaddleOCR官方文档](https://github.com/PaddlePaddle/PaddleOCR)
2. [PP-Structure使用说明](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.7/ppstructure/README_ch.md)
3. [PaddlePaddle安装指南](https://www.paddlepaddle.org.cn/install/quick)

### D. 变更日志

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-05-03 | 初始版本 | AI Assistant |

---

**文档结束**

**下一步行动**：
1. ✅ 评审本实施计划
2. ⏳ 开始前置准备（环境配置）
3. ⏳ 按模块顺序开始开发
4. ⏳ 每日站会同步进度
5. ⏳ 完成后进行验收测试