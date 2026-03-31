# NDL OCR-Lite 集成使用指南

## 📖 概述

本系统集成了日本国立国会图书馆实验室(NDL Lab)开发的 **NDL OCR-Lite** 工具，专门用于日文文献的高精度文字识别。

### NDL OCR-Lite 特点

- 🎯 **专为日文优化**：基于Transformer架构，专门针对日文历史文献训练
- ⚡ **轻量级设计**：无需GPU即可在普通电脑上高速运行
- 📚 **学术级精度**：支持图书、杂志等数字化图像的高质量文本提取
- 🔧 **灵活部署**：支持Windows、Mac、Linux多平台
- 🆓 **开源免费**：采用CC BY 4.0许可证

---

## 🚀 安装指南

### 系统要求

- Python 3.10 或更高版本
- Windows 11 / macOS / Linux
- 推荐 8GB+ 内存
- 可选：支持CUDA的GPU（用于加速）

### 安装步骤

#### 方法一：标准安装（推荐）

```bash
# 1. 克隆NDL OCR-Lite仓库
git clone https://github.com/ndl-lab/ndlocr-lite

# 2. 进入目录
cd ndlocr-lite

# 3. 安装依赖
pip install -r requirements.txt

# 4. 进入src目录
cd src

# 5. 测试安装
python3 ocr.py --help
```

#### 方法二：使用uv工具安装

```bash
# 1. 克隆仓库
git clone https://github.com/ndl-lab/ndlocr-lite
cd ndlocr-lite

# 2. 使用uv安装
uv tool install .

# 3. 测试安装
ndlocr-lite --help
```

### 验证安装

```bash
# 进入src目录
cd ndlocr-lite/src

# 测试帮助命令
python3 ocr.py --help
```

如果显示帮助信息，说明安装成功。

---

## ⚙️ 配置指南

### 环境变量配置

编辑项目根目录的 `.env` 文件：

```env
# NDL OCR-Lite 配置
NDLOCR_LITE_PATH=                    # ndlocr-lite安装路径（可选）
NDLOCR_LITE_GPU=false               # 是否启用GPU加速
NDLOCR_LITE_VIZ=false               # 是否生成可视化结果
NDLOCR_LITE_TIMEOUT=300             # 处理超时时间（秒）
```

### 配置说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `NDLOCR_LITE_PATH` | 自动检测 | ndlocr-lite可执行文件路径 |
| `NDLOCR_LITE_GPU` | `false` | 设为`true`启用GPU加速（需要CUDA环境） |
| `NDLOCR_LITE_VIZ` | `false` | 设为`true`生成识别结果可视化图片 |
| `NDLOCR_LITE_TIMEOUT` | `300` | 单个文件处理超时时间（秒） |

---

## 📚 API接口

### 1. NDL OCR-Lite识别

```
POST /api/ocr/ndlocr-lite
Content-Type: multipart/form-data
```

**参数：**
- `file`: 图片文件（支持jpg, png, tiff, jp2, bmp）
- `use_gpu`: 是否使用GPU（可选，默认false）
- `enable_viz`: 是否生成可视化（可选，默认false）

**示例：**

```bash
# 使用curl
curl -X POST http://localhost:5000/api/ocr/ndlocr-lite \
  -F "file=@document.jpg"
```

```python
# 使用Python requests
import requests

with open('japanese_document.jpg', 'rb') as f:
    files = {'file': f}
    response = requests.post('http://localhost:5000/api/ocr/ndlocr-lite', files=files)
    result = response.json()

print(result['text'])  # 识别的文本
print(result['structured_data'])  # 结构化数据
```

### 2. 检查NDL OCR-Lite状态

```
GET /api/ocr/ndlocr-lite/status
```

**示例：**

```bash
curl http://localhost:5000/api/ocr/ndlocr-lite/status
```

**响应示例：**

```json
{
  "success": true,
  "data": {
    "available": true,
    "executable_path": "/path/to/ndlocr-lite/src/ocr.py",
    "gpu_enabled": false,
    "supported_formats": ["jpg", "jpeg", "png", "tiff", "tif", "jp2", "bmp"]
  }
}
```

---

## 💻 代码集成示例

### 示例1：基础使用

```python
from modules.ocr_processor import OCRProcessor
from modules.ndlocr_result_processor import create_result_processor

# 创建处理器
processor = OCRProcessor()

# 识别图片
result = processor.ndlocr_lite_ocr('document.jpg')

if result['success']:
    print("识别文本:", result['text'])
    print("页数:", result['statistics']['total_pages'])
    print("字数:", result['statistics']['total_words'])
else:
    print("错误:", result['error'])
```

### 示例2：批量处理

```python
from modules.ocr_processor import OCRProcessor

processor = OCRProcessor()

# 批量处理（传入目录）
result = processor.ndlocr_lite_batch('images_directory')

if result['success']:
    # 访问所有页面的文本
    for page in result['pages']:
        print(f"Page {page['page_number']}: {page['text']}")
```

### 示例3：GPU加速 + 可视化

```python
from modules.ocr_processor import OCRProcessor

processor = OCRProcessor()

# 启用GPU和可视化
result = processor.ndlocr_lite_ocr(
    'document.jpg',
    use_gpu=True,
    enable_viz=True
)

if result['success']:
    print("可视化文件路径:", result['visualization_paths'])
```

### 示例4：直接使用NDL处理器

```python
from modules.ndlocr_lite import create_ndlocr_processor, NDLOCRLiteResult
from modules.ndlocr_result_processor import create_result_processor

# 创建处理器
ndl_processor = create_ndlocr_processor(
    use_gpu=False,
    enable_viz=False
)

# 检查是否安装
if not ndl_processor.is_installed():
    print("请先安装NDL OCR-Lite")
    print(ndl_processor.get_installation_guide())
    exit()

# 处理图片
result = ndl_processor.process_image('japanese_doc.jpg')

# 处理结果
result_processor = create_result_processor()
processed = result_processor.process_result(result)

# 导出为JSON
json_output = result_processor.to_json(processed)
print(json_output)
```

---

## 📊 输出格式

### 处理结果结构

```json
{
  "success": true,
  "text": "识别的完整文本...",
  "structured_data": {
    "paragraphs": ["段落1", "段落2", ...],
    "tables": [[["单元格", "单元格"], ...]],
    "lists": [{"type": "ordered", "items": ["项目1", "项目2"]}],
    "key_value_pairs": {"键": "值"}
  },
  "pages": [
    {
      "page_number": 1,
      "original_text": "原文...",
      "cleaned_text": "清洗后...",
      "word_count": 150,
      "char_count": 800
    }
  ],
  "statistics": {
    "total_pages": 5,
    "total_words": 2500,
    "total_chars": 15000,
    "processing_time": 12.5,
    "cleaning_stats": {
      "spaces_removed": 120,
      "chars_cleaned": 5
    }
  },
  "metadata": {
    "output_dir": "/path/to/output",
    "visualization_available": true,
    "visualization_count": 5
  }
}
```

---

## 🔧 高级功能

### 1. 自定义文本清洗

```python
from modules.ndlocr_result_processor import create_result_processor

# 自定义清洗配置
processor = create_result_processor(
    remove_extra_spaces=True,
    normalize_unicode=True,
    fix_common_errors=True,
    remove_page_numbers=True
)

# 处理结果
cleaned = processor.clean_text("原始文本...")
```

### 2. 提取特定结构

```python
# 提取键值对
key_values = processor._extract_key_value_pairs(text)

# 提取表格
tables = processor._extract_tables(lines)

# 提取列表
lists = processor._extract_lists(lines)
```

### 3. 批量处理多个结果

```python
from modules.ndlocr_result_processor import create_result_processor

processor = create_result_processor()
results = processor.batch_process([result1, result2, result3])
```

---

## 🐛 故障排除

### 问题1：NDL OCR-Lite未找到

**症状：**
```
error: NDL OCR-Lite未安装或无法找到
```

**解决方案：**
1. 确认已按照安装指南完成安装
2. 检查环境变量 `NDLOCR_LITE_PATH` 配置正确
3. 确保在命令行中可以运行 `python3 ocr.py --help`

### 问题2：处理超时

**症状：**
```
error: 处理超时(>300秒)
```

**解决方案：**
1. 增加超时时间：在 `.env` 中设置 `NDLOCR_LITE_TIMEOUT=600`
2. 使用GPU加速：设置 `NDLOCR_LITE_GPU=true`
3. 分批处理大文件

### 问题3：图片格式不支持

**症状：**
```
error: 不支持的图片格式或文件不存在
```

**解决方案：**
确保图片格式为以下之一：
- JPG/JPEG
- PNG
- TIFF/TIF
- JP2
- BMP

### 问题4：GPU加速失败

**症状：**
GPU处理失败，切换到CPU模式

**解决方案：**
1. 确认安装了CUDA环境
2. 安装onnxruntime-gpu：`pip install onnxruntime-gpu`
3. 或禁用GPU：设置 `NDLOCR_LITE_GPU=false`

---

## 📝 技术细节

### NDL OCR-Lite工作原理

NDL OCR-Lite由三个核心模块组成：

1. **布局识别**：使用DEIMv2模型识别文档结构
2. **字符识别**：使用PARSeq模型识别文字
3. **阅读顺序**：智能排序识别结果

### 输出文件说明

处理后在输出目录生成：
- `.txt` 文件：纯文本内容
- `.xml` 文件：结构化XML数据（包含位置信息）
- `_viz.png` 文件：可视化结果（可选）

---

## 🎯 最佳实践

### 1. 图片质量优化

- 使用300 DPI以上的扫描图片
- 确保文字清晰、对比度足够
- 避免倾斜或变形的图片

### 2. 处理策略

```python
# 对于大批量文档
processor = OCRProcessor()
for doc in documents:
    result = processor.ndlocr_lite_ocr(doc, enable_viz=False)
```

### 3. 结果后处理

```python
# 使用LLM进一步处理
llm_client = LLMClient({'provider': 'zhipu', 'api_key': 'your_key'})
corrected = llm_client.ocr_correction(ocr_text, language='ja')
```

---

## 📚 相关资源

- **NDL OCR-Lite官方仓库**：https://github.com/ndl-lab/ndlocr-lite
- **Python要求**：Python 3.10+
- **许可证**：CC BY 4.0

---

**版本**：1.1.0  
**更新日期**：2024年3月  
**集成版本**：NDL OCR-Lite latest
