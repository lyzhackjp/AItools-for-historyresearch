"""
学习模块使用示例

展示如何使用学习模块的各个功能。
"""

from learning_module import LearningModule, ResearchAnalyzer, LiteratureAnalyzer, ImprovementGenerator


def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("基本使用示例")
    print("=" * 60)
    
    learner = LearningModule(api_provider='qwen', test_mode=True)
    
    result = learner.analyze_and_suggest(
        module_name='ner_processor',
        context='日文史料历史实体识别',
        research_topic='Japanese historical named entity recognition'
    )
    
    print(f"\n模块名称: {result['module_name']}")
    print(f"应用上下文: {result['context']}")
    print(f"\n研究发现摘要: {result['research_results'].get('summary', 'N/A')[:100]}...")
    print(f"\n改进建议数量:")
    print(f"  - 短期: {len(result['improvement_suggestions']['short_term_improvements'])}")
    print(f"  - 中期: {len(result['improvement_suggestions']['medium_term_improvements'])}")
    print(f"  - 长期: {len(result['improvement_suggestions']['long_term_improvements'])}")


def example_research_only():
    """仅检索学术资源示例"""
    print("\n" + "=" * 60)
    print("学术资源检索示例")
    print("=" * 60)
    
    researcher = ResearchAnalyzer(api_provider='qwen', test_mode=True)
    
    result = researcher.search_research(
        topic='named entity recognition deep learning',
        focus_areas=[
            'BERT-based NER methods',
            'Japanese NER challenges',
            'Historical text NER'
        ]
    )
    
    print(f"\n摘要: {result.get('summary', 'N/A')[:150]}...")
    print(f"\n关键发现 ({len(result.get('key_findings', []))} 项):")
    for finding in result.get('key_findings', [])[:3]:
        print(f"  - {finding}")


def example_prompt_optimization():
    """提示词优化示例"""
    print("\n" + "=" * 60)
    print("提示词优化示例")
    print("=" * 60)
    
    generator = ImprovementGenerator(api_provider='qwen', test_mode=True)
    
    current_prompt = """识别以下文本中的人名和地名：
输入：{text}
输出："""
    
    result = generator.suggest_prompt_optimization(
        current_prompt=current_prompt,
        task_type='命名实体识别',
        target_improvement='提高历史人名识别准确率'
    )
    
    print(f"\n任务类型: {result['task_type']}")
    print(f"优化建议: {result['optimized_prompt'][:200]}...")


def example_test_cases_generation():
    """测试用例生成示例"""
    print("\n" + "=" * 60)
    print("测试用例生成示例")
    print("=" * 60)
    
    generator = ImprovementGenerator(api_provider='qwen', test_mode=True)
    
    test_cases = generator.generate_test_cases(
        module_name='ner_processor',
        context='日文史料历史实体识别',
        num_cases=5
    )
    
    print(f"\n生成了 {len(test_cases)} 个测试用例:")
    for i, case in enumerate(test_cases, 1):
        print(f"  {i}. {case}")


def example_compare_methods():
    """方法比较示例"""
    print("\n" + "=" * 60)
    print("方法比较示例")
    print("=" * 60)
    
    analyzer = LiteratureAnalyzer(api_provider='qwen', test_mode=True)
    
    result = analyzer.compare_methods(
        method1='基于规则的方法（正则表达式+词典）',
        method2='基于深度学习的方法（BiLSTM-CRF）'
    )
    
    print(f"\n方法1: {result['method1']}")
    print(f"方法2: {result['method2']}")
    print(f"\n比较结果:\n{result['comparison'][:300]}...")


if __name__ == '__main__':
    print("学习模块使用示例")
    print("注意: 以下示例在 test_mode=True 时不会调用真实API")
    print()
    
    try:
        example_basic_usage()
    except Exception as e:
        print(f"\n基本示例执行出错: {e}")
    
    try:
        example_research_only()
    except Exception as e:
        print(f"\n检索示例执行出错: {e}")
    
    try:
        example_prompt_optimization()
    except Exception as e:
        print(f"\n提示词优化示例执行出错: {e}")
    
    try:
        example_test_cases_generation()
    except Exception as e:
        print(f"\n测试用例生成示例执行出错: {e}")
    
    try:
        example_compare_methods()
    except Exception as e:
        print(f"\n方法比较示例执行出错: {e}")
    
    print("\n" + "=" * 60)
    print("所有示例执行完成")
    print("=" * 60)
