"""
NER优化学习测试 - 修复版

该脚本用于测试学习模块是否能够正确调用API。
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.api_key_manager import load_all_api_keys
load_all_api_keys()

results = {
    'timestamp': datetime.now().isoformat(),
    'tests': []
}

print("开始NER模块学习测试...")
print("=" * 70)

print("\n【测试1】使用Qwen API进行学术资源检索")
try:
    from learning_module import ResearchAnalyzer
    researcher = ResearchAnalyzer(api_provider='qwen', test_mode=False)
    
    result = researcher.search_research(
        topic='Japanese Historical Named Entity Recognition',
        focus_areas=['BERT NER', 'Japanese language NER', 'Historical text NER']
    )
    
    print(f"✓ Qwen API检索成功")
    print(f"  - 摘要: {result.get('summary', '')[:100]}...")
    print(f"  - 关键发现: {len(result.get('key_findings', []))}项")
    
    results['tests'].append({
        'name': 'Qwen API Research',
        'status': 'success',
        'summary': result.get('summary', ''),
        'findings': result.get('key_findings', [])
    })
    
except Exception as e:
    print(f"✗ Qwen API检索失败: {e}")
    import traceback
    traceback.print_exc()
    results['tests'].append({
        'name': 'Qwen API Research',
        'status': 'failed',
        'error': str(e)
    })

print("\n【测试2】使用Minimax API进行文献分析")
try:
    from learning_module import LiteratureAnalyzer
    analyzer = LiteratureAnalyzer(api_provider='minimax', test_mode=False)
    
    result = analyzer.analyze_literature(
        summary='This is a test summary about NER.',
        key_findings=['BERT is effective for NER', 'Context matters']
    )
    
    print(f"✓ Minimax API分析成功")
    print(f"  - 技术要点: {len(result.get('technical_points', []))}项")
    print(f"  - 实现建议: {len(result.get('implementation_suggestions', []))}项")
    
    results['tests'].append({
        'name': 'Minimax API Analysis',
        'status': 'success',
        'technical_points': result.get('technical_points', []),
        'suggestions': result.get('implementation_suggestions', [])
    })
    
except Exception as e:
    print(f"✗ Minimax API分析失败: {e}")
    import traceback
    traceback.print_exc()
    results['tests'].append({
        'name': 'Minimax API Analysis',
        'status': 'failed',
        'error': str(e)
    })

print("\n【测试3】NER模块优化建议生成")
try:
    from learning_module import ImprovementGenerator
    generator = ImprovementGenerator(api_provider='qwen', test_mode=False)
    
    result = generator.generate_improvements(
        module_name='ner_processor',
        context='Japanese historical entity recognition',
        research_findings={
            'summary': 'NER research findings',
            'key_findings': ['BERT effective', 'Context matters'],
            'trends': ['LLM-based NER', 'Few-shot learning']
        },
        literature_insights={
            'technical_points': ['Pre-training', 'Fine-tuning'],
            'implementation_suggestions': ['Use domain dictionary']
        }
    )
    
    print(f"✓ NER优化建议生成成功")
    print(f"  - 短期改进: {len(result.get('short_term_improvements', []))}项")
    print(f"  - 中期改进: {len(result.get('medium_term_improvements', []))}项")
    print(f"  - 优先级: {result.get('priority', 'N/A')}")
    
    results['tests'].append({
        'name': 'NER Optimization Suggestions',
        'status': 'success',
        'suggestions': result
    })
    
except Exception as e:
    print(f"✗ NER优化建议生成失败: {e}")
    import traceback
    traceback.print_exc()
    results['tests'].append({
        'name': 'NER Optimization Suggestions',
        'status': 'failed',
        'error': str(e)
    })

print("\n" + "=" * 70)
print("测试完成!")

success_count = sum(1 for t in results['tests'] if t['status'] == 'success')
total_count = len(results['tests'])
print(f"成功: {success_count}/{total_count}")

output_file = 'learning_module/learning_test_results_v2.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n结果已保存到: {output_file}")
