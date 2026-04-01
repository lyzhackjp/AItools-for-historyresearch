"""
集成测试 - 性能测试

测试IntelligentResearchAssistant的性能表现
"""

import os
import sys
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from intelligent_research_assistant.intelligent_assistant import IntelligentResearchAssistant


def measure_time(func):
    """测量函数执行时间的装饰器"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed = end_time - start_time
        return result, elapsed
    return wrapper


def test_search_performance():
    """测试搜索性能"""
    print("\n" + "="*60)
    print("测试1: 搜索性能测试")
    print("="*60 + "\n")
    
    assistant = IntelligentResearchAssistant(
        api_provider='qwen',
        test_mode=True
    )
    
    print("[测试项目搜索性能]")
    limits = [10, 20, 50]
    
    for limit in limits:
        start = time.time()
        results = assistant.search_projects('machine learning', limit=limit)
        elapsed = time.time() - start
        
        print(f"  搜索 {limit} 个结果: {elapsed:.3f}秒 ({limit/elapsed:.1f} 结果/秒)")
    
    print("\n[测试论文搜索性能]")
    
    for limit in limits:
        start = time.time()
        results = assistant.search_papers('deep learning', limit=limit)
        elapsed = time.time() - start
        
        print(f"  搜索 {limit} 个结果: {elapsed:.3f}秒 ({limit/elapsed:.1f} 结果/秒)")
    
    print("\n✅ 搜索性能测试完成\n")
    return True


def test_analysis_performance():
    """测试分析性能"""
    print("\n" + "="*60)
    print("测试2: 分析性能测试")
    print("="*60 + "\n")
    
    assistant = IntelligentResearchAssistant(
        api_provider='qwen',
        test_mode=True
    )
    
    projects = assistant.search_projects('test', limit=5)
    
    print("[测试单次分析性能]")
    
    if projects:
        start = time.time()
        analysis = assistant.analyze_project(projects[0], analysis_depth='shallow')
        elapsed = time.time() - start
        print(f"  单次分析: {elapsed:.3f}秒")
    
    print("\n[测试批量分析性能]")
    
    start = time.time()
    analyses = []
    for project in projects[:3]:
        analysis = assistant.analyze_project(project, analysis_depth='shallow')
        analyses.append(analysis)
    elapsed = time.time() - start
    
    print(f"  批量分析 3 个项目: {elapsed:.3f}秒 ({elapsed/3:.3f}秒/项目)")
    
    print("\n✅ 分析性能测试完成\n")
    return True


def test_cache_performance():
    """测试缓存性能"""
    print("\n" + "="*60)
    print("测试3: 缓存性能测试")
    print("="*60 + "\n")
    
    assistant = IntelligentResearchAssistant(
        api_provider='qwen',
        test_mode=True,
        cache_enabled=True
    )
    
    print("[第一次调用 - 无缓存]")
    start = time.time()
    result1 = assistant.analyze_literature(
        summary='测试摘要内容' * 10,
        key_findings=['发现1', '发现2', '发现3'],
        context='测试上下文'
    )
    time_without_cache = time.time() - start
    print(f"  耗时: {time_without_cache:.3f}秒")
    
    print("\n[第二次调用 - 使用缓存]")
    start = time.time()
    result2 = assistant.analyze_literature(
        summary='测试摘要内容' * 10,
        key_findings=['发现1', '发现2', '发现3'],
        context='测试上下文'
    )
    time_with_cache = time.time() - start
    print(f"  耗时: {time_with_cache:.3f}秒")
    
    speedup = time_without_cache / time_with_cache if time_with_cache > 0 else 0
    print(f"\n  加速比: {speedup:.1f}x")
    print(f"  时间节省: {(1 - time_with_cache/time_without_cache)*100:.1f}%")
    
    stats = assistant.get_stats()
    print(f"\n  缓存命中率: {stats['cache_stats']['hit_rate']}")
    
    print("\n✅ 缓存性能测试完成\n")
    return True


def test_memory_usage():
    """测试内存使用"""
    print("\n" + "="*60)
    print("测试4: 内存使用测试")
    print("="*60 + "\n")
    
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        initial_memory = process.memory_info().rss / 1024 / 1024
        print(f"初始内存: {initial_memory:.2f} MB")
        
        assistant = IntelligentResearchAssistant(
            api_provider='qwen',
            test_mode=True
        )
        
        after_init_memory = process.memory_info().rss / 1024 / 1024
        print(f"初始化后内存: {after_init_memory:.2f} MB")
        print(f"初始化增加: {after_init_memory - initial_memory:.2f} MB")
        
        projects = assistant.search_projects('test', limit=50)
        papers = assistant.search_papers('test', limit=50)
        
        after_search_memory = process.memory_info().rss / 1024 / 1024
        print(f"\n搜索后内存: {after_search_memory:.2f} MB")
        print(f"搜索增加: {after_search_memory - after_init_memory:.2f} MB")
        
        analyses = []
        for p in projects[:10]:
            analyses.append(assistant.analyze_project(p, analysis_depth='shallow'))
        
        after_analysis_memory = process.memory_info().rss / 1024 / 1024
        print(f"\n分析后内存: {after_analysis_memory:.2f} MB")
        print(f"分析增加: {after_analysis_memory - after_search_memory:.2f} MB")
        
        print(f"\n总内存增加: {after_analysis_memory - initial_memory:.2f} MB")
        
    except ImportError:
        print("⚠️  psutil未安装，跳过内存测试")
        print("   安装方法: pip install psutil")
    
    print("\n✅ 内存使用测试完成\n")
    return True


def test_concurrent_performance():
    """测试并发性能"""
    print("\n" + "="*60)
    print("测试5: 并发性能测试")
    print("="*60 + "\n")
    
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        assistant = IntelligentResearchAssistant(
            api_provider='qwen',
            test_mode=True
        )
        
        queries = ['ml', 'dl', 'nlp', 'cv', 'rl']
        
        print("[串行搜索]")
        start = time.time()
        serial_results = []
        for query in queries:
            results = assistant.search_projects(query, limit=5)
            serial_results.append(results)
        serial_time = time.time() - start
        print(f"  串行耗时: {serial_time:.3f}秒")
        
        print("\n[并发搜索]")
        start = time.time()
        
        def search_task(query):
            return assistant.search_projects(query, limit=5)
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(search_task, q) for q in queries]
            concurrent_results = [f.result() for f in as_completed(futures)]
        
        concurrent_time = time.time() - start
        print(f"  并发耗时: {concurrent_time:.3f}秒")
        
        speedup = serial_time / concurrent_time if concurrent_time > 0 else 0
        print(f"\n  加速比: {speedup:.1f}x")
        
    except ImportError:
        print("⚠️  concurrent.futures不可用，跳过并发测试")
    
    print("\n✅ 并发性能测试完成\n")
    return True


def test_large_scale_performance():
    """测试大规模数据处理性能"""
    print("\n" + "="*60)
    print("测试6: 大规模数据处理性能测试")
    print("="*60 + "\n")
    
    assistant = IntelligentResearchAssistant(
        api_provider='qwen',
        test_mode=True
    )
    
    print("[测试大规模搜索]")
    start = time.time()
    large_results = assistant.search_projects('test', limit=100)
    search_time = time.time() - start
    print(f"  搜索 100 个结果: {search_time:.3f}秒")
    
    print("\n[测试大规模分析]")
    start = time.time()
    analyses = []
    for i, result in enumerate(large_results[:20]):
        analysis = assistant.analyze_project(result, analysis_depth='shallow')
        analyses.append(analysis)
        if (i + 1) % 5 == 0:
            print(f"  已完成 {i+1}/20 个分析...")
    analysis_time = time.time() - start
    print(f"  分析 20 个项目: {analysis_time:.3f}秒 ({analysis_time/20:.3f}秒/项目)")
    
    print("\n[测试报告生成]")
    start = time.time()
    report = assistant.generate_report(
        search_results=large_results[:20],
        analysis_results=analyses,
        title='大规模测试报告'
    )
    report_time = time.time() - start
    print(f"  报告生成: {report_time:.3f}秒")
    
    print(f"\n总耗时: {search_time + analysis_time + report_time:.3f}秒")
    
    print("\n✅ 大规模数据处理性能测试完成\n")
    return True


def run_all_performance_tests():
    """运行所有性能测试"""
    print("\n" + "="*60)
    print("开始运行性能测试套件")
    print("="*60)
    
    tests = [
        ("搜索性能测试", test_search_performance),
        ("分析性能测试", test_analysis_performance),
        ("缓存性能测试", test_cache_performance),
        ("内存使用测试", test_memory_usage),
        ("并发性能测试", test_concurrent_performance),
        ("大规模数据处理测试", test_large_scale_performance)
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
    print("性能测试结果汇总")
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
    success = run_all_performance_tests()
    sys.exit(0 if success else 1)
