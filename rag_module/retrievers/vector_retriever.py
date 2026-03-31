"""
向量检索器

基于向量相似度的检索实现。
"""

from typing import List, Dict, Any, Optional
import time

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.retrievers.base_retriever import BaseRetriever, RetrieverRegistry
from rag_module.core.types import Chunk, RetrievalResult, RetrievalStrategy


class VectorRetriever(BaseRetriever):
    """向量检索器"""
    
    def __init__(self,
                 vector_store=None,
                 embedder=None,
                 top_k: int = 5,
                 threshold: float = 0.0,
                 **kwargs):
        super().__init__(top_k, threshold, **kwargs)
        self.vector_store = vector_store
        self.embedder = embedder
    
    def retrieve(self, query: str, top_k: int = None) -> RetrievalResult:
        """
        检索相关内容
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            RetrievalResult: 检索结果
        """
        start_time = time.time()
        
        k = top_k or self.top_k
        
        query_vector = self.get_embedding(query)
        
        if self.vector_store is None:
            return RetrievalResult(
                chunks=[],
                scores=[],
                query=query,
                retrieval_strategy=RetrievalStrategy.VECTOR,
                total_candidates=0
            )
        
        results = self.vector_store.search(query_vector, top_k=k)
        
        chunks = []
        scores = []
        
        for chunk, score in results:
            if score >= self.threshold:
                chunks.append(chunk)
                scores.append(score)
        
        retrieval_time = time.time() - start_time
        
        result = RetrievalResult(
            chunks=chunks,
            scores=scores,
            query=query,
            retrieval_strategy=RetrievalStrategy.VECTOR,
            total_candidates=len(results)
        )
        
        return result
    
    def get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入向量"""
        if self.embedder is not None:
            if hasattr(self.embedder, '_get_embedding'):
                return self.embedder._get_embedding(text).tolist()
            elif hasattr(self.embedder, 'encode'):
                return self.embedder.encode(text).tolist()
            elif hasattr(self.embedder, 'get_embedding'):
                return self.embedder.get_embedding(text)
        
        return self._mock_embedding(text)
    
    def _mock_embedding(self, text: str) -> List[float]:
        """生成模拟嵌入向量"""
        import hashlib
        import numpy as np
        
        text_hash = hashlib.md5(text.encode('utf-8')).digest()
        seed = int.from_bytes(text_hash[:4], 'big')
        
        np.random.seed(seed)
        vector = np.random.randn(384)
        vector = vector / np.linalg.norm(vector)
        
        return vector.tolist()
    
    def retrieve_with_filter(self, 
                            query: str, 
                            filter_dict: Dict[str, Any],
                            top_k: int = None) -> RetrievalResult:
        """
        带过滤条件的检索
        
        Args:
            query: 查询文本
            filter_dict: 过滤条件
            top_k: 返回数量
            
        Returns:
            RetrievalResult: 检索结果
        """
        k = top_k or self.top_k
        
        query_vector = self.get_embedding(query)
        
        if self.vector_store is None:
            return RetrievalResult(
                chunks=[],
                scores=[],
                query=query,
                retrieval_strategy=RetrievalStrategy.VECTOR,
                total_candidates=0
            )
        
        results = self.vector_store.search(query_vector, top_k=k, filter_dict=filter_dict)
        
        chunks = []
        scores = []
        
        for chunk, score in results:
            if score >= self.threshold:
                chunks.append(chunk)
                scores.append(score)
        
        return RetrievalResult(
            chunks=chunks,
            scores=scores,
            query=query,
            retrieval_strategy=RetrievalStrategy.VECTOR,
            total_candidates=len(results)
        )
    
    def batch_retrieve(self, queries: List[str], top_k: int = None) -> List[RetrievalResult]:
        """
        批量检索
        
        Args:
            queries: 查询列表
            top_k: 返回数量
            
        Returns:
            List[RetrievalResult]: 检索结果列表
        """
        results = []
        
        for query in queries:
            result = self.retrieve(query, top_k)
            results.append(result)
        
        return results


RetrieverRegistry.register(RetrievalStrategy.VECTOR, VectorRetriever)
