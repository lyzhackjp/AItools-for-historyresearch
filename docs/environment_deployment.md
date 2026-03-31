# 环境部署文档

## 概述

本文档描述如何在全新环境中部署和运行本工作区。系统设计为环境无关，可在不同计算机上无需修改脚本即可正常运行。

## 系统要求

### 硬件要求
- CPU: 多核处理器 (推荐4核以上)
- 内存: 8GB以上 (推荐16GB)
- 存储: 10GB以上可用空间
- GPU: 可选，支持CUDA的NVIDIA显卡可加速训练

### 软件要求
- 操作系统: Windows 10/11, macOS 10.15+, Linux
- Python: 3.8 - 3.11

## 快速部署

### 1. 克隆工作区

```bash
git clone <repository-url>
cd AItools-for-historyresearch
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 验证环境

```bash
python run_automated_workflow.py --check-only
```

## 目录结构

```
AItools-for-historyresearch/
├── config/                 # 配置文件目录
│   ├── environment_config.json      # 环境配置
│   ├── ndlocr_interface_config.json # NDLoCR接口配置
│   └── api_config.json              # API配置
├── modules/                # 核心模块目录
│   ├── environment_manager.py       # 环境管理
│   ├── integration_manager.py       # 整合管理
│   └── classical_ocr_training_workflow.py
├── external/               # 外部依赖目录
│   └── ndlkotenocr-lite/            # NDLoCR (需单独下载)
├── output/                 # 输出目录
├── temp/                   # 临时文件目录
├── cache/                  # 缓存目录
├── logs/                   # 日志目录
├── data/                   # 数据目录
├── models/                 # 模型目录
└── run_automated_workflow.py        # 主执行脚本
```

## 配置说明

### 环境配置 (config/environment_config.json)

```json
{
    "ndlocr_path": "external/ndlkotenocr-lite",
    "output_base": "output",
    "temp_dir": "temp",
    "cache_dir": "cache",
    "log_dir": "logs",
    "data_dir": "data",
    "models_dir": "models",
    "auto_install_dependencies": false,
    "training": {
        "default_epochs": 10,
        "default_batch_size": 4,
        "device": "auto"
    }
}
```

### 关键配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| ndlocr_path | NDLoCR相对路径 | external/ndlkotenocr-lite |
| output_base | 输出目录 | output |
| auto_install_dependencies | 自动安装缺失依赖 | false |
| training.default_epochs | 默认训练轮数 | 10 |
| training.device | 训练设备 | auto (自动检测) |

## 环境变量

系统支持以下环境变量进行动态配置：

| 环境变量 | 说明 |
|----------|------|
| AI_TOOLS_ROOT | 项目根目录 (自动检测) |
| AI_TOOLS_CONFIG | 配置文件路径 |
| AI_TOOLS_CUDA | CUDA路径 |

## 依赖管理

### 必需依赖

```txt
torch>=2.0.0
torchvision>=0.15.0
Pillow>=9.0.0
opencv-python>=4.5.0
numpy>=1.20.0
PyYAML>=6.0
tqdm>=4.64.0
fitz (PyMuPDF)
lmdb>=1.4.0
psutil>=5.9.0
```

### 可选依赖

```txt
mmdet>=3.0.0
mmcv>=2.0.0
pytorch-lightning>=2.0.0
onnx>=1.16.0
onnxruntime>=1.18.0
```

## GPU支持

### CUDA环境配置

1. 安装NVIDIA驱动
2. 安装CUDA Toolkit (推荐11.8+)
3. 安装cuDNN
4. 安装PyTorch CUDA版本:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### 验证CUDA

```python
import torch
print(f"CUDA可用: {torch.cuda.is_available()}")
print(f"CUDA版本: {torch.version.cuda}")
print(f"GPU数量: {torch.cuda.device_count()}")
```

## 常见问题

### Q: 找不到模块错误

确保在项目根目录运行脚本，并已激活虚拟环境。

### Q: CUDA不可用

1. 检查NVIDIA驱动是否正确安装
2. 确认PyTorch版本与CUDA版本匹配
3. 系统会自动回退到CPU训练

### Q: 内存不足

1. 减小batch_size
2. 减少处理的页面数量
3. 使用更小的模型

### Q: 路径错误

系统使用相对路径，确保不要移动或重命名关键目录。

## 跨设备迁移

### 打包工作区

```bash
# 排除大型临时文件
tar --exclude='temp/*' \
    --exclude='cache/*' \
    --exclude='output/*' \
    --exclude='venv' \
    -czvf workspace.tar.gz .
```

### 在新设备部署

```bash
tar -xzvf workspace.tar.gz
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows
pip install -r requirements.txt
python run_automated_workflow.py --check-only
```

## 更新与维护

### 更新依赖

```bash
pip install --upgrade -r requirements.txt
```

### 清理临时文件

```python
from modules.integration_manager import create_integration_manager

env, file_manager, _, _ = create_integration_manager()
file_manager.cleanup_all()
```

### 重置环境

```bash
# 删除并重建虚拟环境
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
