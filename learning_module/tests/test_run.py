"""
学习模块测试运行脚本

测试学习模块的各项核心功能，记录测试结果。
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from learning_module import LearningModule, ResearchAnalyzer, LiteratureAnalyzer, ImprovementGenerator


def test_research_analyzer():
    """测试学术资源检索功能"""
    print("\n" + "="*60)
    print("测试1：学术资源检索 (ResearchAnalyzer)")
    print("="*60)
    
    try:
        researcher = ResearchAnalyzer(api_provider='qwen', test_mode=True)
        
        result = researcher.search_research(
            topic='Japanese Historical Named Entity Recognition',
            focus_areas=[
                'Deep Learning NER Methods',
                'Historical Text Processing',
                'Japanese Language NER'
            ]
        )
        
        print(f"\n✓ 检索成功！")
        print(f"  - 摘要长度: {len(result.get('summary', ''))} 字符")
        print(f"  - 关键发现数量: {len(result.get('key_findings', []))}")
        print(f"  - 技术方法数量: {len(result.get('methods', []))}")
        print(f"  - 应用场景数量: {len(result.get('applications', []))}")
        print(f"  - 发展趋势数量: {len(result.get('trends', []))}")
        
        return True, result
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        return False, None


def test_literature_analyzer():
    """测试文献分析功能"""
    print("\n" + "="*60)
    print("测试2：文献分析 (LiteratureAnalyzer)")
    print("="*60)
    
    try:
        analyzer = LiteratureAnalyzer(api_provider='qwen', test_mode=True)
        
        sample_summary = """
        Named Entity Recognition (NER) is a fundamental NLP task that involves
        identifying and classifying named entities such as person names, locations,
        organizations, dates, and other predefined categories. Recent advances in
        deep learning, particularly transformer-based models like BERT, have
        significantly improved NER performance.
        """
        
        sample_findings = [
            "BERT-based models achieve state-of-the-art results on NER tasks",
            "Contextual embeddings capture rich semantic information",
            "Multi-task learning can improve NER performance"
        ]
        
        result = analyzer.analyze_literature(sample_summary, sample_findings)
        
        print(f"\n✓ 分析成功！")
        print(f"  - 技术要点数量: {len(result.get('technical_points', []))}")
        print(f"  - 实现建议数量: {len(result.get('implementation_suggestions', []))}")
        print(f"  - 最佳实践数量: {len(result.get('best_practices', []))}")
        print(f"  - 局限性数量: {len(result.get('limitations', []))}")
        
        return True, result
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        return False, None


def test_improvement_generator():
    """测试改进建议生成功能"""
    print("\n" + "="*60)
    print("测试3：改进建议生成 (ImprovementGenerator)")
    print("="*60)
    
    try:
        generator = ImprovementGenerator(api_provider='qwen', test_mode=True)
        
        sample_research = {
            'summary': 'Recent advances in NER include transformer-based models.',
            'key_findings': ['BERT achieves SOTA', 'Context matters'],
            'trends': ['Multi-lingual models', 'Few-shot learning']
        }
        
        sample_literature = {
            'technical_points': ['Attention mechanism', 'Pre-training'],
            'implementation_suggestions': ['Use fine-tuned models']
        }
        
        result = generator.generate_improvements(
            module_name='ner_processor',
            context='Japanese historical text NER',
            research_findings=sample_research,
            literature_insights=sample_literature
        )
        
        print(f"\n✓ 生成成功！")
        print(f"  - 短期改进数量: {len(result.get('short_term_improvements', []))}")
        print(f"  - 中期改进数量: {len(result.get('medium_term_improvements', []))}")
        print(f"  - 长期改进数量: {len(result.get('long_term_improvements', []))}")
        print(f"  - 优先级: {result.get('priority', 'N/A')}")
        
        return True, result
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        return False, None


def test_learning_module_integration():
    """测试学习模块综合功能"""
    print("\n" + "="*60)
    print("测试4：学习模块综合分析 (LearningModule)")
    print("="*60)
    
    try:
        learner = LearningModule(api_provider='qwen', test_mode=True)
        
        result = learner.analyze_and_suggest(
            module_name='ner_processor',
            context='Japanese historical entity recognition',
            research_topic='Japanese Historical NER Deep Learning BERT'
        )
        
        print(f"\n✓ 综合分析成功！")
        print(f"  - 模块名称: {result['module_name']}")
        print(f"  - 应用上下文: {result['context']}")
        
        research = result.get('research_results', {})
        literature = result.get('literature_analysis', {})
        suggestions = result.get('improvement_suggestions', {})
        
        print(f"\n  研究结果:")
        print(f"    - 摘要: {len(research.get('summary', ''))} 字符")
        print(f"    - 关键发现: {len(research.get('key_findings', []))} 项")
        
        print(f"\n  文献分析:")
        print(f"    - 技术要点: {len(literature.get('technical_points', []))} 项")
        print(f"    - 实现建议: {len(literature.get('implementation_suggestions', []))} 项")
        
        print(f"\n  改进建议:")
        print(f"    - 短期: {len(suggestions.get('short_term_improvements', []))} 项")
        print(f"    - 中期: {len(suggestions.get('medium_term_improvements', []))} 项")
        print(f"    - 长期: {len(suggestions.get('long_term_improvements', []))} 项")
        print(f"    - 优先级: {suggestions.get('priority', 'N/A')}")
        
        return True, result
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        return False, None


def test_advanced_features():
    """测试高级功能"""
    print("\n" + "="*60)
    print("测试5：高级功能测试")
    print("="*60)
    
    try:
        generator = ImprovementGenerator(api_provider='qwen', test_mode=True)
        
        print("\n5.1 测试用例生成:")
        test_cases = generator.generate_test_cases(
            module_name='ner_processor',
            context='Japanese historical entity recognition',
            num_cases=3
        )
        print(f"    ✓ 生成了 {len(test_cases)} 个测试用例")
        
        print("\n5.2 提示词优化建议:")
        optimization = generator.suggest_prompt_optimization(
            current_prompt='识别以下文本中的人名和地名：{text}',
            task_type='命名实体识别',
            target_improvement='提高历史人名识别准确率'
        )
        print(f"    ✓ 提示词优化建议生成成功")
        print(f"    - 任务类型: {optimization.get('task_type')}")
        
        analyzer = LiteratureAnalyzer(api_provider='qwen', test_mode=True)
        
        print("\n5.3 方法比较:")
        comparison = analyzer.compare_methods(
            method1='基于规则的方法（正则表达式+词典）',
            method2='基于深度学习的方法（BiLSTM-CRF）'
        )
        print(f"    ✓ 方法比较完成")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 高级功能测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("\n" + "="*70)
    print(" " * 15 + "学习模块测试运行报告")
    print("="*70)
    print(f"\n测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试模式: test_mode=True (模拟API调用)")
    
    results = {}
    
    success1, data1 = test_research_analyzer()
    results['research_analyzer'] = success1
    
    success2, data2 = test_literature_analyzer()
    results['literature_analyzer'] = success2
    
    success3, data3 = test_improvement_generator()
    results['improvement_generator'] = success3
    
    success4, data4 = test_learning_module_integration()
    results['learning_module'] = success4
    
    success5 = test_advanced_features()
    results['advanced_features'] = success5
    
    print("\n" + "="*70)
    print(" " * 20 + "测试结果汇总")
    print("="*70)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    failed_tests = total_tests - passed_tests
    
    for test_name, success in results.items():
        status = "✓ 通过" if success else "✗ 失败"
        print(f"  {test_name:30s} : {status}")
    
    print(f"\n总计: {total_tests} 个测试")
    print(f"  - 通过: {passed_tests}")
    print(f"  - 失败: {failed_tests}")
    print(f"  - 通过率: {passed_tests/total_tests*100:.1f}%")
    
    print("\n" + "="*70)
    
    if failed_tests == 0:
        print(" " * 20 + "🎉 所有测试通过！")
    else:
        print(" " * 20 + "⚠️ 部分测试失败，请检查日志")
    
    print("="*70 + "\n")
    
    return failed_tests == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
