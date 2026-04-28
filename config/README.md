# API配置系统使用指南

## 📁 配置文件结构

```
config/
├── api_config.json           # 生产环境配置
├── api_config.test.json      # 测试环境配置
├── api_config_loader.py      # 统一配置加载器
├── config_helpers.py          # 配置辅助工具
└── README.md                 # 本文档
```

## 🚀 快速开始

### 1. 查看配置状态

```python
from config.config_helpers import print_config_status

print_config_status()
```

### 2. 验证环境配置

```python
from config.config_helpers import validate_environment

results = validate_environment()
print(results)
```

### 3. 创建API客户端

```python
from config.config_helpers import create_client_with_config

# 使用默认provider
client = create_client_with_config()

# 为特定模块创建客户端
client = create_client_with_config(module_name='academic_note_generator')

# 指定provider
client = create_client_with_config(provider='dashscope')
```

## 🔧 配置加载器使用

### 基础用法

```python
from config.api_config_loader import (
    get_config,
    get_provider_config,
    load_config,
    get_environment
)

# 获取当前配置
config = get_config()

# 获取特定provider配置
dashscope_config = get_provider_config('dashscope')

# 加载指定环境配置
test_config = load_config('test')

# 获取当前环境
env = get_environment()  # 'production' 或 'test'
```

### 高级用法

```python
from config.api_config_loader import (
    get_timeout,
    get_headers,
    get_max_retries,
    create_llm_config
)

# 获取API超时设置
timeout = get_timeout()  # 60秒

# 获取请求头
headers = get_headers()

# 获取最大重试次数
max_retries = get_max_retries()

# 创建LLM配置
llm_config = create_llm_config(
    provider='dashscope',
    module_name='academic_note_generator'
)
```

## ⚙️ 环境切换

### 方式1：使用环境变量

```bash
# 设置为生产环境
set API_ENV=production

# 设置为测试环境
set API_ENV=test
```

### 方式2：代码中切换

```python
from config.api_config_loader import load_config

# 切换到测试环境
load_config('test')

# 切换到生产环境
load_config('production')
```

### 方式3：使用辅助函数

```python
from config.config_helpers import switch_environment

# 切换到测试环境
switch_environment('test')

# 切换到生产环境
switch_environment('production')
```

## 📝 配置文件说明

### 生产环境配置 (api_config.json)

#### 环境设置

```json
{
  "environment": {
    "name": "production",
    "debug": false
  }
}
```

#### API通用设置

```json
{
  "api": {
    "base_settings": {
      "timeout": 60,           // 请求超时（秒）
      "connect_timeout": 10,    // 连接超时
      "max_retries": 3,        // 最大重试次数
      "retry_delay": 1.0       // 重试延迟
    },
    "headers": {
      "User-Agent": "AI-History-Research-Tools/1.0"
    },
    "rate_limiting": {
      "enabled": true,
      "requests_per_minute": 60
    }
  }
}
```

#### Provider配置示例

```json
{
  "providers": {
    "dashscope": {
      "enabled": true,
      "base_url": "https://dashscope.aliyuncs.com/api/v1",
      "default_model": "qwen-turbo",
      "api_key_env": "DASHSCOPE_API_KEY"
    }
  }
}
```

#### 模块配置示例

```json
{
  "modules": {
    "academic_note_generator": {
      "provider": "dashscope",
      "model": "qwen-turbo",
      "temperature": 0.3,
      "max_tokens": 2000,
      "test_mode": false
    }
  }
}
```

### 测试环境配置 (api_config.test.json)

测试环境配置与生产环境配置结构相同，主要区别：

1. **启用调试模式**：`"debug": true`
2. **更短的超时时间**：`"timeout": 30`
3. **禁用速率限制**：`"enabled": false`
4. **启用模拟数据**：`"test_mode": true`
5. **测试专用API密钥**：`"TEST_*_API_KEY"`

## 🔑 API密钥配置

### 方式1：环境变量

```bash
# Windows
set DASHSCOPE_API_KEY=DASHSCOPE_API_KEY_PLACEHOLDER

# Linux/Mac
export DASHSCOPE_API_KEY=DASHSCOPE_API_KEY_PLACEHOLDER
```

### 方式2：创建.env文件

```python
from config.config_helpers import create_env_file_from_template

create_env_file_from_template(output_path='.env')
```

### 方式3：直接编辑配置文件

在 `api_config.json` 中只能指定环境变量名，不能写入真实 key：

```json
{
  "providers": {
    "dashscope": {
      "api_key_env": "DASHSCOPE_API_KEY"
    }
  }
}
```

`api_config.json`、`current_environment.json` 和 `external_config.json` 是可提交模板文件，只能包含相对路径、公开端点、默认模型名和环境变量名。真实 API key、NDL 账号、NDL 密码、cookie、session、个人路径或本地绝对模型路径必须放在环境变量、系统密钥管理器或被 `.gitignore` 排除的 `secrets/` 中。

## 📊 获取Provider信息

```python
from config.config_helpers import print_provider_info, list_available_providers

# 打印所有可用provider
print_provider_info()

# 获取provider列表
providers = list_available_providers()
for p in providers:
    print(f"{p['name']}: {p['default_model']}")
```

## 🔍 配置验证

### 验证API密钥

```python
from config.api_config_loader import get_config

config = get_config()
validation = config.validate_api_keys()

for provider, is_configured in validation.items():
    status = "✓ 已配置" if is_configured else "✗ 未配置"
    print(f"{provider}: {status}")
```

### 导出配置

```python
from config.api_config_loader import get_config

config = get_config()
config.export_config('exported_config.json')
```

## 💡 使用示例

### 示例1：学术笔记生成

```python
from config.config_helpers import create_client_with_config
from modules.academic_note_generator import AcademicNoteGenerator

# 创建配置好的生成器
generator = AcademicNoteGenerator(
    api_provider="dashscope",
    test_mode=False
)

# 或使用配置辅助函数
client = create_client_with_config(module_name='academic_note_generator')
```

### 示例2：学术摘要生成

```python
from modules.academic_summarizer import AcademicSummarizer

# 使用配置系统
summarizer = AcademicSummarizer(
    api_provider="dashscope",
    test_mode=False
)
```

### 示例3：虚拟人格对话

```python
from modules.virtual_persona_chatbot import VirtualPersonaChatbot

# 创建对话系统
chatbot = VirtualPersonaChatbot(
    api_provider="qwen",  # 或 "minimax"
    test_mode=False
)

# 加载预设人格
chatbot.load_persona('fukuzawa')

# 开始对话
response = chatbot.generate_response("请谈谈你对明治维新的看法")
```

## 🛠️ 故障排除

### 问题1：配置文件未找到

```
错误: 配置文件不存在
```

**解决方案**：
```python
from pathlib import Path
print(Path(__file__).parent)  # 确认config目录存在
```

### 问题2：API密钥未配置

```
警告: 未配置任何API密钥
```

**解决方案**：
```bash
# 设置环境变量
set DASHSCOPE_API_KEY=your_key_here
```

### 问题3：模块导入失败

```
ImportError: cannot import name 'get_config'
```

**解决方案**：
```python
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
```

## 📋 最佳实践

1. **使用环境变量存储敏感信息**：不要将API密钥直接写入代码
2. **定期轮换API密钥**：建议每90天更换一次
3. **使用测试环境进行开发**：开发时使用测试环境，避免产生费用
4. **监控API使用**：利用监控配置追踪API调用和成本
5. **配置文件版本控制**：将配置文件纳入版本控制，但排除包含密钥的版本

## 🔗 相关资源

- [阿里云DashScope文档](https://help.aliyun.com/zh/dashscope/)
- [MiniMax API文档](https://www.minimax.io/)
- [OpenAI API文档](https://platform.openai.com/docs)
- [Anthropic Claude文档](https://docs.anthropic.com/)

---

**创建日期**: 2026年3月28日
**最后更新**: 2026年3月28日
**版本**: 1.0.0
