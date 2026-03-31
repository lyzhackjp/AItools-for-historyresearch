# 学术论文智能精简处理工具使用指南

## 📖 概述

专为日本史学术论文设计的智能内容精简工具，基于阿里通义千问，能够智能识别并删除冗余内容，同时保留核心学术信息。

### 核心功能

1. **智能内容精简**
   - 自动识别并删除逻辑冗余的论述
   - 去除修辞上重复的表达
   - 严格保留核心观点、史实、人物生卒年份
   - 保护所有注释标注和参考文献

2. **专业文档处理**
   - 正确区分正文与脚注内容
   - 保持原文档结构和格式
   - 支持.docx格式输入输出
   - 修订追踪功能

3. **修订追踪功能**
   - 启用修订模式
   - 删除的内容以**红色删除线**显示
   - 修订后的内容以**蓝色下划线**标注
   - 支持学术修改过程的追溯和审核

4. **学术严谨性保障**
   - 专门针对日本史学术论文优化
   - 保护历史专有名词和学术术语
   - 保持原文论证逻辑结构

---

## 🚀 快速开始

### 1. 环境配置

确保已安装必要的依赖：

```bash
pip install python-docx openai anthropic requests python-dotenv
```

### 2. 配置API密钥

在项目根目录创建或编辑 `.env` 文件：

```env
# 阿里通义千问（优先使用）
DASHSCOPE_API_KEY=your_api_key_here

# Minimax（备用）
MINIMAX_API_KEY=your_api_key_here
```

### 3. 基本使用

```python
from modules.paper_polisher import create_paper_polisher

# 创建润色器（优先使用通义千问）
polisher = create_paper_polisher('qwen')

# 处理文档
result = polisher.process_document(
    input_path='input.docx',
    output_path='output.docx',
    enable_track_changes=True
)

print(f"处理完成！")
print(f"删除内容: {result['total_deletions']} 处")
print(f"输出文件: {result['output_file']}")
```

---

## 📝 核心功能详解

### 智能内容精简

**自动识别并删除**：
- 逻辑冗余的论述（重复论证同一观点）
- 修辞上重复的表达（相同的修饰词反复使用）
- 非必要的过渡句和重复强调

**严格保留**：
- 核心学术观点和结论
- 历史史实和重要事件
- 人物生卒年份和重要事迹
- 所有脚注、注释和参考文献标注
- 历史专有名词和学术术语
- 原文的论证逻辑结构

### 修订追踪功能

**启用修订模式**：
```python
result = polisher.process_document(
    input_path='input.docx',
    output_path='output.docx',
    enable_track_changes=True  # 启用修订追踪
)
```

**显示效果**：
- 删除内容：红色删除线
- 新增内容：蓝色下划线

### 专业文档处理

**脚注和注释处理**：
```python
# 自动识别并保留所有脚注
# 不进行精简处理
# 保持原有格式
```

**文档结构保护**：
- 标题层级保持不变
- 段落结构完整保留
- 表格内容不变

---

## 💻 API使用

### 阿里通义千问（优先）

```python
from modules.paper_polisher import create_paper_polisher

# 使用通义千问API
polisher = create_paper_polisher('qwen')

result = polisher.process_document(
    input_path='学术论文.docx',
    output_path='精简后_学术论文.docx'
)
```

**特点**：
- 优先使用
- 支持中文处理
- 专门针对日本史学术论文优化

### Minimax（备用）

```python
from modules.paper_polisher import create_paper_polisher

# 使用Minimax API
polisher = create_paper_polisher('minimax')

result = polisher.process_document(
    input_path='学术论文.docx',
    output_path='精简后_学术论文.docx'
)
```

**特点**：
- 备用方案
- 当通义千问不可用时使用
- 同样支持日文学术论文处理

---

## 🎯 高级功能

### 自定义系统提示词

```python
from modules.paper_polisher import create_paper_polisher

polisher = create_paper_polisher('qwen')

custom_prompt = """你是一位专业的学术论文编辑，擅长精简论文内容。
请重点关注以下几点：
1. 删除重复的论证
2. 精简冗长的表述
3. 保留核心学术贡献
"""

polisher.set_system_prompt(custom_prompt)
```

### 添加历史术语保护

```python
# 添加需要保护的历史术语
polisher.add_history_term("明治维新")
polisher.add_history_term("大正民主")

# 添加需要保护的历史人物
polisher.add_history_figure("伊藤博文")
polisher.add_history_figure("西乡隆盛")
```

### 段落级处理

```python
# 处理单个段落
paragraph_text = "这是需要精简的学术论文段落..."
modified_text, deletions = polisher.polish_paragraph(paragraph_text)

print(f"精简后: {modified_text}")
print(f"删除内容: {deletions}")
```

---

## 📊 处理结果

### 返回结果结构

```python
{
    'success': True,
    'input_file': 'input.docx',
    'output_file': 'output.docx',
    'total_paragraphs': 50,
    'processed_paragraphs': 48,
    'total_deletions': 15,
    'deletions': [
        {
            'text': '重复论证的内容...',
            'reason': '逻辑冗余'
        },
        ...
    ],
    'footnote_count': 5,
    'track_changes_enabled': True,
    'timestamp': '2024-03-27T12:00:00'
}
```

### 统计信息

- **总段落数**：文档中的正文段落总数
- **处理段落数**：实际处理的段落数（排除空段和脚注）
- **删除处数**：精简删除的内容数量
- **脚注数量**：保护的脚注数量

---

## ⚠️ 注意事项

### 1. 密钥安全

```bash
# 不要将密钥提交到版本控制系统
# 使用 .env 文件管理密钥
# .env 文件已加入 .gitignore
```

### 2. 文档备份

```python
# 处理前请备份原始文档
import shutil

# 创建备份
backup_path = 'input_backup.docx'
shutil.copy('input.docx', backup_path)

# 然后再处理
result = polisher.process_document('input.docx', 'output.docx')
```

### 3. 人工审核

```python
# 建议对处理结果进行人工审核
# 特别关注：
# - 学术准确性
# - 论证完整性
# - 历史事实保留
```

### 4. 网络连接

```python
# 需要稳定的网络连接以调用API
# 建议：
# - 使用有线网络
# - 确保防火墙允许API请求
# - 检查代理设置（如有需要）
```

---

## 🛠️ 技术架构

### 依赖库

- **python-docx**: Word文档处理
- **openai**: OpenAI兼容API接口
- **dashscope**: 阿里云SDK（通义千问）
- **requests**: HTTP请求
- **python-dotenv**: 环境变量管理

### 工作流程

```
输入文档 (.docx)
    ↓
解析文档结构
    ↓
识别正文与脚注
    ↓
逐段调用LLM精简
    ↓
应用修订追踪格式
    ↓
保存输出文档
    ↓
生成处理报告
```

---

## 📦 适用场景

1. **日本史学术论文初稿优化**
   - 精简冗长的初稿
   - 删除重复论证
   - 保留核心学术贡献

2. **历史研究文档内容精简**
   - 去除修辞重复
   - 保持史实准确
   - 保护历史术语

3. **学术期刊投稿前内容整理**
   - 符合期刊字数要求
   - 保持学术严谨性
   - 提升论文质量

4. **学位论文内容优化**
   - 精简绪论和结论
   - 删除冗余论述
   - 保护重要论证

---

## 🐛 故障排除

### 问题1: API调用失败

**症状**：
```
Error: API调用失败
```

**解决方案**：
1. 检查API密钥是否正确
2. 检查网络连接是否正常
3. 确认API配额是否充足

### 问题2: 文档格式问题

**症状**：
```
Error: 无法读取文档
```

**解决方案**：
1. 确保输入文档为标准.docx格式
2. 确认文档未损坏
3. 尝试重新保存文档

### 问题3: 处理速度慢

**症状**：
```
处理时间过长
```

**解决方案**：
1. 减少每次处理的段落数量
2. 调整API超时设置
3. 使用批处理模式

---

## 📚 相关文档

- [通义千问API文档](https://help.aliyun.com/document_detail/272912.html)
- [Minimax API文档](https://www.minimaxi.com/document)
- [python-docx文档](https://python-docx.readthedocs.io/)
- [项目主README](README.md)

---

## 📄 许可证

本工具仅供学术研究使用，请遵守相关学术规范和使用条款。

---

**版本**: 1.0.0  
**更新日期**: 2024年3月27日  
**API支持**: 阿里通义千问 (优先) | Minimax (备用)
