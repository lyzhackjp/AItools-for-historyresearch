# 古典籍OCR训练数据准备工作流模块

## 文档信息

| 属性 | 内容 |
|------|------|
| 模块名称 | classical_ocr_training_workflow |
| 版本 | 1.0.0 |
| 创建日期 | 2026-03-31 |
| 文档性质 | 集成文档 |

## 概述

本模块是古典OCR训练资料准备阶段的核心组件，集成了版面分析、日期匹配和训练数据生成功能。该模块作为现有OCR处理流程的扩展，专门用于处理古典籍史料PDF，生成用于OCR模型训练的标准数据集。

## 在整体流程中的位置

```
┌─────────────────────────────────────────────────────────────────┐
│                    OCR处理流程总览                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  PDF输入     │ -> │  PDF预处理   │ -> │  图像提取    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                   │             │
│                                                   v             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │          古典籍OCR训练数据准备工作流 (本模块)            │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │   │
│  │  │ 版面分析   │->│ 内容分类   │->│ 日期提取   │         │   │
│  │  └────────────┘  └────────────┘  └────────────┘         │   │
│  │         │              │              │                  │   │
│  │         v              v              v                  │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │   │
│  │  │ 文本行检测 │  │ 手写体识别 │  │ 日期匹配   │         │   │
│  │  └────────────┘  └────────────┘  └────────────┘         │   │
│  │         │              │              │                  │   │
│  │         v              v              v                  │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │   │
│  │  │ 图像切割   │  │ 标注生成   │  │ 数据验证   │         │   │
│  │  └────────────┘  └────────────┘  └────────────┘         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                   │             │
│                                                   v             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  训练数据集  │ -> │  模型训练   │ -> │  模型评估   │        │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 核心功能

### 1. 版面分析 (LayoutDetector)

使用RTMDet模型检测PDF页面中的文本行区域。

**功能特点：**
- 自动检测文本行边界框
- 支持竖排文本检测
- 置信度阈值可配置

**输入/输出：**
```python
# 输入
img: np.ndarray  # 页面图像 (H, W, 3)

# 输出
detections: List[Dict]  # 检测结果列表
# [{'box': [x1, y1, x2, y2], 'confidence': 0.95, 'class_name': 'line_main'}, ...]
```

### 2. 内容分类 (ContentClassifier)

将检测到的文本行分类为不同类型。

**分类类别：**
| 类别 | 说明 | 识别特征 |
|------|------|----------|
| printed_date | 印刷体日期 | 包含年号日期格式 |
| printed_weather | 印刷体天气 | 包含天气关键词 |
| printed_quote | 印刷体引用 | 包含引用符号 |
| handwritten | 手写内容 | 其他文本 |
| unknown | 未知类型 | 空文本或无法识别 |

### 3. 文本识别 (TextRecognizer)

使用PARSeq模型识别文本行图像中的文字。

**功能特点：**
- 支持古典籍文字识别
- 自动处理竖排文本
- 输出识别文本和置信度

### 4. 日期解析 (DateParser)

从文本中解析日本年号日期。

**支持格式：**
- 明治三十六年一月十八日
- 大正十年五月五日
- 昭和二十年八月十五日
- 一月十八日（需要年号上下文）

**转换规则：**
```python
# 年号转西历
明治 -> 1868 + era_year - 1
大正 -> 1912 + era_year - 1
昭和 -> 1926 + era_year - 1
```

### 5. 训练数据生成

生成标准格式的训练数据集。

**输出格式：**
```json
[
  {
    "image_path": "/path/to/line_image.png",
    "annotation_text": "识别的文本内容",
    "source_page": 1,
    "date_key": "1903-01-18",
    "box": [x1, y1, x2, y2],
    "confidence": 0.95,
    "content_type": "handwritten"
  }
]
```

## API接口

### ClassicalOCRTrainingWorkflow

主要工作流类，整合所有处理步骤。

**初始化：**
```python
from modules.classical_ocr_training_workflow import (
    ClassicalOCRTrainingWorkflow, create_default_config
)

# 使用默认配置
config = create_default_config()
workflow = ClassicalOCRTrainingWorkflow(config)

# 自定义配置
config = {
    'rtmdet_model': '/path/to/rtmdet.onnx',
    'parseq_model': '/path/to/parseq.onnx',
    'rtmdet_config': '/path/to/ndl.yaml',
    'parseq_config': '/path/to/NDLmoji.yaml'
}
workflow = ClassicalOCRTrainingWorkflow(config)
```

**完整工作流：**
```python
result = workflow.run_full_workflow(
    source_pdf="/path/to/source.pdf",      # 原始史料PDF
    annotation_pdf="/path/to/annotation.pdf",  # 翻刻版PDF
    output_dir="/path/to/output",          # 输出目录
    start_page=1,                          # 起始页码
    end_page=10,                           # 结束页码
    target_era_year=36                     # 目标明治年份
)

print(result['success'])  # 是否成功
print(result['source_result']['data']['total_training_samples'])  # 训练样本数
```

**分步处理：**
```python
# 仅处理原始史料PDF
source_result = workflow.process_source_pdf(
    pdf_path="/path/to/source.pdf",
    output_dir="/path/to/output",
    start_page=1,
    end_page=10,
    target_era_year=36
)

# 日期匹配
match_result = workflow.match_with_annotation(
    source_dates=source_result.data['dates'],
    annotation_pdf_path="/path/to/annotation.pdf",
    target_era_year=36
)
```

### 命令行接口

```bash
python -m modules.classical_ocr_training_workflow \
    --source-pdf /path/to/source.pdf \
    --annotation-pdf /path/to/annotation.pdf \
    --output /path/to/output \
    --start-page 1 \
    --end-page 10 \
    --era-year 36
```

## 输出文件结构

```
output_dir/
├── handwritten_images/          # 手写文本行图像
│   ├── page_0001/
│   │   ├── line_0000.png
│   │   ├── line_0001.png
│   │   └── ...
│   ├── page_0002/
│   └── ...
├── analysis/                    # 页面分析结果
│   ├── page_0001.json
│   ├── page_0002.json
│   └── ...
├── training_samples.json        # 训练样本数据
├── workflow_summary.json        # 工作流摘要
└── final_workflow_result.json   # 最终结果
```

## 与现有模块的集成

### 与ndlkotenocr_lite的集成

本模块使用ndlkotenocr_lite提供的模型：

```python
# 模型路径配置
config = {
    'rtmdet_model': 'external/ndlkotenocr-lite/src/model/rtmdet-s-1280x1280.onnx',
    'parseq_model': 'external/ndlkotenocr-lite/src/model/parseq-ndl-32x384-tiny-10.onnx',
    'rtmdet_config': 'external/ndlkotenocr-lite/src/config/ndl.yaml',
    'parseq_config': 'external/ndlkotenocr-lite/src/config/NDLmoji.yaml'
}
```

### 与OCR处理流程的集成

本模块可以作为现有OCR处理流程的前置步骤：

```python
# 原有流程
from modules.pdf_processor import PDFProcessor
from modules.ocr_processor import OCRProcessor

# 新增：训练数据准备
from modules.classical_ocr_training_workflow import ClassicalOCRTrainingWorkflow

# 1. 先进行训练数据准备
workflow = ClassicalOCRTrainingWorkflow(config)
training_result = workflow.run_full_workflow(...)

# 2. 使用训练数据更新模型
# ...

# 3. 使用更新后的模型进行OCR处理
pdf_processor = PDFProcessor()
ocr_processor = OCRProcessor()
```

## 性能参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| detector_conf_threshold | 0.3 | 检测置信度阈值 |
| detector_input_size | 1024 | 检测模型输入尺寸 |
| recognizer_input_size | (384, 32) | 识别模型输入尺寸 |
| target_image_size | (384, 32) | 输出图像尺寸 |

## 错误处理

模块提供详细的错误信息和处理阶段追踪：

```python
result = workflow.run_full_workflow(...)

if not result['success']:
    # 检查错误信息
    for step_result in result['results']:
        if not step_result['success']:
            print(f"阶段 {step_result['stage']} 失败: {step_result['message']}")
            for error in step_result['errors']:
                print(f"  错误: {error}")
```

## 扩展开发

### 自定义内容分类器

```python
from modules.classical_ocr_training_workflow import LayoutDetector, ContentType

class CustomLayoutDetector(LayoutDetector):
    def classify_content(self, text, box, img):
        # 自定义分类逻辑
        if "特定关键词" in text:
            return "custom_type"
        return super().classify_content(text, box, img)
```

### 自定义日期解析器

```python
from modules.classical_ocr_training_workflow import KanjiNumberConverter

class ExtendedKanjiConverter(KanjiNumberConverter):
    KANJI_NUM = {
        **KanjiNumberConverter.KANJI_NUM,
        '零': 0,  # 添加新的汉字数字
    }
```

## 测试

运行单元测试：

```bash
python -m modules.tests.test_classical_ocr_training_workflow
```

## 更新日志

### v1.0.0 (2026-03-31)
- 初始版本发布
- 集成版面分析功能
- 实现内容分类
- 添加日期解析
- 支持训练数据生成
