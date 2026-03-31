"""
测试脚本 - 验证统一任务执行框架功能
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from modules.secure_api_key_manager import SecureAPIKeyManager
from modules.task_manager import TaskManager
from modules.unified_task_executor import UnifiedTaskExecutor

def test_key_manager():
    print("=" * 60)
    print("测试安全API密钥管理器")
    print("=" * 60)
    
    manager = SecureAPIKeyManager()
    status = manager.get_status_report()
    
    print(f"Secrets路径: {status['secrets_path']}")
    print(f"已加载密钥数: {status['total_keys_loaded']}")
    
    print("\n服务状态:")
    for service, info in status['services'].items():
        status_text = "可用" if info['has_key'] else "未配置"
        print(f"  {service}: {status_text}")
    
    return True

def test_task_executor():
    print("\n" + "=" * 60)
    print("测试统一任务执行器")
    print("=" * 60)
    
    executor = UnifiedTaskExecutor()
    
    print(f"当前模式: {executor.get_mode()}")
    print(f"支持的任务: {executor.get_supported_tasks()}")
    
    executor.set_mode('script')
    
    print("\n测试NER任务（脚本模式）:")
    result = executor.execute('ner', text="伊藤博文出生于1841年，是明治维新的重要人物。")
    print(f"成功: {result.success}")
    if result.success:
        entities = result.data.get('entities', [])
        print(f"识别到 {len(entities)} 个实体")
        for e in entities[:5]:
            print(f"  - {e['text']} ({e['category']})")
    
    print("\n测试摘要任务（脚本模式）:")
    result = executor.execute('text_summary', text="这是一段很长的文本，用于测试摘要功能。" * 10)
    print(f"成功: {result.success}")
    if result.success:
        summary = result.data.get('summary', '')
        print(f"摘要: {summary[:100]}...")
    
    print("\n执行统计:")
    stats = executor.get_statistics()
    print(f"总执行次数: {stats['total_executions']}")
    print(f"成功率: {stats['success_rate']:.2%}")
    print(f"平均执行时间: {stats['average_time']:.4f}秒")
    
    return True

def test_task_manager():
    print("\n" + "=" * 60)
    print("测试统一任务管理器")
    print("=" * 60)
    
    manager = TaskManager(mode='script')
    
    print(f"当前模式: {manager.mode}")
    print(f"当前提供商: {manager.provider}")
    print(f"可用任务: {manager.get_available_tasks()}")
    
    print("\n测试模式切换:")
    print(f"  当前模式: {manager.mode}")
    manager.set_mode('api')
    print(f"  切换后: {manager.mode}")
    manager.set_mode('script')
    print(f"  切换回来: {manager.mode}")
    
    print("\n测试OCR校正（脚本模式）:")
    result = manager.ocr_correct("这是一个测试日文本。")
    print(f"成功: {result.get('success')}")
    
    print("\n测试论文润色（脚本模式）:")
    result = manager.paper_polish("这个研究非常非常重要，基本上基本上可以说明问题。")
    print(f"成功: {result.get('success')}")
    if result.get('success'):
        polished = result['data'].get('polished_text', '')
        print(f"润色后: {polished[:100]}")
    
    print("\n执行统计:")
    stats = manager.get_statistics()
    print(f"总任务数: {stats['total_tasks']}")
    print(f"成功率: {stats['success_rate']:.2%}")
    
    return True

def test_custom_prompt():
    print("\n" + "=" * 60)
    print("测试自定义提示词执行")
    print("=" * 60)
    
    manager = TaskManager(mode='script')
    
    custom_prompt = """请分析以下文本的情感倾向。

文本: {text}

请直接输出情感分析结果（正面/负面/中性）。"""
    
    result = manager.execute_with_prompt(
        task_type='text_summary',
        prompt=custom_prompt,
        text="这个产品非常好用，我很满意。"
    )
    
    print(f"成功: {result.get('success')}")
    print(f"模式: {result.get('mode')}")
    
    return True

def main():
    print("=" * 60)
    print("历史研究AI辅助工具 - 功能测试")
    print("=" * 60)
    
    tests = [
        ("API密钥管理器", test_key_manager),
        ("任务执行器", test_task_executor),
        ("任务管理器", test_task_manager),
        ("自定义提示词", test_custom_prompt),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            results.append((name, False, str(e)))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, success, error in results:
        status = "通过" if success else "失败"
        print(f"  {name}: {status}")
        if error:
            print(f"    错误: {error}")
    
    total = len(results)
    passed = sum(1 for _, s, _ in results if s)
    print(f"\n总计: {passed}/{total} 通过")

if __name__ == '__main__':
    main()
