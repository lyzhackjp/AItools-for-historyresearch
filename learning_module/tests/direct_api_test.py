"""
直接NER优化API测试脚本

自动执行，不等待用户输入。
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.api_key_manager import load_all_api_keys
load_all_api_keys()

from learning_module import LearningModule


def test_qwen():
    """测试Qwen API"""
    print("\n" + "="*70)
    print("测试Qwen API (通义千问)")
    print("="*70)
    
    try:
        print("初始化中...")
        learner = LearningModule(api_provider='qwen', test_mode=False)
        print("✓ 初始化成功")
        
        print("执行NER优化分析...")
        result = learner.analyze_and_suggest(
            module_name='ner_processor',
            context='Japanese historical entity recognition',
            research_topic='Japanese Historical NER'
        )
        
        print("\n✓ 分析完成!")
        print(f"模块: {result['module_name']}")
        
        suggestions = result.get('improvement_suggestions', {})
        short = suggestions.get('short_term_improvements', [])
        medium = suggestions.get('medium_term_improvements', [])
        long_term = suggestions.get('long_term_improvements', [])
        
        print(f"\n短期改进 ({len(short)}项):")
        for s in short[:3]:
            print(f"  - {s}")
        
        print(f"\n中期改进 ({len(medium)}项):")
        for m in medium[:3]:
            print(f"  - {m}")
        
        return True, result
        
    except Exception as e:
        print(f"\n✗ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_minimax():
    """测试Minimax API"""
    print("\n" + "="*70)
    print("测试Minimax API")
    print("="*70)
    
    try:
        print("初始化中...")
        learner = LearningModule(api_provider='minimax', test_mode=False)
        print("✓ 初始化成功")
        
        print("执行NER优化分析...")
        result = learner.analyze_and_suggest(
            module_name='ner_processor',
            context='Japanese historical entity recognition',
            research_topic='Japanese Historical NER'
        )
        
        print("\n✓ 分析完成!")
        print(f"模块: {result['module_name']}")
        
        suggestions = result.get('improvement_suggestions', {})
        short = suggestions.get('short_term_improvements', [])
        
        print(f"\n短期改进 ({len(short)}项):")
        for s in short[:3]:
            print(f"  - {s}")
        
        return True, result
        
    except Exception as e:
        print(f"\n✗ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    print("\n" + "="*70)
    print("NER模块API优化测试")
    print("="*70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n开始Qwen API测试...")
    success1, qwen_result = test_qwen()
    
    if success1:
        print("\n✓ Qwen API测试成功")
    else:
        print("\n✗ Qwen API测试失败")
    
    print("\n开始Minimax API测试...")
    success2, minimax_result = test_minimax()
    
    if success2:
        print("\n✓ Minimax API测试成功")
    else:
        print("\n✗ Minimax API测试失败")
    
    print("\n" + "="*70)
    print("测试完成")
    print("="*70)
    
    if success1 and success2:
        print("\n两种API测试均成功!可以继续进行NER模块优化。")
    elif success1:
        print("\n仅Qwen API成功，建议使用Qwen进行优化。")
    elif success2:
        print("\n仅Minimax API成功，建议使用Minimax进行优化。")
    else:
        print("\n两种API均失败，请检查API密钥和网络连接。")


if __name__ == '__main__':
    main()
