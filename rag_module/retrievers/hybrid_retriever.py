"""
混合检索器

结合向量检索和关键词检索的混合检索实现。
"""

from typing import List, Dict, Any, Optional
import time
import re
from collections import Counter

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.retrievers.base_retriever import BaseRetriever, RetrieverRegistry
from rag_module.core.types import Chunk, RetrievalResult, RetrievalStrategy


class HybridRetriever(BaseRetriever):
    """混合检索器"""
    
    def __init__(self,
                 vector_store=None,
                 embedder=None,
                 top_k: int = 5,
                 threshold: float = 0.0,
                 alpha: float = 0.5,
                 **kwargs):
        super().__init__(top_k, threshold, **kwargs)
        self.vector_store = vector_store
        self.embedder = embedder
        self.alpha = alpha
    
    def retrieve(self, query: str, top_k: int = None) -> RetrievalResult:
        """
        混合检索
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            RetrievalResult: 检索结果
        """
        start_time = time.time()
        
        k = top_k or self.top_k
        
        vector_results = self._vector_search(query, k * 2)
        
        keyword_results = self._keyword_search(query, k * 2)
        
        merged_results = self._merge_results(vector_results, keyword_results, k)
        
        chunks = []
        scores = []
        
        for chunk, score in merged_results:
            if score >= self.threshold:
                chunks.append(chunk)
                scores.append(score)
        
        retrieval_time = time.time() - start_time
        
        result = RetrievalResult(
            chunks=chunks,
            scores=scores,
            query=query,
            retrieval_strategy=RetrievalStrategy.HYBRID,
            total_candidates=len(vector_results) + len(keyword_results)
        )
        
        return result
    
    def get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入向量"""
        if self.embedder is not None:
            if hasattr(self.embedder, '_get_embedding'):
                return self.embedder._get_embedding(text).tolist()
            elif hasattr(self.embedder, 'encode'):
                return self.embedder.encode(text).tolist()
        
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
    
    def _vector_search(self, query: str, top_k: int) -> List[tuple]:
        """向量检索"""
        if self.vector_store is None:
            return []
        
        query_vector = self.get_embedding(query)
        
        results = self.vector_store.search(query_vector, top_k=top_k)
        
        return results
    
    def _keyword_search(self, query: str, top_k: int) -> List[tuple]:
        """关键词检索（BM25简化实现）"""
        if self.vector_store is None:
            return []
        
        query_terms = self._tokenize(query)
        
        all_chunks = self._get_all_chunks()
        
        if not all_chunks:
            return []
        
        scores = []
        
        for chunk in all_chunks:
            score = self._compute_bm25_score(query_terms, chunk.content)
            scores.append((chunk, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:top_k]
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        text = text.lower()
        
        tokens = re.findall(r'[\u4e00-\u9fff]+|[a-z]+|[0-9]+', text)
        
        return tokens
    
    def _compute_bm25_score(self, query_terms: List[str], document: str) -> float:
        """计算BM25分数"""
        doc_terms = self._tokenize(document)
        doc_len = len(doc_terms)
        
        avg_doc_len = 100
        
        k1 = 1.5
        b = 0.75
        
        term_freqs = Counter(doc_terms)
        
        score = 0.0
        
        for term in query_terms:
            if term in term_freqs:
                tf = term_freqs[term]
                
                idf = 1.0
                
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * doc_len / avg_doc_len)
                
                score += idf * numerator / denominator
        
        return score
    
    def _get_all_chunks(self) -> List[Chunk]:
        """获取所有块"""
        if hasattr(self.vector_store, 'store') and hasattr(self.vector_store.store, 'get_all_chunks'):
            return self.vector_store.store.get_all_chunks()
        
        if hasattr(self.vector_store, '_memory_store'):
            return self.vector_store._memory_store.get('chunks', [])
        
        return []
    
    def _merge_results(self, 
                      vector_results: List[tuple], 
                      keyword_results: List[tuple],
                      top_k: int) -> List[tuple]:
        """合并检索结果"""
        chunk_scores: Dict[str, tuple] = {}
        
        max_vector_score = max((s for _, s in vector_results), default=1.0)
        max_keyword_score = max((s for _, s in keyword_results), default=1.0)
        
        for chunk, score in vector_results:
            normalized_score = score / max_vector_score if max_vector_score > 0 else 0
            chunk_scores[chunk.id] = (chunk, normalized_score * self.alpha, 0.0)
        
        for chunk, score in keyword_results:
            normalized_score = score / max_keyword_score if max_keyword_score > 0 else 0
            
            if chunk.id in chunk_scores:
                existing_chunk, vec_score, _ = chunk_scores[chunk.id]
                chunk_scores[chunk.id] = (existing_chunk, vec_score, normalized_score * (1 - self.alpha))
            else:
                chunk_scores[chunk.id] = (chunk, 0.0, normalized_score * (1 - self.alpha))
        
        merged = []
        for chunk_id, (chunk, vec_score, kw_score) in chunk_scores.items():
            total_score = vec_score + kw_score
            merged.append((chunk, total_score))
        
        merged.sort(key=lambda x: x[1], reverse=True)
        
        return merged[:top_k]
    
    def set_alpha(self, alpha: float):
        """设置向量检索权重"""
        self.alpha = max(0.0, min(1.0, alpha))


RetrieverRegistry.register(RetrievalStrategy.HYBRID, HybridRetriever)
