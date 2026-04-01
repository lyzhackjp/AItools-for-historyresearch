"""
集成测试 - 功能测试

测试IntelligentResearchAssistant的完整功能流程
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from intelligent_research_assistant.intelligent_assistant import IntelligentResearchAssistant
from intelligent_research_assistant.core.data_models import SearchResult


def test_basic_functionality():
    """测试基本功能"""
    print("\n" + "="*60)
    print("测试1: 基本功能测试")
    print("="*60 + "\n")
    
    assistant = IntelligentResearchAssistant(
        api_provider='qwen',
        test_mode=True
    )
    
    print("✓ 初始化成功")
    
    print("\n[测试项目搜索]")
    projects = assistant.search_projects('machine learning', limit=3)
    assert len(projects) > 0, "项目搜索失败"
    print(f"✓ 找到 {len(projects)} 个项目")
    
    print("\n[测试论文搜索]")
    papers = assistant.search_papers('deep learning', limit=3)
    assert len(papers) > 0, "论文搜索失败"
    print(f"✓ 找到 {len(papers)} 篇论文")
    
    print("\n[测试项目分析]")
    if projects:
        analysis = assistant.analyze_project(projects[0], analysis_depth='shallow')
        assert analysis is not None, "项目分析失败"
        print(f"✓ 项目分析成功: {analysis.summary[:50]}...")
    
    print("\n[测试论文分析]")
    if papers:
        analysis = assistant.analyze_paper(papers[0], analysis_depth='shallow')
        assert analysis is not None, "论文分析失败"
        print(f"✓ 论文分析成功: {analysis.summary[:50]}...")
    
    print("\n[测试文献分析]")
    lit_analysis = assistant.analyze_literature(
        summary='这是一个关于深度学习的文献摘要',
        key_findings=['发现1', '发现2'],
        context='AI研究'
    )
    assert lit_analysis is not None, "文献分析失败"
    print(f"✓ 文献分析成功")
    
    print("\n[测试报告生成]")
    report = assistant.generate_report(
        search_results=projects[:2],
        analysis_results=[lit_analysis],
        title='测试报告'
    )
    assert report is not None, "报告生成失败"
    print(f"✓ 报告生成成功，长度: {len(report.content)} 字符")
    
    print("\n[测试改进建议生成]")
    suggestion = assistant.generate_improvements(
        module_name='test_module',
        context='测试上下文'
    )
    assert suggestion is not None, "改进建议生成失败"
    print(f"✓ 改进建议生成成功，优先级: {suggestion.priority}")
    
    print("\n✅ 基本功能测试通过\n")
    return True


def test_module_optimization():
    """测试模块优化分析"""
    print("\n" + "="*60)
    print("测试2: 模块优化分析测试")
    print("="*60 + "\n")
    
    assistant = IntelligentResearchAssistant(
        api_provider='qwen',
        test_mode=True
    )
    
    result = assistant.analyze_module_optimization(
        module_name='ner_recognizer',
        context='日文史料实体识别',
        search_limit=10,
        analysis_depth='shallow'
    )
    
    assert 'search_results' in result, "缺少搜索结果"
    assert 'analysis_results' in result, "缺少分析结果"
    assert 'report' in result, "缺少报告"
    assert 'improvement_suggestion' in result, "缺少改进建议"
    
    print(f"✓ 搜索项目数: {len(result['search_results']['projects'])}")
    print(f"✓ 搜索论文数: {len(result['search_results']['papers'])}")
    print(f"✓ 报告长度: {len(result['report']['content'])} 字符")
    print(f"✓ 改进建议优先级: {result['improvement_suggestion']['priority']}")
    
    print("\n✅ 模块优化分析测试通过\n")
    return True


def test_data_models():
    """测试数据模型"""
    print("\n" + "="*60)
    print("测试3: 数据模型测试")
    print("="*60 + "\n")
    
    print("[测试SearchResult]")
    search_result = SearchResult(
        id='test-001',
        title='Test Project',
        source='github',
        url='https://github.com/test/project',
        description='Test description',
        score=95.0,
        metadata={'stars': 100}
    )
    
    result_dict = search_result.to_dict()
    restored = SearchResult.from_dict(result_dict)
    assert restored.id == search_result.id, "SearchResult序列化/反序列化失败"
    print("✓ SearchResult序列化/反序列化成功")
    
    print("\n[测试AnalysisResult]")
    from intelligent_research_assistant.core.data_models import AnalysisResult
    
    analysis_result = AnalysisResult(
        source_id='test-001',
        analysis_type='project',
        summary='Test summary',
        key_findings=['Finding 1', 'Finding 2'],
        technical_points=['Point 1', 'Point 2'],
        recommendations=['Rec 1', 'Rec 2'],
        confidence=0.9
    )
    
    result_dict = analysis_result.to_dict()
    restored = AnalysisResult.from_dict(result_dict)
    assert restored.source_id == analysis_result.source_id, "AnalysisResult序列化/反序列化失败"
    print("✓ AnalysisResult序列化/反序列化成功")
    
    print("\n[测试Report]")
    from intelligent_research_assistant.core.data_models import Report
    
    report = Report(
        title='Test Report',
        content='# Test\n\nContent',
        format='markdown',
        sections=[{'title': 'Test', 'content': 'Content'}],
        metadata={'key': 'value'}
    )
    
    result_dict = report.to_dict()
    restored = Report.from_dict(result_dict)
    assert restored.title == report.title, "Report序列化/反序列化失败"
    print("✓ Report序列化/反序列化成功")
    
    print("\n✅ 数据模型测试通过\n")
    return True


def test_cache_functionality():
    """测试缓存功能"""
    print("\n" + "="*60)
    print("测试4: 缓存功能测试")
    print("="*60 + "\n")
    
    assistant = IntelligentResearchAssistant(
        api_provider='qwen',
        test_mode=True,
        cache_enabled=True
    )
    
    print("[第一次调用 - 应该调用LLM]")
    result1 = assistant.analyze_literature(
        summary='测试摘要',
        key_findings=['发现1'],
        context='测试'
    )
    
    print("\n[第二次调用 - 应该使用缓存]")
    result2 = assistant.analyze_literature(
        summary='测试摘要',
        key_findings=['发现1'],
        context='测试'
    )
    
    assert result1.summary == result2.summary, "缓存结果不一致"
    print("✓ 缓存功能正常")
    
    stats = assistant.get_stats()
    print(f"✓ 缓存统计: {stats['cache_stats']}")
    
    print("\n✅ 缓存功能测试通过\n")
    return True


def test_error_handling():
    """测试错误处理"""
    print("\n" + "="*60)
    print("测试5: 错误处理测试")
    print("="*60 + "\n")
    
    assistant = IntelligentResearchAssistant(
        api_provider='qwen',
        test_mode=True
    )
    
    print("[测试空搜索结果处理]")
    try:
        report = assistant.generate_report(
            search_results=[],
            analysis_results=[],
            title='空报告'
        )
        print("✓ 空结果处理正常")
    except Exception as e:
        print(f"✗ 空结果处理失败: {e}")
        return False
    
    print("\n[测试无效参数处理]")
    try:
        assistant.search_projects(query='', limit=0)
        print("✓ 无效参数处理正常")
    except Exception as e:
        print(f"✗ 无效参数处理失败: {e}")
        return False
    
    print("\n✅ 错误处理测试通过\n")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始运行集成测试套件")
    print("="*60)
    
    tests = [
        ("基本功能测试", test_basic_functionality),
        ("模块优化分析测试", test_module_optimization),
        ("数据模型测试", test_data_models),
        ("缓存功能测试", test_cache_functionality),
        ("错误处理测试", test_error_handling)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append({
                'test': test_name,
                'status': 'PASS' if success else 'FAIL'
            })
        except Exception as e:
            print(f"\n❌ 测试失败: {test_name}")
            print(f"   错误: {str(e)}")
            results.append({
                'test': test_name,
                'status': 'FAIL',
                'error': str(e)
            })
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60 + "\n")
    
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    
    for result in results:
        status_icon = "✅" if result['status'] == 'PASS' else "❌"
        print(f"{status_icon} {result['test']}: {result['status']}")
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
