"""
自研RAG适配器

封装项目自带的RAG引擎，提供统一接口。
"""

from typing import List, Dict, Any, Optional
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from rag_module.adapters.base_adapter import (
    BaseRAGAdapter, RAGBackend, RAGDocument, 
    RAGQueryResult, RAGResponse, RAGIndexStats
)


class BuiltInRAGAdapter(BaseRAGAdapter):
    """自研RAG适配器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._engine = None
        self._rag_config = None
    
    @property
    def backend_type(self) -> RAGBackend:
        return RAGBackend.BUILT_IN
    
    def initialize(self) -> bool:
        """初始化自研RAG引擎"""
        try:
            from rag_module.core import RAGEngine, RAGConfig
            
            self._rag_config = RAGConfig(
                chunk_size=self.config.get('chunk_size', 500),
                chunk_overlap=self.config.get('chunk_overlap', 50),
                vector_store=self.config.get('vector_store', 'chroma'),
                vector_store_path=self.config.get('vector_store_path', './data/rag_index'),
                embedding_model=self.config.get('embedding_model', 'bge-m3'),
                llm_provider=self.config.get('llm_provider', 'qwen'),
                retrieval_top_k=self.config.get('retrieval_top_k', 5),
                retrieval_threshold=self.config.get('retrieval_threshold', 0.0)
            )
            
            self._engine = RAGEngine(self._rag_config)
            self._is_initialized = True
            return True
        except Exception as e:
            print(f"初始化自研RAG引擎失败: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """检查引擎健康状态"""
        if not self._is_initialized:
            return {'status': 'error', 'message': '引擎未初始化'}
        
        try:
            stats = self.get_stats()
            return {
                'status': 'healthy',
                'message': '自研RAG引擎运行正常',
                'stats': {
                    'documents': stats.total_documents,
                    'chunks': stats.total_chunks
                }
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def load_document(self, 
                      file_path: str, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """加载文档"""
        if not self._is_initialized:
            raise RuntimeError("引擎未初始化")
        
        try:
            self._engine.load_document(file_path)
            return True
        except Exception as e:
            print(f"加载文档失败: {e}")
            return False
    
    def load_documents(self,
                       file_paths: List[str],
                       metadata_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, bool]:
        """批量加载文档"""
        results = {}
        for i, file_path in enumerate(file_paths):
            metadata = metadata_list[i] if metadata_list and i < len(metadata_list) else None
            results[file_path] = self.load_document(file_path, metadata)
        return results
    
    def retrieve(self,
                 query: str,
                 top_k: int = 5,
                 threshold: float = 0.0,
                 filters: Optional[Dict[str, Any]] = None) -> List[RAGQueryResult]:
        """检索相关文档"""
        if not self._is_initialized:
            raise RuntimeError("引擎未初始化")
        
        try:
            results = self._engine.retrieve(query, top_k=top_k)
            return [
                RAGQueryResult(
                    content=r.content,
                    score=r.score,
                    metadata=r.metadata,
                    source=r.source
                )
                for r in results
                if r.score >= threshold
            ]
        except Exception as e:
            print(f"检索失败: {e}")
            return []
    
    def query(self,
              question: str,
              top_k: int = 5,
              include_sources: bool = True) -> RAGResponse:
        """执行RAG查询"""
        if not self._is_initialized:
            raise RuntimeError("引擎未初始化")
        
        try:
            answer = self._engine.query(question)
            
            sources = []
            if include_sources:
                sources = self.retrieve(question, top_k=top_k)
            
            return RAGResponse(
                answer=answer,
                sources=sources,
                metadata={'backend': 'built_in'}
            )
        except Exception as e:
            return RAGResponse(
                answer=f"查询失败: {str(e)}",
                sources=[],
                metadata={'error': str(e)}
            )
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        if not self._is_initialized:
            raise RuntimeError("引擎未初始化")
        
        try:
            self._engine.delete_document(doc_id)
            return True
        except Exception as e:
            print(f"删除文档失败: {e}")
            return False
    
    def clear_index(self) -> bool:
        """清空索引"""
        if not self._is_initialized:
            raise RuntimeError("引擎未初始化")
        
        try:
            self._engine.clear()
            return True
        except Exception as e:
            print(f"清空索引失败: {e}")
            return False
    
    def get_stats(self) -> RAGIndexStats:
        """获取统计信息"""
        if not self._is_initialized:
            return RAGIndexStats(backend_type='built_in')
        
        try:
            stats = self._engine.get_stats()
            return RAGIndexStats(
                total_documents=stats.total_documents,
                total_chunks=stats.total_chunks,
                index_size_mb=stats.index_size_mb,
                backend_type='built_in'
            )
        except Exception:
            return RAGIndexStats(backend_type='built_in')
