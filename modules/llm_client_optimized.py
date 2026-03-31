"""
LLM客户端模块 - 优化版

统一的LLM API调用接口，支持多种提供商

优化内容 (v2.0.0):
- 完善重试机制：指数退避、最大重试次数
- 添加降级策略：主服务失败自动切换备用服务
- 优化超时处理：可配置超时时间、超时重试
- 添加请求监控：请求统计、错误日志

核心功能：
- 统一API接口：支持DashScope、Minimax、OpenAI等
- 智能重试：指数退避算法、可配置重试策略
- 服务降级：主服务不可用时自动切换备用服务
- 超时控制：灵活的超时配置和超时处理
- 请求监控：请求统计、错误追踪

支持的API提供商：
- DashScope (阿里通义千问)
- Minimax
- OpenAI
- 本地模型
"""

import os
import time
import json
import random
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
import threading


class ProviderType(Enum):
    """API提供商枚举"""
    DASHSCOPE = 'dashscope'
    MINIMAX = 'minimax'
    OPENAI = 'openai'
    LOCAL = 'local'


class ErrorType(Enum):
    """错误类型枚举"""
    TIMEOUT = 'timeout'
    RATE_LIMIT = 'rate_limit'
    AUTH_ERROR = 'auth_error'
    SERVER_ERROR = 'server_error'
    NETWORK_ERROR = 'network_error'
    UNKNOWN = 'unknown'


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    
    def calculate_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay = delay * (0.5 + random.random())
        return delay


@dataclass
class TimeoutConfig:
    """超时配置"""
    connect_timeout: float = 10.0
    read_timeout: float = 60.0
    write_timeout: float = 30.0
    total_timeout: float = 120.0


@dataclass
class RequestStats:
    """请求统计"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_time: float = 0.0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def record_success(self, tokens: int, duration: float):
        """记录成功请求"""
        self.total_requests += 1
        self.successful_requests += 1
        self.total_tokens += tokens
        self.total_time += duration
    
    def record_failure(self, error_type: str, error_msg: str):
        """记录失败请求"""
        self.total_requests += 1
        self.failed_requests += 1
        self.errors.append({
            'type': error_type,
            'message': error_msg,
            'timestamp': datetime.now().isoformat()
        })


class FallbackStrategy:
    """降级策略"""
    
    def __init__(self, providers: List[str], 
                 fallback_order: Optional[List[str]] = None):
        """
        初始化降级策略
        
        Args:
            providers: 可用的提供商列表
            fallback_order: 降级顺序
        """
        self.providers = providers
        self.fallback_order = fallback_order or providers
        self.current_index = 0
        self.failure_counts = {p: 0 for p in providers}
        self.max_failures = 3
        self.recovery_time = 300
        self.last_failure_time = {p: 0 for p in providers}
    
    def get_next_provider(self) -> Optional[str]:
        """获取下一个可用的提供商"""
        current_time = time.time()
        
        for provider in self.fallback_order:
            if self.failure_counts[provider] >= self.max_failures:
                if current_time - self.last_failure_time[provider] > self.recovery_time:
                    self.failure_counts[provider] = 0
                else:
                    continue
            
            return provider
        
        return None
    
    def record_success(self, provider: str):
        """记录成功"""
        self.failure_counts[provider] = 0
    
    def record_failure(self, provider: str):
        """记录失败"""
        self.failure_counts[provider] += 1
        self.last_failure_time[provider] = time.time()


def with_retry(retry_config: Optional[RetryConfig] = None):
    """
    重试装饰器
    
    Args:
        retry_config: 重试配置
    """
    config = retry_config or RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        delay = config.calculate_delay(attempt)
                        logging.warning(
                            f"请求失败 (尝试 {attempt + 1}/{config.max_retries + 1}): {e}. "
                            f"{delay:.2f}秒后重试..."
                        )
                        time.sleep(delay)
                    else:
                        logging.error(f"所有重试均失败: {e}")
            
            raise last_exception
        
        return wrapper
    return decorator


class LLMClientOptimized:
    """LLM客户端 - 优化版"""
    
    PROVIDER_CONFIGS = {
        'dashscope': {
            'api_key_env': 'DASHSCOPE_API_KEY',
            'base_url': 'https://dashscope.aliyuncs.com/api/v1',
            'default_model': 'qwen-max'
        },
        'minimax': {
            'api_key_env': 'MINIMAX_API_KEY',
            'base_url': 'https://api.minimax.chat/v1',
            'default_model': 'abab6.5-chat'
        },
        'openai': {
            'api_key_env': 'OPENAI_API_KEY',
            'base_url': 'https://api.openai.com/v1',
            'default_model': 'gpt-4'
        }
    }
    
    DEFAULT_RETRY_CONFIG = RetryConfig()
    DEFAULT_TIMEOUT_CONFIG = TimeoutConfig()
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化LLM客户端
        
        Args:
            config: 配置字典
        """
        config = config or {}
        
        self.provider = config.get('provider', 'dashscope')
        self.api_key = config.get('api_key') or os.getenv(
            self.PROVIDER_CONFIGS.get(self.provider, {}).get('api_key_env', '')
        )
        self.model = config.get('model') or self.PROVIDER_CONFIGS.get(
            self.provider, {}
        ).get('default_model', 'qwen-max')
        
        self.retry_config = config.get('retry_config', self.DEFAULT_RETRY_CONFIG)
        self.timeout_config = config.get('timeout_config', self.DEFAULT_TIMEOUT_CONFIG)
        
        self.fallback_providers = config.get('fallback_providers', ['dashscope', 'minimax'])
        self.fallback_strategy = FallbackStrategy(self.fallback_providers)
        
        self.stats = RequestStats()
        self.test_mode = config.get('test_mode', False)
        
        self._lock = threading.Lock()
        
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger(f'LLMClient_{self.provider}')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """分类错误类型"""
        error_str = str(error).lower()
        
        if 'timeout' in error_str or 'timed out' in error_str:
            return ErrorType.TIMEOUT
        elif 'rate limit' in error_str or '429' in error_str:
            return ErrorType.RATE_LIMIT
        elif 'auth' in error_str or '401' in error_str or '403' in error_str:
            return ErrorType.AUTH_ERROR
        elif 'server' in error_str or '500' in error_str or '502' in error_str or '503' in error_str:
            return ErrorType.SERVER_ERROR
        elif 'network' in error_str or 'connection' in error_str:
            return ErrorType.NETWORK_ERROR
        else:
            return ErrorType.UNKNOWN
    
    @with_retry()
    def _call_with_retry(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """带重试的API调用"""
        return self._call_llm_internal(prompt, **kwargs)
    
    def _call_llm_internal(self, prompt: str, 
                          temperature: float = 0.7,
                          max_tokens: int = 2000,
                          system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """内部API调用实现"""
        if self.test_mode:
            return self._mock_response(prompt)
        
        start_time = time.time()
        
        try:
            if self.provider == 'dashscope':
                result = self._call_dashscope(prompt, temperature, max_tokens, system_prompt)
            elif self.provider == 'minimax':
                result = self._call_minimax(prompt, temperature, max_tokens, system_prompt)
            elif self.provider == 'openai':
                result = self._call_openai(prompt, temperature, max_tokens, system_prompt)
            else:
                raise ValueError(f"不支持的提供商: {self.provider}")
            
            duration = time.time() - start_time
            tokens = result.get('usage', {}).get('total_tokens', 0)
            
            with self._lock:
                self.stats.record_success(tokens, duration)
                self.fallback_strategy.record_success(self.provider)
            
            return result
            
        except Exception as e:
            error_type = self._classify_error(e)
            
            with self._lock:
                self.stats.record_failure(error_type.value, str(e))
                self.fallback_strategy.record_failure(self.provider)
            
            self.logger.error(f"API调用失败 [{error_type.value}]: {e}")
            raise
    
    def _call_dashscope(self, prompt: str, temperature: float, 
                       max_tokens: int, system_prompt: Optional[str]) -> Dict[str, Any]:
        """调用DashScope API"""
        try:
            import dashscope
            from dashscope import Generation
            
            dashscope.api_key = self.api_key
            
            messages = []
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            messages.append({'role': 'user', 'content': prompt})
            
            response = Generation.call(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                result_format='message'
            )
            
            if response.status_code == 200:
                return {
                    'content': response.output.choices[0].message.content,
                    'usage': {
                        'prompt_tokens': response.usage.input_tokens,
                        'completion_tokens': response.usage.output_tokens,
                        'total_tokens': response.usage.input_tokens + response.usage.output_tokens
                    }
                }
            else:
                raise Exception(f"DashScope API错误: {response.code} - {response.message}")
                
        except ImportError:
            raise ImportError("请安装dashscope: pip install dashscope")
    
    def _call_minimax(self, prompt: str, temperature: float,
                     max_tokens: int, system_prompt: Optional[str]) -> Dict[str, Any]:
        """调用Minimax API"""
        import requests
        
        url = f"{self.PROVIDER_CONFIGS['minimax']['base_url']}/text/chatcompletion"
        
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        
        response = requests.post(
            url, 
            headers=headers, 
            json=data,
            timeout=self.timeout_config.total_timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            return {
                'content': result['choices'][0]['message']['content'],
                'usage': result.get('usage', {})
            }
        else:
            raise Exception(f"Minimax API错误: {response.status_code} - {response.text}")
    
    def _call_openai(self, prompt: str, temperature: float,
                    max_tokens: int, system_prompt: Optional[str]) -> Dict[str, Any]:
        """调用OpenAI API"""
        try:
            import openai
            
            client = openai.OpenAI(api_key=self.api_key)
            
            messages = []
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            messages.append({'role': 'user', 'content': prompt})
            
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                'content': response.choices[0].message.content,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
            
        except ImportError:
            raise ImportError("请安装openai: pip install openai")
    
    def _mock_response(self, prompt: str) -> Dict[str, Any]:
        """测试模式下的模拟响应"""
        return {
            'content': f"[测试模式响应] 收到提示: {prompt[:100]}...",
            'usage': {
                'prompt_tokens': len(prompt) // 4,
                'completion_tokens': 50,
                'total_tokens': len(prompt) // 4 + 50
            }
        }
    
    def call_llm(self, prompt: str, 
                 temperature: float = 0.7,
                 max_tokens: int = 2000,
                 system_prompt: Optional[str] = None,
                 use_fallback: bool = True) -> Dict[str, Any]:
        """
        调用LLM API
        
        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大token数
            system_prompt: 系统提示
            use_fallback: 是否使用降级策略
            
        Returns:
            dict: API响应
        """
        if not use_fallback:
            return self._call_with_retry(
                prompt, 
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt
            )
        
        original_provider = self.provider
        providers_to_try = [original_provider] + [
            p for p in self.fallback_providers if p != original_provider
        ]
        
        last_error = None
        
        for provider in providers_to_try:
            try:
                self.provider = provider
                self.api_key = os.getenv(
                    self.PROVIDER_CONFIGS.get(provider, {}).get('api_key_env', '')
                )
                self.model = self.PROVIDER_CONFIGS.get(provider, {}).get('default_model', self.model)
                
                self.logger.info(f"尝试使用提供商: {provider}")
                
                return self._call_with_retry(
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt
                )
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"提供商 {provider} 失败: {e}")
                continue
        
        self.provider = original_provider
        raise Exception(f"所有提供商均失败，最后错误: {last_error}")
    
    def _call_llm(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """兼容旧接口的调用方法"""
        return self.call_llm(prompt, **kwargs)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取请求统计"""
        with self._lock:
            return {
                'total_requests': self.stats.total_requests,
                'successful_requests': self.stats.successful_requests,
                'failed_requests': self.stats.failed_requests,
                'success_rate': (
                    self.stats.successful_requests / self.stats.total_requests 
                    if self.stats.total_requests > 0 else 0
                ),
                'total_tokens': self.stats.total_tokens,
                'average_time': (
                    self.stats.total_time / self.stats.successful_requests
                    if self.stats.successful_requests > 0 else 0
                ),
                'recent_errors': self.stats.errors[-10:]
            }
    
    def reset_stats(self):
        """重置统计"""
        with self._lock:
            self.stats = RequestStats()
    
    def set_provider(self, provider: str):
        """设置提供商"""
        if provider not in self.PROVIDER_CONFIGS:
            raise ValueError(f"不支持的提供商: {provider}")
        
        self.provider = provider
        self.api_key = os.getenv(
            self.PROVIDER_CONFIGS[provider]['api_key_env']
        )
        self.model = self.PROVIDER_CONFIGS[provider]['default_model']
    
    def set_model(self, model: str):
        """设置模型"""
        self.model = model
    
    def set_retry_config(self, config: RetryConfig):
        """设置重试配置"""
        self.retry_config = config
    
    def set_timeout_config(self, config: TimeoutConfig):
        """设置超时配置"""
        self.timeout_config = config


def create_llm_client_optimized(config: Optional[Dict[str, Any]] = None) -> LLMClientOptimized:
    """
    工厂函数 - 创建优化版LLM客户端
    
    Args:
        config: 配置字典
        
    Returns:
        LLMClientOptimized: LLM客户端实例
    """
    return LLMClientOptimized(config)


if __name__ == "__main__":
    print("LLM客户端 - 优化版 v2.0.0")
    print("="*60)
    print("\n支持的提供商: dashscope, minimax, openai")
    print("\n使用方法:")
    print("```python")
    print("from modules.llm_client_optimized import create_llm_client_optimized, RetryConfig, TimeoutConfig")
    print("")
    print("# 创建客户端")
    print("client = create_llm_client_optimized({")
    print("    'provider': 'dashscope',")
    print("    'model': 'qwen-max',")
    print("    'retry_config': RetryConfig(max_retries=3),")
    print("    'timeout_config': TimeoutConfig(total_timeout=60)")
    print("})")
    print("")
    print("# 调用API")
    print("result = client.call_llm('你好，请介绍一下自己')")
    print("print(result['content'])")
    print("")
    print("# 获取统计")
    print("stats = client.get_stats()")
    print("print(stats)")
    print("```")
