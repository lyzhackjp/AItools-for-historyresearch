"""
RAG工厂模块

提供RAG适配器的创建和切换功能。
"""

from typing import Dict, Any, Optional, Type
from enum import Enum

from rag_module.adapters.base_adapter import (
    BaseRAGAdapter, RAGBackend,
    RAGQueryResult, RAGResponse
)


class RAGFactory:
    """RAG适配器工厂类"""
    
    _adapters: Dict[RAGBackend, Type[BaseRAGAdapter]] = {}
    _current_adapter: Optional[BaseRAGAdapter] = None
    _current_backend: Optional[RAGBackend] = None
    
    @classmethod
    def register_adapter(cls, backend: RAGBackend, adapter_class: Type[BaseRAGAdapter]):
        """
        注册适配器类
        
        Args:
            backend: 后端类型
            adapter_class: 适配器类
        """
        cls._adapters[backend] = adapter_class
    
    @classmethod
    def create_adapter(cls, 
                       backend: RAGBackend,
                       config: Optional[Dict[str, Any]] = None) -> BaseRAGAdapter:
        """
        创建RAG适配器
        
        Args:
            backend: 后端类型
            config: 配置字典
            
        Returns:
            BaseRAGAdapter: 适配器实例
            
        Raises:
            ValueError: 不支持的后端类型
        """
        if backend not in cls._adapters:
            cls._auto_register()
        
        if backend not in cls._adapters:
            raise ValueError(f"不支持的RAG后端类型: {backend}")
        
        adapter_class = cls._adapters[backend]
        return adapter_class(config)
    
    @classmethod
    def _auto_register(cls):
        """自动注册内置适配器"""
        try:
            from rag_module.adapters.built_in_adapter import BuiltInRAGAdapter
            cls.register_adapter(RAGBackend.BUILT_IN, BuiltInRAGAdapter)
        except ImportError:
            pass
        
        try:
            from rag_module.adapters.dify_adapter import DifyRAGAdapter
            cls.register_adapter(RAGBackend.DIFY, DifyRAGAdapter)
        except ImportError:
            pass
        
        try:
            from rag_module.adapters.ragflow_adapter import RagflowRAGAdapter
            cls.register_adapter(RAGBackend.RAGFLOW, RagflowRAGAdapter)
        except ImportError:
            pass
    
    @classmethod
    def get_available_backends(cls) -> Dict[RAGBackend, Dict[str, Any]]:
        """
        获取可用的RAG后端列表
        
        Returns:
            Dict[RAGBackend, Dict]: 后端类型到可用性信息的映射
        """
        cls._auto_register()
        
        result = {}
        
        for backend in [RAGBackend.BUILT_IN, RAGBackend.DIFY, RAGBackend.RAGFLOW]:
            info = {
                'available': False,
                'message': '',
                'backend': backend.value
            }
            
            if backend not in cls._adapters:
                info['message'] = '适配器未注册'
            else:
                try:
                    adapter = cls.create_adapter(backend)
                    check_result = adapter.health_check()
                    info['available'] = check_result.get('status') == 'healthy' or backend == RAGBackend.BUILT_IN
                    info['message'] = check_result.get('message', '')
                except Exception as e:
                    info['message'] = str(e)
            
            result[backend] = info
        
        return result
    
    @classmethod
    def switch_backend(cls, 
                       backend: RAGBackend,
                       config: Optional[Dict[str, Any]] = None) -> BaseRAGAdapter:
        """
        切换RAG后端
        
        Args:
            backend: 目标后端类型
            config: 配置字典
            
        Returns:
            BaseRAGAdapter: 新的适配器实例
        """
        adapter = cls.create_adapter(backend, config)
        
        if not adapter.initialize():
            raise RuntimeError(f"初始化{backend.value}后端失败")
        
        cls._current_adapter = adapter
        cls._current_backend = backend
        
        return adapter
    
    @classmethod
    def get_current_adapter(cls) -> Optional[BaseRAGAdapter]:
        """获取当前适配器"""
        return cls._current_adapter
    
    @classmethod
    def get_current_backend(cls) -> Optional[RAGBackend]:
        """获取当前后端类型"""
        return cls._current_backend
    
    @classmethod
    def auto_select_backend(cls, 
                            prefer: Optional[RAGBackend] = None,
                            config: Optional[Dict[str, Any]] = None) -> BaseRAGAdapter:
        """
        自动选择可用的RAG后端
        
        Args:
            prefer: 首选后端
            config: 配置字典
            
        Returns:
            BaseRAGAdapter: 适配器实例
        """
        available = cls.get_available_backends()
        
        if prefer and available.get(prefer, {}).get('available'):
            return cls.switch_backend(prefer, config)
        
        priority = [RAGBackend.BUILT_IN, RAGBackend.RAGFLOW, RAGBackend.DIFY]
        
        for backend in priority:
            if available.get(backend, {}).get('available'):
                try:
                    return cls.switch_backend(backend, config)
                except Exception:
                    continue
        
        return cls.switch_backend(RAGBackend.BUILT_IN, config)


def create_rag_adapter(backend: str = 'built_in',
                       config: Optional[Dict[str, Any]] = None) -> BaseRAGAdapter:
    """
    便捷函数：创建RAG适配器
    
    Args:
        backend: 后端类型字符串 ('built_in', 'dify', 'ragflow')
        config: 配置字典
        
    Returns:
        BaseRAGAdapter: 适配器实例
    """
    backend_map = {
        'built_in': RAGBackend.BUILT_IN,
        'dify': RAGBackend.DIFY,
        'ragflow': RAGBackend.RAGFLOW
    }
    
    rag_backend = backend_map.get(backend.lower(), RAGBackend.BUILT_IN)
    return RAGFactory.create_adapter(rag_backend, config)


def get_rag() -> Optional[BaseRAGAdapter]:
    """便捷函数：获取当前RAG适配器"""
    return RAGFactory.get_current_adapter()


def switch_rag(backend: str, 
               config: Optional[Dict[str, Any]] = None) -> BaseRAGAdapter:
    """
    便捷函数：切换RAG后端
    
    Args:
        backend: 后端类型字符串
        config: 配置字典
        
    Returns:
        BaseRAGAdapter: 新的适配器实例
    """
    backend_map = {
        'built_in': RAGBackend.BUILT_IN,
        'dify': RAGBackend.DIFY,
        'ragflow': RAGBackend.RAGFLOW
    }
    
    rag_backend = backend_map.get(backend.lower(), RAGBackend.BUILT_IN)
    return RAGFactory.switch_backend(rag_backend, config)
