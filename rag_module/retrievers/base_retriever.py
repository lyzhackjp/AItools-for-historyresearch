"""
检索器基类

定义检索器的统一接口和基础功能。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.core.types import Chunk, RetrievalResult, RetrievalStrategy


class BaseRetriever(ABC):
    """检索器基类"""
    
    def __init__(self, 
                 top_k: int = 5,
                 threshold: float = 0.0,
                 **kwargs):
        self.top_k = top_k
        self.threshold = threshold
    
    @abstractmethod
    def retrieve(self, query: str, top_k: int = None) -> RetrievalResult:
        """
        检索相关内容
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            RetrievalResult: 检索结果
        """
        pass
    
    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """
        获取文本嵌入向量
        
        Args:
            text: 文本
            
        Returns:
            List[float]: 嵌入向量
        """
        pass


class RetrieverRegistry:
    """检索器注册表"""
    
    _retrievers: Dict[RetrievalStrategy, type] = {}
    
    @classmethod
    def register(cls, strategy: RetrievalStrategy, retriever_class: type):
        """注册检索器"""
        cls._retrievers[strategy] = retriever_class
    
    @classmethod
    def get_retriever(cls, strategy: RetrievalStrategy, **kwargs) -> Optional[BaseRetriever]:
        """获取检索器实例"""
        retriever_class = cls._retrievers.get(strategy)
        if retriever_class:
            return retriever_class(**kwargs)
        return None
    
    @classmethod
    def get_supported_strategies(cls) -> List[RetrievalStrategy]:
        """获取支持的策略"""
        return list(cls._retrievers.keys())


class RetrieverManager:
    """检索器管理器"""
    
    def __init__(self,
                 strategy: RetrievalStrategy = RetrievalStrategy.VECTOR,
                 vector_store=None,
                 embedder=None,
                 top_k: int = 5,
                 threshold: float = 0.0,
                 **kwargs):
        self.strategy = strategy
        self.vector_store = vector_store
        self.embedder = embedder
        self.top_k = top_k
        self.threshold = threshold
        self.kwargs = kwargs
        self._retriever = None
        self._init_retriever()
    
    def _init_retriever(self):
        """初始化检索器"""
        from rag_module.retrievers.vector_retriever import VectorRetriever
        from rag_module.retrievers.hybrid_retriever import HybridRetriever
        
        RetrieverRegistry.register(RetrievalStrategy.VECTOR, VectorRetriever)
        RetrieverRegistry.register(RetrievalStrategy.HYBRID, HybridRetriever)
        
        self._retriever = RetrieverRegistry.get_retriever(
            self.strategy,
            vector_store=self.vector_store,
            embedder=self.embedder,
            top_k=self.top_k,
            threshold=self.threshold,
            **self.kwargs
        )
    
    def retrieve(self, query: str, top_k: int = None) -> RetrievalResult:
        """
        检索相关内容
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            RetrievalResult: 检索结果
        """
        if self._retriever is None:
            raise ValueError("检索器未初始化")
        
        return self._retriever.retrieve(query, top_k)
    
    def set_top_k(self, top_k: int):
        """设置返回数量"""
        self.top_k = top_k
        if self._retriever:
            self._retriever.top_k = top_k
    
    def set_threshold(self, threshold: float):
        """设置相似度阈值"""
        self.threshold = threshold
        if self._retriever:
            self._retriever.threshold = threshold
