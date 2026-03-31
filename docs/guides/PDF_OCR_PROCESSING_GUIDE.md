# PDF OCR处理模块使用指南

## 📖 概述

本项目提供了完整的PDF到Word文档处理流程，专门针对日文历史文献的OCR识别进行了优化。

### 核心模块

1. **environment_checker.py** - 环境依赖检查
2. **ndl_ocr_monitor.py** - NDL OCR服务监控
3. **ndl_ocr_batch_processor.py** - NDL OCR批量处理
4. **ndlocr_lite.py** - NDL OCR调用封装
5. **ndlocr_result_processor.py** - 结果处理

---

## 🚀 快速开始

### 1. 环境检查

在执行任何任务前，建议先运行环境检查：

```python
from modules.environment_checker import run_environment_check

# 检查环境
passed = run_environment_check("PDF处理任务")

if not passed:
    print("请先解决环境问题")
else:
    print("环境检查通过，可以继续")
```

**自动生成报告**：
- 文件名格式：`{时间戳}_环境检查报告.md`
- 包含所有依赖项状态
- 问题与解决方案建议

### 2. NDL OCR健康检查

快速检查NDL OCR服务状态：

```python
from modules.ndl_ocr_monitor import quick_health_check

# 快速检查
is_healthy = quick_health_check()

if is_healthy:
    print("NDL OCR服务正常")
else:
    print("服务不可用，请检查")
```

### 3. 批量OCR处理

处理多张图片的OCR识别：

```python
from modules.ndl_ocr_batch_processor import create_batch_processor

# 创建处理器
processor = create_batch_processor()

# 批量处理
results = processor.process_batch(
    image_dir="test Images",      # 图片目录
    output_dir="ocr_output",     # 输出目录
    max_pages=20                 # 最大页数
)

# 获取统计
stats = processor.get_statistics()
print(f"成功: {stats['success']}/{stats['total']}")
print(f"成功率: {stats['success_rate']:.1f}%")
print(f"总字符数: {stats['total_chars']:,}")
```

---

## 📊 完整工作流

### PDF到Word一键处理

```python
from modules.ndl_ocr_batch_processor import create_workflow

# 创建工作流
workflow = create_workflow()

# 执行工作流
result = workflow.run_workflow(
    pdf_path="test-pdf/伊藤博文伝 中-1.pdf",
    output_dir="output",
    max_pages=20,
    dpi=300,
    generate_word=True
)

if result['success']:
    print(f"Word文档: {result['word_output']}")
```

**工作流步骤**：
1. ✅ PDF转图片（300 DPI）
2. ✅ NDL OCR批量识别
3. ✅ 数据清洗
4. ✅ 生成Word文档

---

## 🔍 环境检查模块详解

### EnvironmentChecker 类

```python
from modules.environment_checker import EnvironmentChecker

# 创建检查器
checker = EnvironmentChecker()

# 执行检查
passed, report = checker.check_all()

# 获取报告文件名
filename = checker.get_report_filename()
```

**检查内容**：
- ✅ 系统信息（OS、版本、架构）
- ✅ Python版本（需要3.8+）
- ✅ Python依赖包
  - Flask、Web框架
  - python-docx、Word处理
  - PyMuPDF、PDF处理
  - Pillow、图片处理
  - Tesseract OCR
  - OpenAI/Anthropic API
  - 其他必要依赖
- ✅ NDL OCR安装状态
  - 目录存在性
  - 依赖完整性
- ✅ 配置文件状态

### 环境检查报告示例

```markdown
# 环境依赖检查报告

## 系统信息
- 操作系统: Windows
- 版本: 10 或更高版本
- 架构: AMD64

## Python环境
- 版本: 3.11.9
- 路径: C:\Python311\python.exe

## Python依赖
- Flask Web框架: ✓ 已安装 (v3.0.0)
- python-docx Word文档处理: ✓ 已安装 (v1.2.0)
- ...

## NDL OCR环境
- ✓ NDL OCR: 已安装
- 路径: C:\...\ndlocr-lite\src\ocr.py
- 依赖状态: 15/15

## 总结
**检查结果**: ✅ 全部通过
```

---

## 💓 NDL OCR监控详解

### NDLOCRHeartbeatMonitor 类

```python
from modules.ndl_ocr_monitor import NDLOCRHeartbeatMonitor

# 创建监控器
monitor = NDLOCRHeartbeatMonitor(
    ndlocr_path="ndlocr-lite/src/ocr.py"
)

# 单次心跳检测
result = monitor.perform_heartbeat()
print(f"可用: {result['available']}")
print(f"响应时间: {result['response_time']:.2f}秒")

# 获取状态
status = monitor.get_status()
print(f"健康状态: {status['health_status']}")

# 生成报告
report = monitor.generate_report()
monitor.save_report()
```

### 心跳机制（5分钟间隔）

```python
# 启动持续监控
monitor.start_monitoring(interval=300)  # 300秒 = 5分钟

# 执行其他任务...
time.sleep(3600)

# 停止监控
monitor.stop_monitoring()

# 查看最终状态
status = monitor.get_status()
print(f"检查次数: {status['total_checks']}")
print(f"可用率: {status['uptime_percentage']:.1f}%")
```

### 监控配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `interval` | 300秒 | 心跳间隔（5分钟） |
| `timeout` | 60秒 | 单次检测超时 |

### 告警机制

当连续失败3次以上时，会自动触发告警：

```
⚠️  NDL OCR服务告警
连续失败次数: 5
最后错误: 处理超时
建议操作:
  1. 检查NDL OCR是否正确安装
  2. 检查系统资源是否充足
  3. 检查网络连接是否正常
```

---

## 🔄 批量处理器详解

### NDLOCRBatchProcessor 类

```python
from modules.ndl_ocr_batch_processor import NDLOCRBatchProcessor

# 初始化
processor = NDLOCRBatchProcessor(
    ndlocr_path="ndlocr-lite/src/ocr.py"
)

# 批量处理
results = processor.process_batch(
    image_dir="test Images",
    output_dir="ocr_output",
    max_pages=None,      # None表示全部
    timeout=60           # 单张超时
)

# 处理结果
for result in results:
    print(f"Page {result['page']}: {'✓' if result['success'] else '✗'}")
    if result['success']:
        print(f"  字符数: {result['char_count']}")
```

### 处理结果结构

```python
{
    'page': 1,
    'filename': 'page_0001.png',
    'success': True,
    'text': '识别的文本内容...',
    'char_count': 1234,
    'output_path': 'ocr_output/page_0001',
    'error': None
}
```

### 统计信息

```python
stats = processor.get_statistics()
# {
#     'total': 20,
#     'success': 20,
#     'failed': 0,
#     'total_chars': 13642,
#     'avg_chars': 682.1,
#     'success_rate': 100.0
# }
```

---

## 🎯 NDLOCRWorkflow 工作流

### 完整工作流

```python
from modules.ndl_ocr_batch_processor import create_workflow

workflow = create_workflow()

result = workflow.run_workflow(
    pdf_path="test-pdf/document.pdf",
    output_dir="output",
    max_pages=20,
    dpi=300,
    generate_word=True
)
```

### 工作流返回值

```python
{
    'success': True,
    'pdf_path': 'test-pdf/document.pdf',
    'output_dir': 'output',
    'pages_processed': 20,
    'pages_success': 20,
    'ocr_results': [...],          # OCR结果列表
    'cleaned_texts': [...],       # 清洗后文本
    'ocr_output_dir': 'output/ocr_results_20260327',
    'word_output': 'output/document_OCR识别结果.docx'
}
```

---

## 📝 最佳实践

### 1. 执行前检查环境

```python
from modules.environment_checker import run_environment_check

# 在所有任务前执行
if not run_environment_check("PDF处理"):
    sys.exit(1)
```

### 2. 批量处理前检查服务状态

```python
from modules.ndl_ocr_monitor import NDLOCRHeartbeatMonitor

monitor = NDLOCRHeartbeatMonitor()

# 快速检查
if not monitor.check_service()[0]:
    print("NDL OCR不可用，尝试等待...")
    if not monitor.wait_for_service(max_wait=300):
        print("服务启动失败")
        sys.exit(1)
```

### 3. 带心跳监控的批量处理

```python
# 启动监控
monitor = NDLOCRHeartbeatMonitor()
monitor.start_monitoring(interval=300)  # 5分钟心跳

# 执行批量处理
processor = NDLOCRBatchProcessor()
results = processor.process_batch(...)

# 停止监控
monitor.stop_monitoring()
```

### 4. 生成健康报告

```python
from modules.ndl_ocr_monitor import NDLOCRHeartbeatMonitor

monitor = NDLOCRHeartbeatMonitor()

# 执行多次心跳检测
for _ in range(5):
    monitor.perform_heartbeat()
    time.sleep(60)

# 生成并保存报告
report = monitor.generate_report()
monitor.save_report("ndl_ocr_health_report.md")
```

---

## ⚠️ 注意事项

### 1. NDL OCR安装

确保NDL OCR已正确安装：

```bash
git clone https://github.com/ndl-lab/ndlocr-lite
cd ndlocr-lite
pip install -r requirements.txt
```

### 2. 测试图片

确保测试图片存在：

```python
test_images_dir = Path("test Images")
if not test_images_dir.exists():
    print("警告: test Images目录不存在")
```

### 3. 超时设置

根据图片复杂度调整超时：

```python
# 简单图片
results = processor.process_batch(timeout=30)

# 复杂古籍
results = processor.process_batch(timeout=120)
```

### 4. 磁盘空间

批量处理会生成大量文件，确保有足够空间：

```python
import shutil
total, used, free = shutil.disk_usage("/")
print(f"可用空间: {free // (2**30)} GB")
```

---

## 🐛 故障排查

### 问题1: NDL OCR找不到

**错误**：
```
FileNotFoundError: NDL OCR未找到
```

**解决方案**：
1. 确认已克隆仓库
2. 检查路径是否正确
3. 运行环境检查

### 问题2: 批量处理失败

**排查步骤**：
1. 检查单张图片处理
2. 查看错误信息
3. 检查日志输出

### 问题3: 内存不足

**解决方案**：
1. 减少批量大小
2. 增加超时时间
3. 清理临时文件

---

## 📚 相关文档

- [NDL OCR-Lite集成指南](NDL_OCR_LITE_INTEGRATION.md)
- [集成总结](INTEGRATION_SUMMARY.md)
- [快速开始](QUICK_START.md)
- [主README](README.md)

---

## 🔧 API参考

### 环境检查

```python
EnvironmentChecker()              # 创建检查器
checker.check_all()              # 执行所有检查
checker.generate_report()        # 生成报告
checker.save_report()            # 保存报告
run_environment_check()          # 便捷函数
```

### 服务监控

```python
NDLOCRHeartbeatMonitor()         # 创建监控器
monitor.check_service()           # 单次检查
monitor.perform_heartbeat()       # 执行心跳
monitor.start_monitoring()        # 启动监控
monitor.stop_monitoring()         # 停止监控
monitor.get_status()              # 获取状态
monitor.wait_for_service()        # 等待服务
monitor.generate_report()         # 生成报告
quick_health_check()             # 快速检查
```

### 批量处理

```python
NDLOCRBatchProcessor()           # 创建处理器
processor.process_image()        # 处理单张
processor.process_batch()         # 批量处理
processor.get_statistics()        # 获取统计
create_batch_processor()         # 工厂函数
```

### 工作流

```python
NDLOCRWorkflow()                # 创建工作流
workflow.run_workflow()          # 执行工作流
create_workflow()                # 工厂函数
```

---

**版本**: 1.1.0  
**更新日期**: 2024年3月  
**模块版本**: NDL OCR-Lite latest
