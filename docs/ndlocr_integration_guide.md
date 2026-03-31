# NDLoCR 接入指南

## 概述

NDLoCR (NDL古典籍OCR-Lite) 是日本国立国会图书馆开发的开源OCR工具，用于识别古典日语文献。本工作区通过接口隔离机制与NDLoCR集成，确保在NDLoCR不可用时系统仍能正常运行。

## 接口架构

```
┌─────────────────────────────────────────────────────────┐
│                    本工作区                              │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐   │
│  │            NDLoCRInterface (接口抽象层)          │   │
│  │  - 检测NDLoCR可用性                              │   │
│  │  - 验证模型文件完整性                            │   │
│  │  - 提供统一调用接口                              │   │
│  │  - 支持Mock模式回退                              │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                              │
│                         ▼                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │              外部 NDLoCR 插件                    │   │
│  │  (独立于工作区，需单独下载)                      │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 安装步骤

### 1. 下载NDLoCR

```bash
# 进入项目目录
cd AItools-for-historyresearch

# 创建外部目录
mkdir -p external

# 克隆NDLoCR仓库
cd external
git clone https://github.com/ndl-lab/ndlkotenocr-lite.git
cd ..
```

### 2. 安装NDLoCR依赖

```bash
cd external/ndlkotenocr-lite
pip install -r requirements.txt
cd ../..
```

### 3. 下载模型文件

从NDLoCR官方Release下载模型文件：

```bash
# 模型文件列表
external/ndlkotenocr-lite/src/model/
├── rtmdet-s-1280x1280.onnx      # 文本检测模型
└── parseq-ndl-32x384-tiny-10.onnx  # 文本识别模型
```

下载地址: https://github.com/ndl-lab/ndlkotenocr-lite/releases

### 4. 验证安装

```bash
python run_automated_workflow.py --check-only
```

输出应包含:
```
NDLoCR验证:
  可用: True
  配置完整: True
```

## 配置文件

### NDLoCR接口配置 (config/ndlocr_interface_config.json)

```json
{
    "interface_name": "NDLoCR Interface",
    "version": "1.0.0",
    "adapter_config": {
        "base_path": "external/ndlkotenocr-lite",
        "model_dir": "src/model",
        "config_dir": "src/config"
    },
    "required_components": {
        "detection": {
            "model_file": "rtmdet-s-1280x1280.onnx",
            "config_file": "ndl.yaml"
        },
        "recognition": {
            "model_file": "parseq-ndl-32x384-tiny-10.onnx",
            "config_file": "NDLmoji.yaml"
        }
    }
}
```

### 自定义NDLoCR路径

如果NDLoCR安装在其他位置，修改 `config/environment_config.json`:

```json
{
    "ndlocr_path": "path/to/your/ndlkotenocr-lite"
}
```

## 接口使用

### Python API

```python
from modules.integration_manager import create_integration_manager

# 创建整合管理器
env_manager, file_manager, ndlocr_interface, workflow = create_integration_manager()

# 检查NDLoCR可用性
if ndlocr_interface.is_available:
    print("NDLoCR可用")
    
    # 验证配置
    validation = ndlocr_interface.validate_setup()
    if validation["all_valid"]:
        # 加载模型
        ndlocr_interface.load_models()
        
        # 获取模型路径
        det_model = ndlocr_interface.get_detection_model_path()
        rec_model = ndlocr_interface.get_recognition_model_path()
        print(f"检测模型: {det_model}")
        print(f"识别模型: {rec_model}")
else:
    print("NDLoCR不可用，使用Mock模式")
    mock = ndlocr_interface.create_mock_interface()
```

### 命令行验证

```bash
# 完整环境检查
python run_automated_workflow.py --check-only

# 仅检查NDLoCR
python -c "
from modules.integration_manager import create_integration_manager
_, _, ndlocr, _ = create_integration_manager()
print(ndlocr.validate_setup())
"
```

## Mock模式

当NDLoCR不可用时，系统自动启用Mock模式进行测试：

```python
# Mock模式输出示例
mock_interface = ndlocr_interface.create_mock_interface()
# {
#     "type": "mock",
#     "detection_model": "mock_detection.onnx",
#     "recognition_model": "mock_recognition.onnx",
#     "message": "这是模拟接口，用于测试目的"
# }
```

## 接口抽象层

### NDLoCRInterface 类

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `is_available` | 检查NDLoCR是否可用 | bool |
| `validate_setup()` | 验证配置完整性 | Dict |
| `load_models()` | 加载模型 | bool |
| `get_detection_model_path()` | 获取检测模型路径 | str/None |
| `get_recognition_model_path()` | 获取识别模型路径 | str/None |
| `create_mock_interface()` | 创建模拟接口 | Dict |
| `get_config_template()` | 获取配置模板 | Dict |

### 验证返回结构

```python
validation = ndlocr_interface.validate_setup()
# 返回:
# {
#     "available": True/False,
#     "path": "/path/to/ndlkotenocr-lite",
#     "required_files": {
#         "src/model/rtmdet-s-1280x1280.onnx": True/False,
#         "src/model/parseq-ndl-32x384-tiny-10.onnx": True/False,
#         ...
#     },
#     "all_valid": True/False
# }
```

## 故障排除

### 问题: NDLoCR不可用

**检查清单:**
1. 确认 `external/ndlkotenocr-lite` 目录存在
2. 确认模型文件已下载
3. 检查配置文件路径设置

```bash
# 检查目录
ls external/ndlkotenocr-lite/src/model/

# 应显示:
# rtmdet-s-1280x1280.onnx
# parseq-ndl-32x384-tiny-10.onnx
```

### 问题: 模型文件缺失

**解决方案:**
1. 从GitHub Release下载模型
2. 放置到 `external/ndlkotenocr-lite/src/model/` 目录

### 问题: ONNX运行时错误

**解决方案:**
```bash
pip install onnxruntime
# 或GPU版本
pip install onnxruntime-gpu
```

## 工作区隔离机制

### 设计原则

1. **接口抽象**: 通过 `NDLoCRInterface` 类封装所有NDLoCR交互
2. **配置驱动**: 路径和设置通过配置文件管理
3. **优雅降级**: NDLoCR不可用时自动切换到Mock模式
4. **无硬编码**: 所有路径使用相对路径或配置文件

### 迁移到新环境

当工作区迁移到新计算机时:

1. **复制工作区** (不包含NDLoCR)
2. **在新环境下载NDLoCR**
3. **运行环境检查**

```bash
# 新环境操作
git clone <workspace-url>
cd AItools-for-historyresearch
pip install -r requirements.txt

# 下载NDLoCR
mkdir -p external
cd external
git clone https://github.com/ndl-lab/ndlkotenocr-lite.git
cd ..

# 验证
python run_automated_workflow.py --check-only
```

## 高级配置

### 使用自定义模型

```json
// config/ndlocr_interface_config.json
{
    "required_components": {
        "detection": {
            "model_file": "your-custom-detection.onnx"
        },
        "recognition": {
            "model_file": "your-custom-recognition.onnx"
        }
    }
}
```

### 多版本NDLoCR

```json
// config/environment_config.json
{
    "ndlocr_path": "external/ndlkotenocr-lite-v2"
}
```

## 参考资源

- NDLoCR官方仓库: https://github.com/ndl-lab/ndlkotenocr-lite
- NDLoCR文档: https://github.com/ndl-lab/ndlkotenocr-lite/wiki
- 模型下载: https://github.com/ndl-lab/ndlkotenocr-lite/releases
