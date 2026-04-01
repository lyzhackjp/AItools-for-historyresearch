# IntelligentResearchAssistant 使用指南

## 目录

1. [快速入门](#快速入门)
2. [基础使用](#基础使用)
3. [进阶使用](#进阶使用)
4. [实战案例](#实战案例)
5. [最佳实践](#最佳实践)
6. [常见问题](#常见问题)

---

## 快速入门

### 安装与配置

#### 1. 环境要求

- Python 3.7+
- 网络连接（用于API调用和搜索）

#### 2. 安装依赖

```bash
pip install requests
```

#### 3. 配置API密钥

创建 `secrets/api_keys.txt` 文件或设置环境变量：

```bash
# 通义千问
export DASHSCOPE_API_KEY="your-api-key"

# OpenAI
export OPENAI_API_KEY="your-api-key"

# 其他提供商
export MINIMAX_API_KEY="your-api-key"
export ZHIPU_API_KEY="your-api-key"
export DEEPSEEK_API_KEY="your-api-key"
```

#### 4. 第一个程序

```python
from intelligent_research_assistant import IntelligentResearchAssistant

# 创建助手实例
assistant = IntelligentResearchAssistant(
    api_provider='qwen',
    test_mode=False
)

# 搜索项目
projects = assistant.search_projects('machine learning', limit=5)

# 显示结果
for project in projects:
    print(f"项目: {project.title}")
    print(f"URL: {project.url}")
    print(f"评分: {project.score}\n")
```

---

## 基础使用

### 1. 项目搜索

#### 基本搜索

```python
# 搜索GitHub项目
projects = assistant.search_projects('deep learning framework')

# 限制结果数量
projects = assistant.search_projects('nlp', limit=20)

# 指定平台
projects = assistant.search_projects(
    query='machine learning',
    platforms=['github'],
    limit=10
)
```

#### 处理搜索结果

```python
projects = assistant.search_projects('transformer', limit=10)

for project in projects:
    print(f"ID: {project.id}")
    print(f"标题: {project.title}")
    print(f"来源: {project.source}")
    print(f"URL: {project.url}")
    print(f"描述: {project.description}")
    print(f"评分: {project.score}")
    print(f"元数据: {project.metadata}")
    print("-" * 50)
```

### 2. 论文搜索

#### 基本搜索

```python
# 搜索学术论文
papers = assistant.search_papers('attention mechanism')

# 限制结果数量
papers = assistant.search_papers('BERT', limit=15)

# 指定数据源
papers = assistant.search_papers(
    query='natural language processing',
    sources=['arxiv'],
    limit=20
)
```

#### 处理论文结果

```python
papers = assistant.search_papers('GPT', limit=10)

for paper in papers:
    print(f"标题: {paper.title}")
    print(f"作者: {paper.metadata.get('authors', [])}")
    print(f"发表时间: {paper.metadata.get('published', '')}")
    print(f"摘要: {paper.description[:200]}...")
    print("-" * 50)
```

### 3. 项目分析

#### 单个项目分析

```python
# 搜索项目
projects = assistant.search_projects('pytorch', limit=1)

# 分析项目
analysis = assistant.analyze_project(projects[0])

# 查看分析结果
print(f"概述: {analysis.summary}")
print(f"\n关键发现:")
for finding in analysis.key_findings:
    print(f"  - {finding}")

print(f"\n技术要点:")
for point in analysis.technical_points:
    print(f"  - {point}")

print(f"\n建议:")
for rec in analysis.recommendations:
    print(f"  - {rec}")

print(f"\n置信度: {analysis.confidence}")
```

#### 不同分析深度

```python
# 快速分析（适合大量数据）
quick_analysis = assistant.analyze_project(
    project,
    analysis_depth='shallow'
)

# 标准分析
standard_analysis = assistant.analyze_project(
    project,
    analysis_depth='medium'
)

# 深度分析（适合重要项目）
deep_analysis = assistant.analyze_project(
    project,
    analysis_depth='deep'
)
```

### 4. 论文分析

```python
# 搜索论文
papers = assistant.search_papers('transformer', limit=1)

# 分析论文
analysis = assistant.analyze_paper(papers[0])

print(f"概述: {analysis.summary}")
print(f"研究方法: {analysis.technical_points}")
print(f"创新点: {analysis.key_findings}")
print(f"应用价值: {analysis.recommendations}")
```

### 5. 文献分析

```python
# 分析文献摘要
analysis = assistant.analyze_literature(
    summary="""
    BERT是一种预训练语言表示模型，通过在大规模文本语料上进行预训练，
    然后在下游任务上进行微调，取得了显著的性能提升。
    """,
    key_findings=[
        '双向编码器性能优于单向',
        '预训练-微调范式效果显著',
        'MLM任务有效提升语言理解'
    ],
    context='NLP预训练模型研究'
)

print(f"概述: {analysis.summary}")
print(f"技术要点: {analysis.technical_points}")
```

---

## 进阶使用

### 1. 批量处理

```python
# 批量搜索和分析
projects = assistant.search_projects('machine learning', limit=20)

analyses = []
for i, project in enumerate(projects):
    print(f"分析项目 {i+1}/{len(projects)}: {project.title}")
    analysis = assistant.analyze_project(project, analysis_depth='shallow')
    analyses.append(analysis)

print(f"\n完成 {len(analyses)} 个项目的分析")
```

### 2. 报告生成

```python
# 搜索项目
projects = assistant.search_projects('deep learning', limit=10)

# 分析项目
analyses = []
for project in projects[:5]:
    analysis = assistant.analyze_project(project, analysis_depth='shallow')
    analyses.append(analysis)

# 生成报告
report = assistant.generate_report(
    search_results=projects,
    analysis_results=analyses,
    title='深度学习项目分析报告'
)

# 保存报告
report.save('deep_learning_report.md')

print(f"报告已生成: {len(report.content)} 字符")
```

### 3. 改进建议生成

```python
# 搜索相关项目
projects = assistant.search_projects('NER named entity recognition', limit=10)

# 分析项目
analyses = [assistant.analyze_project(p, analysis_depth='shallow') for p in projects[:5]]

# 生成改进建议
suggestion = assistant.generate_improvements(
    module_name='ner_recognizer',
    context='日文史料实体识别',
    research_findings={
        'summary': '基于深度学习的NER方法在多个数据集上取得了最佳性能',
        'key_findings': [
            'BERT预训练模型效果显著',
            '序列标注方法仍是主流',
            '领域适配是关键挑战'
        ]
    }
)

print(f"短期建议: {suggestion.short_term}")
print(f"中期建议: {suggestion.medium_term}")
print(f"长期建议: {suggestion.long_term}")
print(f"优先级: {suggestion.priority}")
```

### 4. 一站式模块优化

```python
# 完整的模块优化分析流程
result = assistant.analyze_module_optimization(
    module_name='text_classifier',
    context='日文历史文献分类',
    search_limit=30,
    analysis_depth='deep'
)

# 访问结果
print("搜索结果:")
print(f"  项目数: {len(result['search_results']['projects'])}")
print(f"  论文数: {len(result['search_results']['papers'])}")

print("\n分析结果:")
print(f"  项目分析数: {len(result['analysis_results']['projects'])}")
print(f"  论文分析数: {len(result['analysis_results']['papers'])}")

print("\n报告:")
print(f"  长度: {len(result['report']['content'])} 字符")

print("\n改进建议:")
print(f"  优先级: {result['improvement_suggestion']['priority']}")

# 保存报告
with open('optimization_report.md', 'w', encoding='utf-8') as f:
    f.write(result['report']['content'])
```

---

## 实战案例

### 案例1: 研究某个技术领域

```python
def research_technology_field(assistant, field_name, context):
    """研究某个技术领域"""
    print(f"\n{'='*60}")
    print(f"研究领域: {field_name}")
    print(f"{'='*60}\n")
    
    # 搜索项目和论文
    print("[1] 搜索相关项目和论文...")
    projects = assistant.search_projects(field_name, limit=20)
    papers = assistant.search_papers(field_name, limit=20)
    
    print(f"  找到 {len(projects)} 个项目")
    print(f"  找到 {len(papers)} 篇论文")
    
    # 分析Top项目
    print("\n[2] 分析Top项目...")
    top_projects = sorted(projects, key=lambda x: x.score, reverse=True)[:5]
    
    project_analyses = []
    for i, project in enumerate(top_projects, 1):
        print(f"  分析 {i}/5: {project.title[:40]}...")
        analysis = assistant.analyze_project(project, analysis_depth='medium')
        project_analyses.append(analysis)
    
    # 分析Top论文
    print("\n[3] 分析Top论文...")
    top_papers = sorted(papers, key=lambda x: x.score, reverse=True)[:5]
    
    paper_analyses = []
    for i, paper in enumerate(top_papers, 1):
        print(f"  分析 {i}/5: {paper.title[:40]}...")
        analysis = assistant.analyze_paper(paper, analysis_depth='medium')
        paper_analyses.append(analysis)
    
    # 生成报告
    print("\n[4] 生成综合报告...")
    report = assistant.generate_report(
        search_results=projects + papers,
        analysis_results=project_analyses + paper_analyses,
        title=f'{field_name} 技术研究报告'
    )
    
    # 保存报告
    filename = f"{field_name.replace(' ', '_')}_report.md"
    report.save(filename)
    print(f"  报告已保存: {filename}")
    
    return {
        'projects': projects,
        'papers': papers,
        'project_analyses': project_analyses,
        'paper_analyses': paper_analyses,
        'report': report
    }

# 使用示例
assistant = IntelligentResearchAssistant(api_provider='qwen')
result = research_technology_field(
    assistant,
    field_name='knowledge graph',
    context='AI研究'
)
```

### 案例2: 模块功能优化

```python
def optimize_module(assistant, module_name, module_description):
    """优化模块功能"""
    print(f"\n{'='*60}")
    print(f"优化模块: {module_name}")
    print(f"{'='*60}\n")
    
    # 执行完整分析
    result = assistant.analyze_module_optimization(
        module_name=module_name,
        context=module_description,
        search_limit=40,
        analysis_depth='deep'
    )
    
    # 提取关键信息
    suggestion = result['improvement_suggestion']
    
    print("\n[改进建议]")
    print(f"\n短期改进 (1-3个月):")
    for i, item in enumerate(suggestion['short_term'][:5], 1):
        print(f"  {i}. {item}")
    
    print(f"\n中期改进 (3-6个月):")
    for i, item in enumerate(suggestion['medium_term'][:5], 1):
        print(f"  {i}. {item}")
    
    print(f"\n长期改进 (6-12个月):")
    for i, item in enumerate(suggestion['long_term'][:5], 1):
        print(f"  {i}. {item}")
    
    print(f"\n优先级: {suggestion['priority']}")
    print(f"置信度: {suggestion['confidence']}")
    
    # 保存报告
    report_filename = f"{module_name}_optimization_report.md"
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(result['report']['content'])
    
    print(f"\n详细报告已保存: {report_filename}")
    
    return result

# 使用示例
assistant = IntelligentResearchAssistant(api_provider='qwen')
result = optimize_module(
    assistant,
    module_name='ner_recognizer',
    module_description='日文历史文献命名实体识别'
)
```

### 案例3: 文献综述

```python
def literature_review(assistant, topic, limit=30):
    """文献综述"""
    print(f"\n{'='*60}")
    print(f"文献综述: {topic}")
    print(f"{'='*60}\n")
    
    # 搜索论文
    print("[1] 搜索相关论文...")
    papers = assistant.search_papers(topic, limit=limit)
    print(f"  找到 {len(papers)} 篇论文")
    
    # 分析论文
    print("\n[2] 分析论文...")
    analyses = []
    for i, paper in enumerate(papers[:15], 1):
        print(f"  分析 {i}/15: {paper.title[:50]}...")
        analysis = assistant.analyze_paper(paper, analysis_depth='shallow')
        analyses.append(analysis)
    
    # 提取关键信息
    print("\n[3] 提取关键信息...")
    all_findings = []
    all_points = []
    
    for analysis in analyses:
        all_findings.extend(analysis.key_findings)
        all_points.extend(analysis.technical_points)
    
    # 去重
    unique_findings = list(set(all_findings))[:10]
    unique_points = list(set(all_points))[:10]
    
    print(f"\n[关键发现] (前10个):")
    for i, finding in enumerate(unique_findings, 1):
        print(f"  {i}. {finding}")
    
    print(f"\n[技术要点] (前10个):")
    for i, point in enumerate(unique_points, 1):
        print(f"  {i}. {point}")
    
    # 生成综述报告
    print("\n[4] 生成综述报告...")
    report = assistant.generate_report(
        search_results=papers,
        analysis_results=analyses,
        title=f'{topic} 文献综述'
    )
    
    report.save(f'{topic.replace(" ", "_")}_literature_review.md')
    print(f"  综述报告已保存")
    
    return {
        'papers': papers,
        'analyses': analyses,
        'key_findings': unique_findings,
        'technical_points': unique_points,
        'report': report
    }

# 使用示例
assistant = IntelligentResearchAssistant(api_provider='qwen')
result = literature_review(
    assistant,
    topic='transformer attention mechanism',
    limit=30
)
```

---

## 最佳实践

### 1. 性能优化

#### 使用缓存

```python
# 启用缓存（默认）
assistant = IntelligentResearchAssistant(
    api_provider='qwen',
    cache_enabled=True,
    cache_ttl_days=7
)

# 第一次调用 - 调用API
result1 = assistant.analyze_literature(summary='test', key_findings=[])

# 第二次相同调用 - 使用缓存
result2 = assistant.analyze_literature(summary='test', key_findings=[])
```

#### 批量处理

```python
# 推荐：批量处理
projects = assistant.search_projects('ml', limit=50)
analyses = [assistant.analyze_project(p, analysis_depth='shallow') for p in projects]

# 不推荐：逐个处理大量数据
for i in range(100):
    projects = assistant.search_projects(f'topic_{i}', limit=10)
```

#### 选择合适的分析深度

```python
# 大量数据 - 使用浅层分析
for project in large_project_list:
    analysis = assistant.analyze_project(project, analysis_depth='shallow')

# 重要项目 - 使用深度分析
for important_project in important_projects:
    analysis = assistant.analyze_project(important_project, analysis_depth='deep')
```

### 2. 错误处理

```python
def safe_search(assistant, query, limit=10, retries=3):
    """安全的搜索函数"""
    for attempt in range(retries):
        try:
            results = assistant.search_projects(query, limit=limit)
            return results
        except Exception as e:
            print(f"搜索失败 (尝试 {attempt+1}/{retries}): {e}")
            if attempt == retries - 1:
                print("所有尝试均失败，返回空列表")
                return []
            time.sleep(2)  # 等待后重试

# 使用
results = safe_search(assistant, 'machine learning', limit=20)
```

### 3. 结果验证

```python
def validate_and_process(assistant, projects):
    """验证和处理搜索结果"""
    valid_projects = []
    
    for project in projects:
        # 验证必要字段
        if not project.title or not project.url:
            print(f"跳过无效项目: {project.id}")
            continue
        
        # 验证评分
        if project.score < 50:
            print(f"跳过低分项目: {project.title}")
            continue
        
        valid_projects.append(project)
    
    return valid_projects

# 使用
projects = assistant.search_projects('test', limit=50)
valid_projects = validate_and_process(assistant, projects)
```

---

## 常见问题

### Q1: 如何提高搜索结果的质量？

**A:**
1. 使用更具体的查询词
2. 增加搜索限制数量
3. 结合多个平台的搜索结果
4. 过滤低分结果

```python
# 使用具体查询
projects = assistant.search_projects('BERT Chinese NER', limit=30)

# 过滤高分结果
high_score_projects = [p for p in projects if p.score > 80]
```

### Q2: 如何处理大量数据？

**A:**
1. 分批处理
2. 使用缓存
3. 选择浅层分析
4. 定期保存中间结果

```python
# 分批处理
batch_size = 20
all_results = []

for i in range(0, len(large_list), batch_size):
    batch = large_list[i:i+batch_size]
    results = process_batch(assistant, batch)
    all_results.extend(results)
    
    # 保存中间结果
    save_intermediate_results(results, f'batch_{i}.json')
```

### Q3: 如何选择API提供商？

**A:** 根据需求选择：

| 提供商 | 优点 | 缺点 | 适用场景 |
|--------|------|------|----------|
| 通义千问 | 性价比高，中文好 | - | 通用场景 |
| OpenAI | 效果最好 | 价格高 | 高质量需求 |
| 智谱AI | 国产，性价比高 | - | 国产替代 |
| DeepSeek | 价格实惠 | 新兴 | 预算有限 |

### Q4: 如何调试问题？

**A:**
1. 使用测试模式
2. 检查日志输出
3. 验证API密钥
4. 检查网络连接

```python
# 测试模式
assistant = IntelligentResearchAssistant(
    api_provider='qwen',
    test_mode=True
)

# 检查统计信息
stats = assistant.get_stats()
print(f"LLM调用次数: {stats['llm_stats']['call_count']}")
print(f"缓存命中率: {stats['cache_stats']['hit_rate']}")
```

---

## 总结

本使用指南涵盖了 `IntelligentResearchAssistant` 的主要功能和使用方法。通过合理使用搜索、分析、报告生成等功能，可以高效地完成技术研究和模块优化工作。

关键要点：
- ✅ 使用缓存提高性能
- ✅ 选择合适的分析深度
- ✅ 批量处理大量数据
- ✅ 做好错误处理
- ✅ 定期保存中间结果

如有更多问题，请参考 [API文档](./API_DOCUMENTATION.md) 或 [迁移指南](./MIGRATION_GUIDE.md)。
