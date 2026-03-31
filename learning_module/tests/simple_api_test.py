"""简单的API测试"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.api_key_manager import load_all_api_keys
load_all_api_keys()

print("测试1: 直接导入并测试LLMClient")
try:
    from modules.llm_client import LLMClient
    config = {'provider': 'dashscope'}
    client = LLMClient(config)
    print("✓ LLMClient初始化成功")
    print(f"  Provider: {client.provider}")
    print(f"  Model: {client.model}")
except Exception as e:
    print(f"✗ 失败: {e}")

print("\n测试2: 导入ResearchAnalyzer")
try:
    from learning_module import ResearchAnalyzer
    analyzer = ResearchAnalyzer(api_provider='qwen', test_mode=False)
    print("✓ ResearchAnalyzer初始化成功")
    print(f"  API Provider: {analyzer.api_provider}")
    print(f"  Test Mode: {analyzer.test_mode}")
    print(f"  Client: {analyzer.client is not None}")
except Exception as e:
    print(f"✗ 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n测试3: 调用_call_llm方法")
try:
    response = analyzer._call_llm("你好，请用一句话介绍自己")
    print(f"✓ API调用成功")
    print(f"  响应: {response[:100]}...")
except Exception as e:
    print(f"✗ 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n全部测试完成!")
