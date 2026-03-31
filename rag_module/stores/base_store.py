"""
向量存储基类

定义向量存储的统一接口和基础功能。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.core.types import Chunk, IndexStats, VectorStoreType


class BaseVectorStore(ABC):
    """向量存储基类"""
    
    def __init__(self, 
                 store_path: str = None,
                 embedding_dimension: int = 1024,
                 **kwargs):
        self.store_path = store_path
        self.embedding_dimension = embedding_dimension
        self.metadata = {}
    
    @abstractmethod
    def add_vectors(self, 
                   vectors: List[List[float]], 
                   chunks: List[Chunk]) -> Dict[str, Any]:
        """
        添加向量和对应的块
        
        Args:
            vectors: 向量列表
            chunks: 对应的块列表
            
        Returns:
            dict: 添加结果
        """
        pass
    
    @abstractmethod
    def search(self, 
              query_vector: List[float], 
              top_k: int = 5,
              filter_dict: Dict[str, Any] = None) -> List[Tuple[Chunk, float]]:
        """
        搜索相似向量
        
        Args:
            query_vector: 查询向量
            top_k: 返回数量
            filter_dict: 元数据过滤条件
            
        Returns:
            List[Tuple[Chunk, float]]: (块, 相似度分数) 列表
        """
        pass
    
    @abstractmethod
    def delete(self, chunk_ids: List[str]) -> Dict[str, Any]:
        """
        删除向量
        
        Args:
            chunk_ids: 要删除的块ID列表
            
        Returns:
            dict: 删除结果
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> IndexStats:
        """
        获取索引统计信息
        
        Returns:
            IndexStats: 统计信息
        """
        pass
    
    @abstractmethod
    def save(self, path: str = None) -> bool:
        """
        保存索引
        
        Args:
            path: 保存路径
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def load(self, path: str = None) -> bool:
        """
        加载索引
        
        Args:
            path: 加载路径
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """清空索引"""
        pass
    
    def _compute_cosine_similarity(self, 
                                   query_vector: List[float], 
                                   vectors: List[List[float]]) -> List[float]:
        """计算余弦相似度"""
        import numpy as np
        
        query = np.array(query_vector)
        docs = np.array(vectors)
        
        query_norm = query / np.linalg.norm(query)
        doc_norms = np.linalg.norm(docs, axis=1, keepdims=True)
        doc_norms = np.where(doc_norms == 0, 1, doc_norms)
        docs_normalized = docs / doc_norms
        
        similarities = np.dot(docs_normalized, query_norm)
        
        return similarities.tolist()


class VectorStoreRegistry:
    """向量存储注册表"""
    
    _stores: Dict[VectorStoreType, type] = {}
    
    @classmethod
    def register(cls, store_type: VectorStoreType, store_class: type):
        """注册存储"""
        cls._stores[store_type] = store_class
    
    @classmethod
    def get_store(cls, store_type: VectorStoreType, **kwargs) -> Optional[BaseVectorStore]:
        """获取存储实例"""
        store_class = cls._stores.get(store_type)
        if store_class:
            return store_class(**kwargs)
        return None
    
    @classmethod
    def get_supported_types(cls) -> List[VectorStoreType]:
        """获取支持的类型"""
        return list(cls._stores.keys())


class VectorStoreManager:
    """向量存储管理器"""
    
    def __init__(self, 
                 store_type: VectorStoreType = VectorStoreType.CHROMA,
                 store_path: str = './data/rag_vectors',
                 embedding_dimension: int = 1024,
                 **kwargs):
        self.store_type = store_type
        self.store_path = store_path
        self.embedding_dimension = embedding_dimension
        self.kwargs = kwargs
        self._store = None
        self._init_store()
    
    def _init_store(self):
        """初始化存储"""
        from rag_module.stores.chroma_store import ChromaStore
        from rag_module.stores.faiss_store import FAISSStore
        from rag_module.stores.memory_store import MemoryStore
        
        VectorStoreRegistry.register(VectorStoreType.CHROMA, ChromaStore)
        VectorStoreRegistry.register(VectorStoreType.FAISS, FAISSStore)
        VectorStoreRegistry.register(VectorStoreType.MEMORY, MemoryStore)
        
        self._store = VectorStoreRegistry.get_store(
            self.store_type,
            store_path=self.store_path,
            embedding_dimension=self.embedding_dimension,
            **self.kwargs
        )
    
    def add_vectors(self, 
                   vectors: List[List[float]], 
                   chunks: List[Chunk]) -> Dict[str, Any]:
        """添加向量"""
        if self._store is None:
            raise ValueError("向量存储未初始化")
        return self._store.add_vectors(vectors, chunks)
    
    def search(self, 
              query_vector: List[float], 
              top_k: int = 5,
              filter_dict: Dict[str, Any] = None) -> List[Tuple[Chunk, float]]:
        """搜索相似向量"""
        if self._store is None:
            raise ValueError("向量存储未初始化")
        return self._store.search(query_vector, top_k, filter_dict)
    
    def delete(self, chunk_ids: List[str]) -> Dict[str, Any]:
        """删除向量"""
        if self._store is None:
            raise ValueError("向量存储未初始化")
        return self._store.delete(chunk_ids)
    
    def get_stats(self) -> IndexStats:
        """获取统计信息"""
        if self._store is None:
            raise ValueError("向量存储未初始化")
        return self._store.get_stats()
    
    def save(self, path: str = None) -> bool:
        """保存索引"""
        if self._store is None:
            return False
        return self._store.save(path)
    
    def load(self, path: str = None) -> bool:
        """加载索引"""
        if self._store is None:
            return False
        return self._store.load(path)
    
    def clear(self) -> bool:
        """清空索引"""
        if self._store is None:
            return False
        return self._store.clear()
    
    @property
    def store(self) -> BaseVectorStore:
        """获取底层存储"""
        return self._store
