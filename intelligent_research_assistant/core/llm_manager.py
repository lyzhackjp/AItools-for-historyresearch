"""
统一LLM管理器

提供单例模式的LLM调用接口，统一管理所有LLM调用
支持多种LLM提供商，自动重试和错误处理
"""

import os
import sys
import json
import time
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

try:
    from modules.llm_client import LLMClient
    HAS_LLM_CLIENT = True
except ImportError:
    HAS_LLM_CLIENT = False

try:
    from config.local_llm_config import get_local_model
except Exception:  # pragma: no cover
    def get_local_model(role: str = "chat_primary") -> str:
        return "qwen36-27b-academic"


class LLMManager:
    """
    统一LLM管理器 - 单例模式
    
    功能：
    - 单例模式，全局唯一实例
    - 统一API调用接口
    - 自动重试和错误处理
    - 支持多种LLM提供商
    - 调用统计和监控
    """
    
    _instance = None
    _initialized = False
    
    @classmethod
    def get_instance(
        cls,
        api_provider: str = 'qwen',
        model: str = None,
        test_mode: bool = False,
        **kwargs
    ):
        """
        获取单例实例
        
        Args:
            api_provider: API提供商 ('qwen', 'openai', 'minimax', 'zhipu', 'deepseek', 'ollama')
            model: 模型名称（可选）
            test_mode: 测试模式
            **kwargs: 其他参数
            
        Returns:
            LLMManager: 单例实例
        """
        if cls._instance is None:
            cls._instance = cls(api_provider, model, test_mode, **kwargs)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于测试）"""
        cls._instance = None
        cls._initialized = False
    
    def __init__(
        self,
        api_provider: str = 'qwen',
        model: str = None,
        test_mode: bool = False,
        **kwargs
    ):
        """
        初始化LLM管理器
        
        Args:
            api_provider: API提供商
            model: 模型名称
            test_mode: 测试模式
            **kwargs: 其他参数
        """
        if self._initialized:
            return
        
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.kwargs = kwargs
        
        self.provider_mapping = {
            'qwen': 'dashscope',
            'openai': 'openai',
            'minimax': 'minimax',
            'zhipu': 'zhipu',
            'deepseek': 'deepseek',
            'ollama': 'ollama',
            'anthropic': 'anthropic'
        }
        
        self.default_models = {
            'qwen': 'qwen-plus',
            'openai': 'gpt-4',
            'minimax': 'abab6-chat',
            'zhipu': 'glm-4',
            'deepseek': 'deepseek-chat',
            'ollama': get_local_model('chat_primary'),
            'anthropic': 'claude-3-sonnet-20240229'
        }
        
        self.model = model or self.default_models.get(api_provider, 'qwen-plus')
        
        self.client = None
        self.call_count = 0
        self.error_count = 0
        self.total_tokens = 0
        self.call_history = []
        
        if not test_mode and HAS_LLM_CLIENT:
            self._init_client()
        
        self._initialized = True
    
    def _init_client(self):
        """初始化LLM客户端"""
        try:
            provider = self.provider_mapping.get(self.api_provider, 'dashscope')
            
            config = {
                'provider': provider,
                'model': self.model
            }
            
            self.client = LLMClient(config)
            
        except Exception as e:
            print(f"[LLMManager] 初始化客户端失败: {e}")
            self.client = None
    
    def call(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        retry_count: int = 3,
        **kwargs
    ) -> str:
        """
        统一的LLM调用接口
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大token数
            retry_count: 重试次数
            **kwargs: 其他参数
            
        Returns:
            str: LLM响应文本
        """
        if self.test_mode:
            return self._mock_response(prompt)
        
        if not self.client:
            return self._handle_no_client(prompt)
        
        for attempt in range(retry_count):
            try:
                self.call_count += 1
                start_time = time.time()
                
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\n{prompt}"
                
                result = self.client._call_llm(full_prompt)
                
                if isinstance(result, dict):
                    response = result.get('content', '')
                else:
                    response = str(result)
                
                elapsed_time = time.time() - start_time
                
                self._record_call(
                    prompt=prompt[:100],
                    response_length=len(response),
                    elapsed_time=elapsed_time,
                    success=True
                )
                
                return response
                
            except Exception as e:
                self.error_count += 1
                print(f"[LLMManager] 调用失败 (尝试 {attempt + 1}/{retry_count}): {e}")
                
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                else:
                    return self._handle_error(e, prompt)
        
        return ""
    
    def call_json(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        retry_count: int = 3,
        **kwargs
    ) -> dict:
        """
        调用LLM并返回JSON格式结果
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大token数
            retry_count: 重试次数
            **kwargs: 其他参数
            
        Returns:
            dict: JSON格式的响应
        """
        json_prompt = prompt
        if not prompt.strip().lower().endswith('json'):
            json_prompt = f"{prompt}\n\n请以JSON格式返回结果。"
        
        response = self.call(
            prompt=json_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            retry_count=retry_count,
            **kwargs
        )
        
        return self._parse_json_response(response)
    
    def call_with_cache(
        self,
        prompt: str,
        system_prompt: str = None,
        cache_manager=None,
        cache_key: str = None,
        **kwargs
    ) -> str:
        """
        带缓存的LLM调用
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            cache_manager: 缓存管理器
            cache_key: 缓存键
            **kwargs: 其他参数
            
        Returns:
            str: LLM响应文本
        """
        if cache_manager and cache_key:
            cached = cache_manager.get(cache_key)
            if cached:
                return cached
        
        response = self.call(
            prompt=prompt,
            system_prompt=system_prompt,
            **kwargs
        )
        
        if cache_manager and cache_key and response:
            cache_manager.set(cache_key, response)
        
        return response
    
    def batch_call(
        self,
        prompts: List[str],
        system_prompt: str = None,
        delay: float = 1.0,
        **kwargs
    ) -> List[str]:
        """
        批量调用LLM
        
        Args:
            prompts: 提示词列表
            system_prompt: 系统提示词
            delay: 调用间隔（秒）
            **kwargs: 其他参数
            
        Returns:
            List[str]: 响应列表
        """
        results = []
        
        for i, prompt in enumerate(prompts):
            print(f"[LLMManager] 批量调用 {i+1}/{len(prompts)}")
            
            response = self.call(
                prompt=prompt,
                system_prompt=system_prompt,
                **kwargs
            )
            
            results.append(response)
            
            if i < len(prompts) - 1:
                time.sleep(delay)
        
        return results
    
    def get_stats(self) -> dict:
        """
        获取调用统计信息
        
        Returns:
            dict: 统计信息
        """
        return {
            'api_provider': self.api_provider,
            'model': self.model,
            'test_mode': self.test_mode,
            'call_count': self.call_count,
            'error_count': self.error_count,
            'success_rate': (self.call_count - self.error_count) / max(self.call_count, 1),
            'total_tokens': self.total_tokens,
            'call_history_count': len(self.call_history)
        }
    
    def _mock_response(self, prompt: str) -> str:
        """生成模拟响应（测试模式）"""
        if '分析' in prompt or 'analysis' in prompt.lower():
            return json.dumps({
                'summary': '这是一个测试分析结果',
                'key_findings': ['发现1', '发现2', '发现3'],
                'technical_points': ['技术点1', '技术点2'],
                'recommendations': ['建议1', '建议2'],
                'confidence': 0.85
            }, ensure_ascii=False, indent=2)
        
        elif '建议' in prompt or 'suggestion' in prompt.lower():
            return json.dumps({
                'short_term': ['短期建议1', '短期建议2'],
                'medium_term': ['中期建议1', '中期建议2'],
                'long_term': ['长期建议1', '长期建议2'],
                'priority': 'medium',
                'confidence': 0.8
            }, ensure_ascii=False, indent=2)
        
        elif '报告' in prompt or 'report' in prompt.lower():
            return """# 测试报告

## 概述
这是一个测试报告内容。

## 主要发现
1. 发现1
2. 发现2
3. 发现3

## 建议
- 建议1
- 建议2
- 建议3

## 结论
测试完成。
"""
        
        else:
            return f"测试响应: {prompt[:50]}..."
    
    def _handle_no_client(self, prompt: str) -> str:
        """处理无客户端的情况"""
        print("[LLMManager] 警告: LLM客户端未初始化，返回模拟响应")
        return self._mock_response(prompt)
    
    def _handle_error(self, error: Exception, prompt: str) -> str:
        """处理错误"""
        error_msg = f"LLM调用错误: {str(error)}"
        print(f"[LLMManager] {error_msg}")
        
        self._record_call(
            prompt=prompt[:100],
            response_length=0,
            elapsed_time=0,
            success=False,
            error=str(error)
        )
        
        return f"错误: {error_msg}"
    
    def _parse_json_response(self, response: str) -> dict:
        """解析JSON响应"""
        try:
            json_str = response
            
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                json_str = response[start:end].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                json_str = response[start:end].strip()
            
            if not json_str.startswith('{') and not json_str.startswith('['):
                for i, char in enumerate(json_str):
                    if char in '{[':
                        json_str = json_str[i:]
                        break
            
            return json.loads(json_str)
            
        except Exception as e:
            print(f"[LLMManager] JSON解析失败: {e}")
            return {
                'error': 'JSON解析失败',
                'raw_response': response[:500]
            }
    
    def _record_call(
        self,
        prompt: str,
        response_length: int,
        elapsed_time: float,
        success: bool,
        error: str = None
    ):
        """记录调用历史"""
        record = {
            'timestamp': datetime.now().isoformat(),
            'prompt_preview': prompt,
            'response_length': response_length,
            'elapsed_time': elapsed_time,
            'success': success,
            'error': error
        }
        
        self.call_history.append(record)
        
        if len(self.call_history) > 100:
            self.call_history = self.call_history[-50:]
    
    def __repr__(self):
        return f"LLMManager(provider={self.api_provider}, model={self.model}, calls={self.call_count})"


def test_llm_manager():
    """测试LLM管理器"""
    print("\n=== 测试LLM管理器 ===\n")
    
    llm = LLMManager.get_instance(api_provider='qwen', test_mode=True)
    
    print(f"1. 初始化: {llm}")
    
    response = llm.call("分析这个项目的特点")
    print(f"\n2. 文本调用:\n{response[:200]}...")
    
    result = llm.call_json("分析这个项目的技术栈")
    print(f"\n3. JSON调用:\n{json.dumps(result, ensure_ascii=False, indent=2)}")
    
    stats = llm.get_stats()
    print(f"\n4. 统计信息:\n{json.dumps(stats, ensure_ascii=False, indent=2)}")
    
    print("\n✅ 测试完成")


if __name__ == '__main__':
    test_llm_manager()
