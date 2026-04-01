# open_source_finder 提示词文档

## 模块说明

开源项目深度搜寻与分析模块，集成LLM进行项目深度分析、论文内容解析和研究趋势预测。

### 核心功能
- README深度解析
- 论文内容结构化提取
- 项目技术深度分析
- 研究趋势预测
- 增强报告生成

---

## 系统提示词

### [OSF_G001] - 开源项目分析专家系统提示词

- **描述**: 设定LLM为开源项目分析专家
- **使用场景**: 项目深度分析、技术评估
- **标识符**: OSF_G001
- **创建日期**: 2026-04-01

**内容**:

```
你是一位资深的技术架构师和开源项目分析专家，专精于开源项目的技术评估和趋势分析。

你的专长包括：
1. 深度分析项目的技术架构和实现方案
2. 评估项目的创新性和技术难度
3. 识别项目的应用场景和目标用户
4. 分析项目的社区健康度和维护持续性
5. 评估项目的集成难度和潜在风险
6. 预测技术发展趋势和研究方向

请严格按照JSON格式输出分析结果，确保结构清晰、数据准确。
```

---

## 用户提示词

### [OSF_U001] - README深度解析提示词

- **描述**: 深度解析GitHub项目的README文件
- **使用场景**: 调用analyze_readme方法时使用
- **标识符**: OSF_U001
- **创建日期**: 2026-04-01

**内容**:

```
请深度分析以下GitHub项目的README文件，提取关键信息。

【项目信息】
- 名称：{project_name}
- Stars：{stars}
- 最近更新：{last_updated}
- URL：{project_url}

【README内容】
{readme_content}

请从以下维度进行分析，并以JSON格式输出：

{{
  "project_overview": {{
    "description": "<项目概述（50字以内）>",
    "main_purpose": "<主要目的>",
    "target_users": ["<目标用户1>", "<目标用户2>"]
  }},
  "technical_analysis": {{
    "core_technology": ["<核心技术1>", "<核心技术2>"],
    "tech_stack": {{
      "languages": ["<编程语言>"],
      "frameworks": ["<框架>"],
      "dependencies": ["<关键依赖>"]
    }},
    "architecture_pattern": "<架构模式>",
    "innovations": ["<创新点1>", "<创新点2>"]
  }},
  "feature_analysis": {{
    "key_features": [
      {{"feature": "<功能名称>", "description": "<功能描述>", "maturity": "<成熟度：high/medium/low>"}}
    ],
    "limitations": ["<局限性1>", "<局限性2>"]
  }},
  "usage_evaluation": {{
    "installation_difficulty": "<安装难度：easy/medium/hard>",
    "learning_curve": "<学习曲线：gentle/moderate/steep>",
    "documentation_quality": "<文档质量：excellent/good/fair/poor>",
    "example_availability": "<示例完整性：comprehensive/adequate/limited>"
  }},
  "integration_assessment": {{
    "difficulty_level": "<集成难度：easy/medium/hard>",
    "requirements": ["<系统要求1>", "<系统要求2>"],
    "dependencies": ["<依赖项1>", "<依赖项2>"],
    "estimated_effort": "<预估工作量>",
    "potential_issues": ["<潜在问题1>", "<潜在问题2>"]
  }},
  "community_health": {{
    "activity_level": "<活跃度：very_active/active/moderate/low>",
    "maintainability": "<可维护性：excellent/good/fair/poor>",
    "support_quality": "<支持质量：excellent/good/fair/poor>",
    "contribution_ease": "<贡献友好度：high/medium/low>"
  }},
  "risk_assessment": {{
    "maintenance_risk": {{
      "level": "<风险等级：low/medium/high>",
      "reasons": ["<原因1>", "<原因2>"]
    }},
    "dependency_risk": {{
      "level": "<风险等级>",
      "reasons": ["<原因1>"]
    }},
    "license_risk": {{
      "level": "<风险等级>",
      "license_type": "<许可证类型>",
      "restrictions": ["<限制条件>"]
    }}
  }},
  "overall_evaluation": {{
    "technical_score": <技术评分 1-10>,
    "practical_score": <实用评分 1-10>,
    "community_score": <社区评分 1-10>,
    "recommendation_level": "<推荐等级：strongly_recommend/recommend/consider/not_recommend>",
    "key_takeaways": ["<关键要点1>", "<关键要点2>", "<关键要点3>"]
  }}
}}
```

**模板变量说明**:
- `{project_name}`: 项目名称
- `{stars}`: Star数量
- `{last_updated}`: 最近更新时间
- `{project_url}`: 项目URL
- `{readme_content}`: README文件内容

---

### [OSF_U002] - 论文深度分析提示词

- **描述**: 深度分析学术论文内容
- **使用场景**: 调用analyze_paper方法时使用
- **标识符**: OSF_U002
- **创建日期**: 2026-04-01

**内容**:

```
请深度分析以下学术论文，提取关键信息。

【论文信息】
- 标题：{paper_title}
- 作者：{authors}
- 发表时间：{publish_date}
- 来源：{source}

【论文内容】
{paper_content}

请从以下维度进行分析，并以JSON格式输出：

{{
  "research_overview": {{
    "main_question": "<核心研究问题>",
    "research_gap": "<研究空白>",
    "contribution": "<主要贡献>"
  }},
  "methodology_analysis": {{
    "approach": "<研究方法>",
    "techniques": ["<技术手段1>", "<技术手段2>"],
    "innovation": "<方法论创新点>",
    "limitations": ["<方法局限性1>", "<方法局限性2>"]
  }},
  "key_findings": {{
    "main_results": ["<主要发现1>", "<主要发现2>"],
    "performance_metrics": {{
      "<指标名称>": "<指标值>"
    }},
    "comparisons": ["<与其他方法的对比>"]
  }},
  "practical_implications": {{
    "applications": ["<应用场景1>", "<应用场景2>"],
    "impact": "<实际影响>",
    "implementation_feasibility": "<实现可行性：high/medium/low>"
  }},
  "future_directions": {{
    "suggested_improvements": ["<改进建议1>", "<改进建议2>"],
    "open_questions": ["<开放问题1>", "<开放问题2>"],
    "research_opportunities": ["<研究机会1>", "<研究机会2>"]
  }},
  "quality_assessment": {{
    "novelty_score": <创新性评分 1-10>,
    "rigor_score": <严谨性评分 1-10>,
    "significance_score": <重要性评分 1-10>,
    "reproducibility": "<可复现性：high/medium/low>"
  }},
  "relevance_assessment": {{
    "relevance_to_field": "<与领域相关性>",
    "potential_impact": "<潜在影响>",
    "recommended_actions": ["<推荐行动1>", "<推荐行动2>"]
  }}
}}
```

**模板变量说明**:
- `{paper_title}`: 论文标题
- `{authors}`: 作者列表
- `{publish_date}`: 发表时间
- `{source}`: 来源（arXiv等）
- `{paper_content}`: 论文内容（摘要、方法论等）

---

### [OSF_U003] - 研究趋势分析提示词

- **描述**: 分析特定领域的研究趋势
- **使用场景**: 调用analyze_trends方法时使用
- **标识符**: OSF_U003
- **创建日期**: 2026-04-01

**内容**:

```
请分析以下{focus_area}领域的开源项目和论文，总结研究趋势。

【项目概览】
{projects_summary}

【统计信息】
- 项目总数：{total_projects}
- 时间范围：{time_range}
- 主要平台：{platforms}

请从以下角度进行分析，并以JSON格式输出：

{{
  "emerging_technologies": [
    {{
      "technology": "<技术名称>",
      "description": "<技术描述>",
      "momentum": "<发展趋势：rising/stable/declining>",
      "project_count": <相关项目数>,
      "key_projects": ["<代表性项目1>", "<代表性项目2>"]
    }}
  ],
  "popular_frameworks": [
    {{
      "framework": "<框架名称>",
      "usage_count": <使用次数>,
      "trend": "<趋势>",
      "alternatives": ["<替代方案>"]
    }}
  ],
  "research_directions": [
    {{
      "direction": "<研究方向>",
      "description": "<方向描述>",
      "activity_level": "<活跃度>",
      "key_papers": ["<关键论文>"]
    }}
  ],
  "technology_landscape": {{
    "main_categories": ["<主要技术类别>"],
    "convergence_points": ["<技术融合点>"],
    "gap_areas": ["<空白领域>"]
  }},
  "market_trends": {{
    "industry_adoption": "<行业采用情况>",
    "commercialization": "<商业化程度>",
    "investment_focus": "<投资热点>"
  }},
  "future_predictions": {{
    "short_term": "<短期预测（6-12个月）>",
    "medium_term": "<中期预测（1-2年）>",
    "long_term": "<长期预测（3-5年）>",
    "disruptive_factors": ["<颠覆性因素>"]
  }},
  "actionable_insights": [
    {{
      "insight": "<洞察内容>",
      "priority": "<优先级：high/medium/low>",
      "action": "<建议行动>"
    }}
  ]
}}
```

**模板变量说明**:
- `{focus_area}`: 关注领域名称
- `{projects_summary}`: 项目摘要列表
- `{total_projects}`: 项目总数
- `{time_range}`: 时间范围
- `{platforms}`: 主要平台列表

---

### [OSF_U004] - 增强报告生成提示词

- **描述**: 生成综合分析报告
- **使用场景**: 调用generate_enhanced_report方法时使用
- **标识符**: OSF_U004
- **创建日期**: 2026-04-01

**内容**:

```
请基于以下分析结果，生成一份综合性的{focus_area}领域深度分析报告。

【分析数据】
{analysis_data}

【报告要求】
1. 结构清晰，层次分明
2. 重点突出，数据支撑
3. 实用性强，可操作

请按以下结构生成报告：

# {focus_area}领域深度分析报告

## 📊 执行摘要
<生成200字以内的执行摘要，包含关键发现和核心建议>

## 🔥 Top项目深度分析
<选择Top 5项目，每个项目包含：
- 项目名称和评分
- 技术深度分析
- 实用价值评估
- 集成难度评估
- 风险评估
- 综合推荐>

## 📈 研究趋势分析
<包含：
- 新兴技术方向
- 主流技术栈
- 研究方向分布
- 未来预测>

## 💡 行动建议
<分级建议：
- 立即行动（高优先级）
- 中期规划（中优先级）
- 长期关注（低优先级）>

## ⚠️ 风险提示
<列出主要风险和应对措施>

## 📚 参考资源
<列出关键项目和论文链接>
```

**模板变量说明**:
- `{focus_area}`: 关注领域名称
- `{analysis_data}`: 分析数据（JSON格式）

---

## 使用示例

### 示例1：README深度解析

```python
from open_source_finder.src.enhanced_analyzer import EnhancedAnalyzer

analyzer = EnhancedAnalyzer(api_provider='qwen')

result = analyzer.analyze_readme(
    project_name="vibe-coding-cn",
    stars=1250,
    last_updated="2026-03-30",
    project_url="https://github.com/user/vibe-coding-cn",
    readme_content="..."
)

print(result['technical_analysis']['core_technology'])
# 输出: ['LLM', 'Code Generation', 'AI Assistant']
```

### 示例2：研究趋势分析

```python
from open_source_finder.src.enhanced_analyzer import EnhancedAnalyzer

analyzer = EnhancedAnalyzer(api_provider='qwen')

trends = analyzer.analyze_trends(
    focus_area="Vibe Coding",
    projects_summary="...",
    total_projects=25
)

print(trends['emerging_technologies'])
# 输出: [{'technology': 'Multi-modal Code Understanding', 'momentum': 'rising', ...}]
```

---

## 注意事项

1. **API调用频率**: 避免频繁调用，建议使用缓存机制
2. **响应解析**: 所有响应均为JSON格式，需要正确解析
3. **错误处理**: 添加完善的错误处理和重试机制
4. **测试模式**: 支持test_mode，使用模拟数据进行测试

---

**文档版本**: 1.0.0
**最后更新**: 2026-04-01
**维护者**: AI History Research Tools Team
