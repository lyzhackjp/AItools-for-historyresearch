# NDL古典籍OCR-Lite 集成文档

## 📋 概述

本项目已成功集成 **NDL古典籍OCR-Lite (ndlkotenocr-lite)** 模型，与现有的 **NDL OCR-Lite** 形成完整的OCR处理体系。

### 🎯 核心功能

1. **双模型支持**: 同时支持近代现代文献和古典籍文献的OCR识别
2. **运行时切换**: 可在处理过程中动态选择使用的OCR模型
3. **模型对比**: 支持同时使用两种模型处理同一文档，便于对比效果

---

## 📦 模型介绍

### 1. NDL OCR-Lite (ndlocr_lite)

**用途**: 识别近代现代日本印刷体文献

**适用场景**:
- 近代文献(明治以后)
- 现代文献、新闻、杂志
- 书籍、教科书等印刷体文字
- 近代法令、官报等官方文献

**GitHub**: https://github.com/ndl-lab/ndlocr-lite

**特点**:
- 专为日文现代印刷体优化
- 处理速度快
- 识别精度高

---

### 2. NDL古典籍OCR-Lite (ndlkotenocr_lite)

**用途**: 识别古典籍资料(江戸期以前的和古書、清代以前的漢籍)

**适用场景**:
- 江戸期以前的古典籍
- 清代以前的漢籍(中文古典文献)
- 草书字(くせ字)
- 和古書(わこしょ)
- 手写体文献

**GitHub**: https://github.com/ndl-lab/ndlkotenocr-lite

**特点**:
- 专门针对古典籍资料优化
- 支持草书字、日文汉字、平假名、片假名混合识别
- CPU环境下可高速运行(无需GPU)
- 比NDL古典籍OCR ver.3精度稍低约2%

---

## 🔧 安装配置

### 1. 环境要求

- Python 3.10+
- Windows 10+ / macOS Sequoia / Linux Ubuntu 22.04+
- 推荐8GB+内存
- CPU环境下可运行(无需GPU)

### 2. 依赖安装

ndlkotenocr-lite的依赖已包含在项目requirements中:

```bash
pip install -r external/ndlkotenocr-lite/requirements.txt
```

主要依赖:
- onnxruntime (CPU推理)
- Pillow (图像处理)
- PyYAML (配置文件)
- lxml (XML处理)

### 3. 模型文件

模型文件位于: `external/ndlkotenocr-lite/src/model/`

- `rtmdet-s-1280x1280.onnx` - 布局检测模型
- `parseq-ndl-32x384-tiny-10.onnx` - 文字识别模型

配置文件位于: `external/ndlkotenocr-lite/src/config/`

- `ndl.yaml` - 布局检测配置
- `NDLmoji.yaml` - 字符集配置

---

## 💻 编程接口

### 1. 使用统一OCR处理器

```python
from modules.unified_ocr_processor import UnifiedOCRProcessor, UnifiedOCRConfig

config = UnifiedOCRConfig(
    ndlocr_path='external/ndlocr-lite/src/ocr.py',
    ndlkoten_path='external/ndlkotenocr-lite/src/ocr.py',
    default_model='ndlocr_lite'
)

processor = UnifiedOCRProcessor(config)

result = processor.process_image(
    image_path='path/to/image.jpg',
    model_type='ndlkotenocr_lite'
)

print(result.text)
```

### 2. 查看可用模型

```python
available_models = processor.get_available_models()
for model in available_models:
    print(f"{model['type']}: {model['name_cn']}")
    print(f"  用途: {model['use_case']}")
    print(f"  可用: {model['available']}")
```

### 3. 对比两种模型

```python
results = processor.compare_models('path/to/image.jpg')

for model_type, result in results.items():
    print(f"\n{model_type}:")
    print(f"  识别结果: {result.text[:100]}...")
    print(f"  处理时间: {result.processing_time:.2f}秒")
```

---

## 🌐 API接口

### 1. 获取所有OCR模型

```
GET /api/ocr/models
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "models": [
      {
        "type": "ndlocr_lite",
        "name": "NDL OCRlite",
        "name_cn": "NDL OCR(近代现代文献)",
        "description": "用于识别近代现代日本印刷体文献",
        "use_case": "近代文献、现代文献、新闻、杂志、书籍等印刷体文字",
        "available": true
      },
      {
        "type": "ndlkotenocr_lite",
        "name": "NDL古典籍OCR-Lite",
        "name_cn": "NDL古典籍OCR(古典籍文献)",
        "description": "用于识别古典籍资料(江戸期以前的和古書、清代以前的漢籍)",
        "use_case": "江戸期以前の古典籍、漢籍、草书字、和古書等",
        "available": true
      }
    ],
    "default_model": "ndlocr_lite"
  }
}
```

### 2. 使用指定模型OCR处理

```
POST /api/ocr/model/process
Content-Type: multipart/form-data

参数:
- file: 图片文件
- model_type: 模型类型 ('ndlocr_lite' 或 'ndlkotenocr_lite')
```

**请求示例**:
```bash
curl -X POST http://localhost:5000/api/ocr/model/process \
  -F "file=@document.jpg" \
  -F "model_type=ndlkotenocr_lite"
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "text": "古典籍识别结果...",
    "pages": [...],
    "structures": [...],
    "processing_time": 12.34,
    "model_type": "ndlkotenocr_lite",
    "model_description": "NDL古典籍OCR(古典籍文献)"
  },
  "method": "ndlkotenocr_lite",
  "message": "NDL古典籍OCR(古典籍文献)识别成功"
}
```

### 3. 对比两种模型

```
POST /api/ocr/model/compare
Content-Type: multipart/form-data

参数:
- file: 图片文件
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "comparison": {
      "ndlocr_lite": {
        "success": true,
        "text": "近代文献识别结果...",
        "processing_time": 8.5,
        "model_description": "NDL OCR(近代现代文献)"
      },
      "ndlkotenocr_lite": {
        "success": true,
        "text": "古典籍识别结果...",
        "processing_time": 12.3,
        "model_description": "NDL古典籍OCR(古典籍文献)"
      }
    },
    "file_analyzed": "document.jpg"
  },
  "message": "模型对比完成"
}
```

---

## 📖 使用场景

### 场景1: 近代文献处理

```python
processor = UnifiedOCRProcessor()

result = processor.process_image(
    image_path='modern_document.jpg',
    model_type='ndlocr_lite'
)
```

**适用**:
- 明治以后的书籍
- 近代报纸
- 现代杂志
- 战后文献

---

### 场景2: 古典籍处理

```python
processor = UnifiedOCRProcessor()

result = processor.process_image(
    image_path='classical_manuscript.jpg',
    model_type='ndlkotenocr_lite'
)
```

**适用**:
- 江户时代的古籍
- 手写体文献
- 汉文典籍
- 草书体文献

---

### 场景3: 不确定文献类型

```python
processor = UnifiedOCRProcessor()

results = processor.compare_models('unknown_document.jpg')

for model_type, result in results.items():
    print(f"\n{model_type}: {result.text[:200]}...")

print("\n请根据实际效果选择合适的模型")
```

---

## ⚙️ 配置选项

### 环境变量配置

在 `.env` 文件中配置:

```env
NDLKOTENOCR_LITE_PATH=external/ndlkotenocr-lite/src/ocr.py
NDLKOTENOCR_LITE_GPU=false
NDLKOTENOCR_LITE_VIZ=false
NDLKOTENOCR_LITE_TIMEOUT=300

DEFAULT_OCR_MODEL=ndlocr_lite
```

### 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| NDLKOTENOCR_LITE_PATH | ndlkotenocr-lite路径 | 空(自动检测) |
| NDLKOTENOCR_LITE_GPU | 是否使用GPU | false |
| NDLKOTENOCR_LITE_VIZ | 是否生成可视化图像 | false |
| NDLKOTENOCR_LITE_TIMEOUT | 处理超时时间(秒) | 300 |
| DEFAULT_OCR_MODEL | 默认OCR模型 | ndlocr_lite |

---

## 🎯 选择指南

### 如何选择合适的模型?

#### 选择 NDL OCR-Lite (ndlocr_lite) 如果:

- ✅ 文献年代较近(明治以后)
- ✅ 印刷质量较好
- ✅ 字体为现代印刷体
- ✅ 需要更快的处理速度
- ✅ 文献为横向排版

#### 选择 NDL古典籍OCR-Lite (ndlkotenocr_lite) 如果:

- ✅ 文献年代较早(江户时代以前)
- ✅ 手写体或草书字
- ✅ 包含大量古典汉字
- ✅ 竖排版文献
- ✅ 需要识别古典日语

#### 不确定时:

使用 `/api/ocr/model/compare` 对比两种模型的结果，选择效果更好的。

---

## 🔍 技术细节

### 模型架构

NDL古典籍OCR-Lite包含三个主要模块:

1. **布局检测 (RTMDet)**
   - 检测文本区域、图表等
   - 识别文字方向(横排/竖排)

2. **文字识别 (PARSEQ)**
   - 识别具体文字内容
   - 支持多种字符类型混合

3. **读序整序**
   - 确定文字阅读顺序
   - 处理竖排文字

### 输出格式

处理结果包含:

- `.txt` - 纯文本输出
- `.xml` - 结构化XML输出(包含位置信息)
- `.json` - JSON格式输出
- `_tei.xml` - TEI格式输出
- `viz_*.jpg` - 可视化图像(可选)

---

## ⚠️ 注意事项

1. **性能要求**: 建议8GB以上内存，处理时间约10-30秒/页

2. **文件格式**: 支持JPG、PNG、TIFF、JP2、BMP格式

3. **图像质量**: 图像质量直接影响识别精度，建议300DPI以上

4. **竖排文字**: NDL古典籍OCR-Lite专门优化了竖排文字识别

5. **草书字**: 草书字识别效果可能因具体字体而异

6. **模型更新**: 建议定期更新模型以获得最佳效果

---

## 📚 参考资源

### 官方文档
- NDL古典籍OCR-Lite: https://github.com/ndl-lab/ndlkotenocr-lite
- NDL OCR-Lite: https://github.com/ndl-lab/ndlocr-lite

### 相关论文
- 青池亨. "CPU環境で高速に動作する軽量OCR「NDL古典籍OCR-Lite」の開発"
- 人文科学とコンピュータ_symposium論文集 (じんもんこん2024)

### 学术资源
- 古典籍資料のOCRテキスト化実験
- OCR学習用データセット（みんな翻刻）

---

## ✅ 验证清单

- [x] ndlkotenocr-lite已下载并配置
- [x] 依赖已安装
- [x] 模块集成完成
- [x] API接口可用
- [x] 文档已创建

---

**集成完成时间**: 2026-03-28

**版本**: 1.2.0

**状态**: ✅ 运行正常
