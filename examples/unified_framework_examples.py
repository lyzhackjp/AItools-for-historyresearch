"""
统一任务执行框架 - 快速入门示例

本示例展示如何使用统一任务执行框架完成各种任务
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from modules.task_manager import TaskManager


def example_ner():
    """命名实体识别示例"""
    print("=" * 60)
    print("示例1: 命名实体识别")
    print("=" * 60)
    
    manager = TaskManager(mode='script')
    
    text = """
    伊藤博文出生于1841年，是明治维新的重要人物。
    他曾担任日本第一任内阁总理大臣，对日本近代化产生了深远影响。
    """
    
    result = manager.ner(text)
    
    if result.get('success'):
        data = result.get('data', {})
        entities = data.get('entities', []) if data else []
        print(f"\n识别到 {len(entities)} 个实体:")
        for entity in entities:
            print(f"  - {entity['text']} ({entity['category']})")
    else:
        print(f"错误: {result.get('error')}")


def example_summary():
    """文本摘要示例"""
    print("\n" + "=" * 60)
    print("示例2: 文本摘要")
    print("=" * 60)
    
    manager = TaskManager(mode='script')
    
    text = """
    明治维新是日本历史上的一次政治革命，发生于1868年。
    这次革命推翻了德川幕府的统治，建立了以天皇为中心的新政府。
    明治维新推动了日本的现代化进程，使日本从一个封建国家转变为现代工业国家。
    改革包括废除封建制度、建立现代军队、推行义务教育、发展工业等。
    这些改革对日本的后续发展产生了深远影响。
    """
    
    result = manager.summarize(text, max_length=100)
    
    if result.get('success'):
        data = result.get('data', {})
        summary = data.get('summary', '') if data else ''
        original_length = data.get('original_length', 0) if data else 0
        print(f"\n原文长度: {original_length} 字")
        print(f"摘要: {summary}")
    else:
        print(f"错误: {result.get('error')}")


def example_mode_switch():
    """模式切换示例"""
    print("\n" + "=" * 60)
    print("示例3: 模式切换")
    print("=" * 60)
    
    manager = TaskManager(mode='script')
    
    print(f"\n当前模式: {manager.mode}")
    
    text = "西乡隆盛是明治维新的重要人物，出生于萨摩藩。"
    
    print("\n使用脚本模式执行:")
    result1 = manager.ner(text)
    print(f"  成功: {result1['success']}")
    
    print("\n切换到API模式:")
    manager.set_mode('api')
    print(f"  当前模式: {manager.mode}")
    
    print("\n切换回脚本模式:")
    manager.set_mode('script')
    print(f"  当前模式: {manager.mode}")


def example_custom_prompt():
    """自定义提示词示例"""
    print("\n" + "=" * 60)
    print("示例4: 自定义提示词")
    print("=" * 60)
    
    manager = TaskManager(mode='script')
    
    custom_prompt = """请分析以下文本的情感倾向。

文本: {text}

请直接输出情感分析结果（正面/负面/中性）。"""
    
    result = manager.execute_with_prompt(
        task_type='text_summary',
        prompt=custom_prompt,
        text="这个研究非常有价值，对历史学界做出了重要贡献。"
    )
    
    print(f"\n成功: {result['success']}")
    print(f"模式: {result['mode']}")


def example_statistics():
    """执行统计示例"""
    print("\n" + "=" * 60)
    print("示例5: 执行统计")
    print("=" * 60)
    
    manager = TaskManager(mode='script')
    
    manager.ner("伊藤博文是明治维新的重要人物。")
    manager.summarize("这是一段测试文本。")
    manager.ocr_correct("这是一个测试文本。")
    
    stats = manager.get_statistics()
    
    print(f"\n总任务数: {stats['total_tasks']}")
    print(f"成功率: {stats['success_rate']:.2%}")
    print(f"当前模式: {stats['mode']}")
    print(f"当前提供商: {stats['provider']}")


def example_api_key_status():
    """API密钥状态示例"""
    print("\n" + "=" * 60)
    print("示例6: API密钥状态")
    print("=" * 60)
    
    manager = TaskManager()
    
    status = manager.get_api_key_status()
    
    print(f"\nSecrets路径: {status['secrets_path']}")
    print(f"已加载密钥数: {status['total_keys_loaded']}")
    
    print("\n服务状态:")
    for service, info in status['services'].items():
        status_text = "已配置" if info['has_key'] else "未配置"
        print(f"  {service}: {status_text}")


def main():
    """运行所有示例"""
    print("=" * 60)
    print("统一任务执行框架 - 快速入门示例")
    print("=" * 60)
    
    examples = [
        ("命名实体识别", example_ner),
        ("文本摘要", example_summary),
        ("模式切换", example_mode_switch),
        ("自定义提示词", example_custom_prompt),
        ("执行统计", example_statistics),
        ("API密钥状态", example_api_key_status),
    ]
    
    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"\n{name} 示例出错: {e}")
    
    print("\n" + "=" * 60)
    print("示例运行完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
