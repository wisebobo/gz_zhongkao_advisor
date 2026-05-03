# PDF OCR 智能文档解析系统设计文档

**版本**: v1.0  
**日期**: 2026-04-30  
**作者**: AI Assistant  
**状态**: ✅ 已批准，待实施

---

## 📋 目录

1. [项目概述](#项目概述)
2. [需求分析](#需求分析)
3. [技术方案](#技术方案)
4. [系统架构](#系统架构)
5. [核心模块设计](#核心模块设计)
6. [数据流设计](#数据流设计)
7. [输出格式规范](#输出格式规范)
8. [性能指标](#性能指标)
9. [实施计划](#实施计划)
10. [风险与应对](#风险与应对)

---

## 项目概述

### 背景

当前PDF OCR识别程序（`pdf_ocr_processor.py` + `reconstruct_tables.py`）存在以下问题：

1. **列数不一致**：某些行单元格多，某些行少，导致表格错位
2. **换行识别错误**：单元格内换行被识别为独立行
3. **混合文档处理能力弱**：无法区分文章段落和表格区域
4. **输出格式单一**：仅生成简单文本列表，未保持原始结构

### 目标

构建基于PaddleOCR PP-Structure的智能PDF文档解析系统，实现：

- ✅ 自动检测PDF页面类型（纯文章/纯表格/混合）
- ✅ 高精度表格结构识别（支持合并单元格）
- ✅ 智能分离文章和表格内容
- ✅ 分离式输出（文章→TXT，表格→Excel，元数据→JSON）

### 适用范围

- **主要场景**：广州中考招生数据PDF（结构化表格为主）
- **扩展场景**：政策文件、混合文档（文章+表格）、复杂报表

---

## 需求分析

### 功能需求

#### FR1: 智能版面分析
- **描述**：自动识别PDF每页的内容类型
- **输入**：PDF页面图片
- **输出**：元素列表（含类型标签：text/title/table/figure）
- **验收标准**：
  - 表格检测准确率 ≥ 90%
  - 文章段落检测准确率 ≥ 85%
  - 处理速度 ≤ 3秒/页（CPU）

#### FR2: 表格结构识别
- **描述**：提取表格的行列结构和单元格内容
- **输入**：表格区域图片
- **输出**：结构化DataFrame（含合并单元格信息）
- **验收标准**：
  - 单元格识别准确率 ≥ 95%
  - 合并单元格正确还原
  - 列数自动对齐（不足补空值）

#### FR3: 文章内容提取
- **描述**：提取并整理文章段落文本
- **输入**：文章区域元素列表
- **输出**：格式化文本（保持阅读顺序）
- **验收标准**：
  - 段落顺序正确（从上到下）
  - 去除页眉页脚噪声
  - 保留段落间距

#### FR4: 分离式输出
- **描述**：生成三种类型的输出文件
- **输出**：
  - `{pdf_name}_tables.xlsx`：所有表格（每个表格一个Sheet）
  - `{pdf_name}_articles.txt`：所有文章内容
  - `{pdf_name}_metadata.json`：元数据（位置、类型等）
- **验收标准**：
  - Excel文件格式正确，可直接打开
  - TXT文件编码UTF-8，可读性好
  - JSON包含完整的元素位置信息

### 非功能需求

#### NFR1: 性能要求
- 单页处理时间 ≤ 5秒（CPU环境）
- 内存占用 ≤ 2GB
- 支持批量处理（≥ 100页PDF）

#### NFR2: 兼容性
- Python 3.8+
- Windows/Linux/macOS
- CPU/GPU均可运行

#### NFR3: 可维护性
- 模块化设计，各模块独立可测试
- 提供详细日志和错误提示
- 配置文件化（阈值、参数可调）

---

## 技术方案

### 核心技术栈

| 组件 | 技术选型 | 版本 | 说明 |
|------|---------|------|------|
| OCR引擎 | PaddleOCR PP-StructureV3 | 2.10.0 | 文档版面分析+表格识别 |
| 深度学习框架 | PaddlePaddle | 2.6.2 | CPU/GPU支持 |
| PDF处理 | PyMuPDF (fitz) | 最新 | PDF转图片 |
| HTML解析 | BeautifulSoup4 | 最新 | 解析表格HTML |
| 数据处理 | Pandas | 最新 | DataFrame操作 |
| Excel输出 | openpyxl | 最新 | Excel文件生成 |

### 为什么选择PP-Structure？

**优势对比**：

| 特性 | 自研坐标算法 | PP-Structure |
|------|------------|-------------|
| 开发周期 | 2-3周 | 3-5天 |
| 表格检测准确率 | 70-80% | 90-95% |
| 合并单元格支持 | ❌ 需手动实现 | ✅ 原生支持 |
| 混合文档处理 | ⚠️ 规则复杂 | ✅ 自动分类 |
| 维护成本 | 高（规则调优） | 低（模型优化） |
| 适用场景 | 简单表格 | 复杂布局 |

**结论**：PP-Structure是成熟的生产级方案，大幅降低开发成本，提升识别准确率。

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────┐
│           SmartPDFParser (主控制器)          │
└──────┬──────────┬──────────┬────────────────┘
       │          │          │
       ↓          ↓          ↓
┌──────────┐ ┌──────────┐ ┌──────────────┐
│ Layout   │ │ Element  │ │ Table        │
│ Analyzer │ │Classifier│ │ Extractor    │
│          │ │          │ │              │
│ PP-      │ │ 过滤/    │ │ HTML→DF      │
│ Structure│ │ 分类     │ │ 合并单元格    │
└──────────┘ └──────────┘ └──────────────┘
       │          │          │
       ↓          ↓          ↓
┌─────────────────────────────────────────────┐
│         SeparatedOutputManager               │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Tables   │ │ Articles │ │ Metadata    │ │
│  │ .xlsx    │ │ .txt     │ │ .json       │ │
│  └──────────┘ └──────────┘ └─────────────┘ │
└─────────────────────────────────────────────┘
```

### 模块依赖关系

```
SmartPDFParser
  ├── DocumentLayoutAnalyzer (依赖: paddleocr.PPStructure)
  ├── ElementClassifier (无外部依赖)
  ├── TableStructureExtractor (依赖: bs4, pandas)
  ├── ArticleTextExtractor (无外部依赖)
  └── SeparatedOutputManager (依赖: pandas, openpyxl)
```

---

## 核心模块设计

### 模块1: DocumentLayoutAnalyzer

**职责**：使用PP-Structure进行页面元素检测和分类

**接口定义**：

```python
class DocumentLayoutAnalyzer:
    def __init__(self, use_gpu=False, lang='ch', confidence_threshold=0.6):
        """
        Args:
            use_gpu: 是否使用GPU加速
            lang: 识别语言 ('ch'/'en'/'multi')
            confidence_threshold: 置信度阈值
        """
    
    def analyze_page(self, image: np.ndarray) -> List[Dict]:
        """
        分析单页布局
        
        Args:
            image: RGB图像数组 (H, W, 3)
            
        Returns:
            elements: [
                {
                    'type': 'text' | 'title' | 'table' | 'figure',
                    'bbox': [x1, y1, x2, y2],
                    'res': {
                        'text': str,      # 识别文本
                        'html': str       # 表格HTML（仅table类型）
                    },
                    'confidence': float
                },
                ...
            ]
        """
```

**关键实现细节**：

1. **PP-Structure初始化**：
```python
from paddleocr import PPStructure

self.engine = PPStructure(
    show_log=False,
    recovery=True,      # 保留表格结构
    lang=lang,
    use_gpu=use_gpu,
    table=True,         # 启用表格识别
    ocr=True            # 同时启用OCR
)
```

2. **结果后处理**：
- 过滤置信度 < threshold 的元素
- 标准化bbox格式（确保[x1,y1,x2,y2]）
- 提取关键字段（type, text, html）

**测试用例**：
- 输入：纯表格页面图片 → 输出：1个table元素
- 输入：纯文章页面图片 → 输出：多个text元素
- 输入：混合页面图片 → 输出：table + text元素

---

### 模块2: ElementClassifier

**职责**：对PP-Structure的输出进行分类和过滤

**接口定义**：

```python
class ElementClassifier:
    def __init__(self, confidence_threshold=0.6):
        self.confidence_threshold = confidence_threshold
    
    def classify_elements(self, raw_elements: List[Dict]) -> Dict[str, List]:
        """
        分类元素
        
        Returns:
            {
                'tables': [...],      # 表格元素
                'articles': [...],    # 文章段落
                'titles': [...],      # 标题
                'figures': [...]      # 图片
            }
        """
```

**分类逻辑**：

```python
def classify_elements(self, raw_elements):
    classified = {
        'tables': [],
        'articles': [],
        'titles': [],
        'figures': []
    }
    
    for elem in raw_elements:
        # 1. 置信度过滤
        if elem['confidence'] < self.confidence_threshold:
            continue
        
        # 2. 类型映射
        elem_type = elem['type']
        
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

**增强功能**（可选）：
- 合并相邻的同类型元素（如连续段落）
- 检测页眉页脚并过滤

---

### 模块3: TableStructureExtractor

**职责**：将HTML表格转换为DataFrame，处理合并单元格

**接口定义**：

```python
class TableStructureExtractor:
    def html_to_dataframe(self, html_content: str) -> pd.DataFrame:
        """
        HTML表格转DataFrame
        
        Args:
            html_content: HTML字符串
            
        Returns:
            DataFrame: 结构化表格数据
        """
    
    def detect_merged_cells(self, html_content: str) -> List[Tuple]:
        """
        检测合并单元格
        
        Returns:
            [(row_idx, col_idx, rowspan, colspan), ...]
        """
```

**关键实现**：

1. **HTML解析**：
```python
import pandas as pd

def html_to_dataframe(self, html_content):
    # pandas直接解析HTML表格
    dfs = pd.read_html(html_content)
    
    if not dfs:
        return None
    
    df = dfs[0]
    
    # 处理NaN（合并单元格填充）
    df = df.fillna('')
    
    return df
```

2. **合并单元格检测**：
```python
from bs4 import BeautifulSoup

def detect_merged_cells(self, html_content):
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
```

**注意事项**：
- pandas的`read_html`会自动处理简单的合并单元格
- 复杂合并可能需要额外后处理（暂不实现，后续优化）

---

### 模块4: ArticleTextExtractor

**职责**：提取和整理文章段落

**接口定义**：

```python
class ArticleTextExtractor:
    def extract_articles(self, article_elements: List[Dict], page_num: int) -> str:
        """
        提取文章文本
        
        Args:
            article_elements: 文章元素列表
            page_num: 页码
            
        Returns:
            str: 格式化文本
        """
```

**实现逻辑**：

```python
def extract_articles(self, article_elements, page_num):
    # 1. 按Y坐标排序（从上到下）
    sorted_elements = sorted(
        article_elements,
        key=lambda x: x['bbox'][1] if x['bbox'] else 0
    )
    
    # 2. 提取文本
    paragraphs = []
    for elem in sorted_elements:
        text = elem['res'].get('text', '')
        if text.strip():
            paragraphs.append(text.strip())
    
    # 3. 拼接段落
    article_text = '\n\n'.join(paragraphs)
    
    # 4. 添加页码标记
    formatted_text = f"=== 第{page_num}页 ===\n\n{article_text}"
    
    return formatted_text
```

---

### 模块5: SeparatedOutputManager

**职责**：生成最终输出文件

**接口定义**：

```python
class SeparatedOutputManager:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_tables_to_excel(self, tables_data: List[Dict], pdf_name: str) -> Path:
        """保存表格到Excel"""
    
    def save_articles_to_txt(self, articles_data: List[Dict], pdf_name: str) -> Path:
        """保存文章到TXT"""
    
    def save_metadata(self, metadata: Dict, pdf_name: str) -> Path:
        """保存元数据到JSON"""
```

**输出文件结构**：

```
output/
├── {pdf_name}_tables.xlsx
│   ├── Page_1_Table_1
│   ├── Page_1_Table_2
│   ├── Page_2_Table_1
│   └── ...
├── {pdf_name}_articles.txt
└── {pdf_name}_metadata.json
```

**Excel格式示例**：

| Sheet名称 | 内容 |
|----------|------|
| Page_1_Table_1 | 第1页第1个表格 |
| Page_2_Table_1 | 第2页第1个表格 |

**TXT格式示例**：

```
=== 第1页 ===

2023年广州市普通高中名额分配政策说明

根据市教育局规定，...

================================================================================

=== 第2页 ===

以下为各学校名额分配情况：
```

**JSON元数据结构**：

```json
{
  "pdf_name": "2023名额分配结果",
  "total_pages": 30,
  "process_time": "2026-04-30 10:30:00",
  "pages": {
    "1": {
      "tables_count": 1,
      "articles_count": 2,
      "elements": [
        {
          "type": "title",
          "bbox": [100, 50, 500, 80]
        },
        {
          "type": "table",
          "bbox": [50, 100, 800, 600],
          "sheet": "Page_1_Table_1"
        }
      ]
    }
  }
}
```

---

### 模块6: SmartPDFParser（主控制器）

**职责**：整合所有模块，协调整个处理流程

**接口定义**：

```python
class SmartPDFParser:
    def __init__(self, use_gpu=False, lang='ch'):
        self.layout_analyzer = DocumentLayoutAnalyzer(use_gpu, lang)
        self.element_classifier = ElementClassifier()
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
            stats: {
                'total_pages': int,
                'total_tables': int,
                'total_articles': int
            }
        """
```

**处理流程**：

```python
def process_pdf(self, pdf_path, output_dir=None):
    # 步骤1: 初始化
    if output_dir is None:
        output_dir = Path(pdf_path).parent / "ocr_output"
    self.output_manager = SeparatedOutputManager(output_dir)
    
    pdf_name = Path(pdf_path).stem
    
    # 步骤2: PDF转图片
    images = self.pdf_to_images(pdf_path)
    
    # 步骤3: 逐页处理
    all_tables = []
    all_articles = []
    metadata = {...}
    
    for page_num, image in enumerate(images, 1):
        # 3.1 版面分析
        elements = self.layout_analyzer.analyze_page(image)
        
        # 3.2 元素分类
        classified = self.element_classifier.classify_elements(elements)
        
        # 3.3 处理表格
        for idx, table_elem in enumerate(classified['tables'], 1):
            html = table_elem['res'].get('html', '')
            if html:
                df = self.table_extractor.html_to_dataframe(html)
                merged = self.table_extractor.detect_merged_cells(html)
                
                all_tables.append({
                    'page': page_num,
                    'table_index': idx,
                    'dataframe': df,
                    'merged_cells': merged
                })
        
        # 3.4 处理文章
        if classified['articles']:
            article_text = self.article_extractor.extract_articles(
                classified['articles'], page_num
            )
            all_articles.append({'page': page_num, 'text': article_text})
        
        # 3.5 记录元数据
        metadata['pages'][str(page_num)] = {...}
    
    # 步骤4: 生成输出文件
    if all_tables:
        self.output_manager.save_tables_to_excel(all_tables, pdf_name)
    
    if all_articles:
        self.output_manager.save_articles_to_txt(all_articles, pdf_name)
    
    self.output_manager.save_metadata(metadata, pdf_name)
    
    # 步骤5: 返回统计
    return {
        'total_pages': len(images),
        'total_tables': len(all_tables),
        'total_articles': len(all_articles)
    }
```

**辅助方法**：

```python
def pdf_to_images(self, pdf_path: str, dpi=300) -> List[np.ndarray]:
    """PDF转图片"""
    import fitz
    
    doc = fitz.open(pdf_path)
    images = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # 转换为numpy数组
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        img_array = np.array(img)
        
        images.append(img_array)
    
    doc.close()
    return images
```

---

## 数据流设计

### 完整数据流图

```
PDF文件
  ↓
[PDF转图片] PyMuPDF
  ↓
图片数组 (RGB, H×W×3)
  ↓
[版面分析] PP-Structure
  ↓
原始元素列表
  [{type, bbox, res, confidence}, ...]
  ↓
[元素分类] ElementClassifier
  ↓
分类结果
  {
    tables: [...],
    articles: [...],
    titles: [...],
    figures: [...]
  }
  ↓
  ├─→ [表格提取] TableStructureExtractor
  │     ↓
  │   HTML → DataFrame
  │     ↓
  │   结构化表格数据
  │
  └─→ [文章提取] ArticleTextExtractor
        ↓
      格式化文本
  ↓
[输出管理] SeparatedOutputManager
  ↓
  ├─→ tables.xlsx
  ├─→ articles.txt
  └─→ metadata.json
```

### 关键数据结构

#### 1. 元素结构（Element）

```python
{
    'type': 'table',              # 元素类型
    'bbox': [50, 100, 800, 600],  # 边界框 [x1, y1, x2, y2]
    'res': {
        'text': '...',            # 识别文本
        'html': '<table>...</table>'  # 表格HTML
    },
    'confidence': 0.95            # 置信度
}
```

#### 2. 表格数据结构

```python
{
    'page': 1,                    # 页码
    'table_index': 1,             # 表格序号
    'dataframe': pd.DataFrame,    # 表格数据
    'merged_cells': [             # 合并单元格信息
        (0, 0, 1, 2),             # (row, col, rowspan, colspan)
        ...
    ]
}
```

#### 3. 文章数据结构

```python
{
    'page': 1,                    # 页码
    'text': '=== 第1页 ===\n\n...'  # 格式化文本
}
```

---

## 输出格式规范

### Excel输出规范

**文件命名**：`{pdf_name}_tables.xlsx`

**Sheet命名规则**：`Page_{页码}_Table_{序号}`

**格式要求**：
- 第一行为表头（如果检测到）
- 合并单元格用空字符串填充
- 数字保持原始格式（不转换）
- 编码：UTF-8

**示例**：

| 代码 | 初中学校 | 考生人数 | 名额总数 |
|------|---------|---------|---------|
| 010301 | 广州市第一中学 | 392 | 16 |
| 010302 | 广州市第四中学 | 595 | 25 |

---

### TXT输出规范

**文件命名**：`{pdf_name}_articles.txt`

**编码**：UTF-8

**格式**：
```
=== 第{页码}页 ===

{段落1}

{段落2}

================================================================================

=== 第{页码+1}页 ===

...
```

**分隔符**：80个等号

---

### JSON元数据规范

**文件命名**：`{pdf_name}_metadata.json`

**编码**：UTF-8

**结构**：
```json
{
  "pdf_name": "string",
  "total_pages": number,
  "process_time": "YYYY-MM-DD HH:MM:SS",
  "config": {
    "use_gpu": boolean,
    "lang": "string",
    "confidence_threshold": number
  },
  "pages": {
    "{page_num}": {
      "tables_count": number,
      "articles_count": number,
      "elements": [
        {
          "type": "string",
          "bbox": [number, number, number, number]
        }
      ]
    }
  }
}
```

---

## 性能指标

### 目标性能

| 指标 | 目标值 | 测量条件 |
|------|--------|---------|
| 单页处理时间 | ≤ 5秒 | CPU, Intel i5, 16GB RAM |
| 内存占用 | ≤ 2GB | 峰值内存 |
| 表格检测准确率 | ≥ 90% | IoU > 0.5 |
| 单元格识别准确率 | ≥ 95% | 字符级别 |
| 文章提取准确率 | ≥ 85% | 段落完整性 |

### 基准测试计划

**测试数据集**：
1. 2023名额分配结果.pdf（30页，纯表格）
2. 政策文件.pdf（10页，纯文章）
3. 混合文档.pdf（20页，混合）

**测试指标**：
- 处理时间（每页）
- 内存峰值
- 准确率（人工标注对比）

---

## 实施计划

### 阶段1: 核心模块开发（3天）

**Day 1**: 
- [ ] 创建DocumentLayoutAnalyzer模块
- [ ] 测试PP-Structure基本功能
- [ ] 编写单元测试

**Day 2**:
- [ ] 创建ElementClassifier模块
- [ ] 创建TableStructureExtractor模块
- [ ] 测试HTML解析和合并单元格

**Day 3**:
- [ ] 创建ArticleTextExtractor模块
- [ ] 创建SeparatedOutputManager模块
- [ ] 测试输出文件格式

### 阶段2: 集成与测试（2天）

**Day 4**:
- [ ] 创建SmartPDFParser主类
- [ ] 整合所有模块
- [ ] 端到端测试（2023名额分配结果.pdf）

**Day 5**:
- [ ] 性能测试和优化
- [ ] 错误处理和日志完善
- [ ] 编写使用文档

### 阶段3: 文档与交付（1天）

**Day 6**:
- [ ] 编写API文档
- [ ] 编写示例代码
- [ ] 代码审查和重构
- [ ] 提交PR

---

## 风险与应对

### 风险1: PP-Structure模型下载失败

**影响**：无法启动程序  
**概率**：中  
**应对**：
- 提供离线模型包
- 添加重试机制
- 清晰的错误提示和安装指南

### 风险2: 复杂表格识别不准确

**影响**：合并单元格还原错误  
**概率**：低  
**应对**：
- 在metadata.json中标记低置信度表格
- 提供人工校验工具（后续迭代）
- 输出HTML供用户检查

### 风险3: 内存溢出（大PDF）

**影响**：程序崩溃  
**概率**：低  
**应对**：
- 逐页处理，及时释放内存
- 添加分页批处理选项
- 监控内存使用并告警

### 风险4: GPU兼容性问题

**影响**：无法使用GPU加速  
**概率**：中  
**应对**：
- 默认使用CPU模式
- 提供GPU检测和环境配置指南
- 优雅的降级策略

---

## 附录

### A. 依赖清单

```txt
paddlepaddle==2.6.2
paddleocr==2.10.0
PyMuPDF>=1.23.0
beautifulsoup4>=4.12.0
pandas>=2.0.0
openpyxl>=3.1.0
Pillow>=10.0.0
numpy>=1.24.0
```

### B. 参考资源

1. [PaddleOCR官方文档](https://github.com/PaddlePaddle/PaddleOCR)
2. [PP-Structure使用说明](https://github.com/PaddlePaddle/PaddleOCR/blob/release/2.7/ppstructure/README_ch.md)
3. [PaddlePaddle安装指南](https://www.paddlepaddle.org.cn/install/quick)

### C. 术语表

| 术语 | 解释 |
|------|------|
| PP-Structure | PaddleOCR的文档结构化模块 |
| 版面分析 | 检测文档中的不同元素类型（文本、表格、图片等） |
| 合并单元格 | Excel中跨多行或多列的单元格 |
| IoU | Intersection over Union，目标检测评估指标 |

---

**文档结束**
