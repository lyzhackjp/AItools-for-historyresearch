# OpenSourceFinder 快速参考卡

## 🚀 最快开始

### 一行命令
```bash
cd learning_module
python open_source_quick_start.py
```

### 三行代码
```python
from learning_module import OpenSourceFinder
finder = OpenSourceFinder(test_mode=True)
results = finder.search_all('ocr', '日文OCR')
```

## 📋 常用命令

### 基本搜索
```python
finder.search_all('ocr_processor', '日文OCR')
```

### 仅 GitHub
```python
finder.search_github('easyocr', limit=10)
```

### 仅 HuggingFace
```python
finder.search_huggingface('japanese ocr', limit=10)
```

### 生成报告
```python
finder.generate_integration_report(results, 'ocr', '日文OCR')
```

### 保存结果
```python
finder.save_report(report, 'report.json')
finder.save_search_results(results, 'results.json')
```

## ⚡ 快速优化流程

```python
from learning_module import OpenSourceFinder

finder = OpenSourceFinder(test_mode=True)

# 1. 搜索
results = finder.search_all('ocr_processor', '日文OCR')

# 2. 过滤
filtered = finder.rank_and_filter(results, min_stars=50)

# 3. 报告
report = finder.generate_integration_report(filtered, 'ocr', '日文OCR')

# 4. 保存
finder.save_report(report, 'ocr_report.json')

# 5. 优化
optimization = finder.execute_optimization(report, 'modules/ocr.py')
```

## 🎯 评分阈值

| 级别 | GitHub Stars | HuggingFace Downloads | 评分范围 |
|------|-------------|----------------------|---------|
| 高质量 | ≥1000 | ≥50000 | 70-100 |
| 中等 | 100-1000 | 1000-50000 | 40-70 |
| 低质量 | <100 | <1000 | 0-40 |

## 📊 评分权重速查

### GitHub
- ⭐ Stars: 40%
- 🍴 Forks: 20%
- 👁 Watchers: 15%
- 🐛 Issues: 10%
- 🏷 Topics: 15%

### HuggingFace
- 📥 Downloads: 50%
- ❤️ Likes: 30%
- 🏷 Tags: 20%

## 💡 关键词建议

### OCR 相关
```
ocr, text recognition, handwriting recognition
easyocr, paddleocr, tesseract
japanese ocr, chinese ocr
document recognition, pdf ocr
```

### NER 相关
```
ner, named entity recognition
entity extraction, spaCy
japanese ner, multilingual ner
transformers ner, bert ner
```

### 其他
```
embedding, text similarity
document processing, pdf parsing
chatbot, dialogue system
```

## 🔧 参数配置

### 初始化
```python
finder = OpenSourceFinder(
    api_provider='qwen',     # qwen, openai, zhipu, deepseek
    test_mode=False,         # True = 测试数据
    github_token='token'     # 可选，提高 API 限制
)
```

### 搜索
```python
finder.search_github(
    query='keyword',
    limit=10,
    language='python'         # python, javascript, etc.
)
```

### 过滤
```python
finder.rank_and_filter(
    results,
    min_stars=50,            # 默认: 50
    min_downloads=1000        # 默认: 1000
)
```

## 📁 输出文件

### 搜索结果
- `ocr_optimization_search_results.json`
- `search_results.json`

### 报告
- `ocr_optimization_integration_report.json`
- `integration_report.json`

## 🎨 整合难度标识

| 标识 | 含义 | GitHub Stars | HuggingFace Downloads |
|------|------|-------------|----------------------|
| 🟢 easy | 易于整合 | >5000 | >50000 |
| 🟡 medium | 中等难度 | 1000-5000 | 10000-50000 |
| 🔴 hard | 较难整合 | <1000 | <10000 |

## ⚠️ 常见问题

### Q: API 限制？
A: 设置 GitHub Token 提高限制
```python
finder = OpenSourceFinder(github_token='your-token')
```

### Q: 搜索结果太少？
A: 增加关键词
```python
keywords = ['ocr', 'easyocr', 'japanese ocr', 'text recognition']
results = finder.search_all('ocr', 'OCR', keywords=keywords)
```

### Q: LLM 不可用？
A: 使用基础模式自动降级
```python
finder = OpenSourceFinder(test_mode=True)
# 自动使用基础评分和报告
```

### Q: 如何提高搜索质量？
A: 使用更具体的关键词
```python
keywords = [
    'easyocr',           # 具体的库名
    'japanese ocr',       # 具体语言
    'handwriting recognition'  # 具体任务
]
```

## 📚 学习资源

- [详细使用指南](OPEN_SOURCE_FINDER_README.md)
- [完整总结](OPEN_SOURCE_FINDER_SUMMARY.md)
- [示例代码](open_source_finder_example.py)
- [OCR 优化测试](test_ocr_optimization.py)

## 🎯 下一步

1. ✅ 尝试快速启动: `python open_source_quick_start.py`
2. ✅ 查看示例: `python open_source_finder_example.py`
3. ✅ 测试优化: `python test_ocr_optimization.py`
4. 📝 审查生成的报告
5. 🔍 评估推荐的仓库/模型
6. 🚀 制定优化计划

## 📞 需要帮助？

查看完整文档：
- 📖 [使用指南](OPEN_SOURCE_FINDER_README.md)
- 📊 [工作流程](WORKFLOW_DIAGRAM.md)（第十二部分）
- 🔧 [详细总结](OPEN_SOURCE_FINDER_SUMMARY.md)

---

**版本**: 1.1.0 | **创建日期**: 2026-03-29 | **状态**: ✅ 生产就绪
