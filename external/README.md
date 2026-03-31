# External 外接模块

本目录用于存放外部开源工具作为本项目的备选/扩展模块。**此目录内容不纳入Git版本控制**，用户需自行下载安装。

## 目录结构

```
external/
├── dify/              # Dify LLM应用开发平台
├── ragflow/           # Ragflow RAG引擎
├── ndlocr-lite/       # NDL OCR-Lite模型
└── ndlkotenocr-lite/  # NDL古典籍OCR-Lite模型
```

## 外接工具列表

| 工具名称 | 用途 | 官方仓库 | 接口模块 |
|----------|------|----------|----------|
| Dify | LLM应用开发平台，内置RAG功能 | https://github.com/langgenius/dify | `rag_module/adapters/dify_adapter.py` |
| Ragflow | 开源RAG引擎，支持深度文档理解 | https://github.com/infiniflow/ragflow | `rag_module/adapters/ragflow_adapter.py` |
| NDL OCR-Lite | 近代现代日本印刷体OCR | https://github.com/ndl-lab/ndlocr-lite | `modules/ndlocr_lite.py` |
| NDL古典籍OCR-Lite | 古典籍草书字OCR | https://github.com/ndl-lab/ndlkotenocr-lite | `modules/ndlkotenocr_lite.py` |

## 安装指南

### Dify 安装

```bash
cd external
git clone https://github.com/langgenius/dify.git
cd dify
cp .env.example .env
# 编辑.env配置API密钥等
docker compose up -d
```

### Ragflow 安装

```bash
cd external
git clone https://github.com/infiniflow/ragflow.git
cd ragflow
# 按照官方文档配置Docker环境
```

### NDL OCR 安装

```bash
cd external
git clone https://github.com/ndl-lab/ndlocr-lite.git
git clone https://github.com/ndl-lab/ndlkotenocr-lite.git

# 下载模型文件（从GitHub Release页面）
# 放置到对应目录：
# ndlocr-lite/src/model/
# ndlkotenocr-lite/src/model/

# 安装依赖
cd ndlocr-lite && pip install -r requirements.txt
cd ../ndlkotenocr-lite && pip install -r requirements.txt
```

## 接口使用

### RAG模块切换

本项目提供统一的RAG接口，支持在自研RAG、Dify、Ragflow之间无缝切换：

```python
from rag_module.adapters import RAGFactory, RAGBackend

# 查看可用后端
available = RAGFactory.get_available_backends()
for backend, info in available.items():
    print(f"{backend.value}: {info['message']}")

# 切换到Dify
dify_adapter = RAGFactory.switch_backend(
    RAGBackend.DIFY,
    config={
        'api_key': 'your-dify-api-key',
        'base_url': 'http://localhost/v1',
        'dataset_id': 'your-dataset-id'
    }
)

# 切换到Ragflow
ragflow_adapter = RAGFactory.switch_backend(
    RAGBackend.RAGFLOW,
    config={
        'api_key': 'your-ragflow-api-key',
        'base_url': 'http://localhost',
        'dataset_name': 'my-dataset'
    }
)

# 使用统一接口
result = ragflow_adapter.query('明治维新的影响是什么？')
print(result.answer)
```

### 自动选择后端

```python
from rag_module.adapters import RAGFactory

# 自动选择第一个可用的后端（优先级：built_in > ragflow > dify）
adapter = RAGFactory.auto_select_backend()

# 或指定首选
adapter = RAGFactory.auto_select_backend(prefer=RAGBackend.RAGFLOW)
```

## 配置文件

外部工具的配置信息应存放在：

- `config/external_config.json` - 外部工具连接配置
- `.env` - API密钥等敏感信息

### 配置示例 (config/external_config.json)

```json
{
    "dify": {
        "enabled": false,
        "base_url": "http://localhost/v1",
        "dataset_id": "",
        "timeout": 60
    },
    "ragflow": {
        "enabled": false,
        "base_url": "http://localhost",
        "dataset_name": "history-research",
        "timeout": 60
    },
    "ndlocr": {
        "enabled": true,
        "model_path": "./external/ndlocr-lite/src/model"
    },
    "ndlkotenocr": {
        "enabled": true,
        "model_path": "./external/ndlkotenocr-lite/src/model"
    }
}
```

## 注意事项

1. **不纳入版本控制**：external目录已添加到.gitignore，不会上传到GitHub
2. **模型文件**：NDL OCR模型文件较大（数百MB），需单独下载
3. **Docker环境**：Dify和Ragflow推荐使用Docker部署
4. **API密钥**：请勿将API密钥提交到版本控制

## 相关文档

- [RAG模块使用指南](../rag_module/docs/RAG_MODULE_GUIDE.md)
- [NDLoCR接入指南](../docs/ndlocr_integration_guide.md)
