"""
内存向量存储

使用纯内存存储向量，适用于测试和小规模数据。
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.stores.base_store import BaseVectorStore, VectorStoreRegistry
from rag_module.core.types import Chunk, IndexStats, VectorStoreType


class MemoryStore(BaseVectorStore):
    """内存向量存储"""
    
    def __init__(self,
                 embedding_dimension: int = 1024,
                 **kwargs):
        super().__init__(None, embedding_dimension, **kwargs)
        self._vectors: List[List[float]] = []
        self._chunks: List[Chunk] = []
        self._ids: List[str] = []
    
    def add_vectors(self, 
                   vectors: List[List[float]], 
                   chunks: List[Chunk]) -> Dict[str, Any]:
        """添加向量"""
        if len(vectors) != len(chunks):
            raise ValueError("向量数量与块数量不匹配")
        
        for vector, chunk in zip(vectors, chunks):
            self._vectors.append(vector)
            self._chunks.append(chunk)
            self._ids.append(chunk.id)
        
        return {
            'success': True,
            'added_count': len(vectors),
            'total_count': len(self._vectors)
        }
    
    def search(self, 
              query_vector: List[float], 
              top_k: int = 5,
              filter_dict: Dict[str, Any] = None) -> List[Tuple[Chunk, float]]:
        """搜索相似向量"""
        if not self._vectors:
            return []
        
        similarities = self._compute_cosine_similarity(query_vector, self._vectors)
        
        indexed = list(enumerate(similarities))
        indexed.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for idx, score in indexed[:top_k]:
            chunk = self._chunks[idx]
            
            if filter_dict:
                match = all(
                    chunk.metadata.get(k) == v 
                    for k, v in filter_dict.items()
                )
                if not match:
                    continue
            
            results.append((chunk, score))
        
        return results[:top_k]
    
    def delete(self, chunk_ids: List[str]) -> Dict[str, Any]:
        """删除向量"""
        indices_to_remove = []
        
        for chunk_id in chunk_ids:
            if chunk_id in self._ids:
                idx = self._ids.index(chunk_id)
                indices_to_remove.append(idx)
        
        for idx in sorted(indices_to_remove, reverse=True):
            self._ids.pop(idx)
            self._vectors.pop(idx)
            self._chunks.pop(idx)
        
        return {
            'success': True,
            'deleted_count': len(indices_to_remove),
            'remaining_count': len(self._vectors)
        }
    
    def get_stats(self) -> IndexStats:
        """获取统计信息"""
        total_size = 0
        if self._vectors:
            import sys
            total_size = sum(sys.getsizeof(v) for v in self._vectors)
            total_size += sum(sys.getsizeof(c.content) for c in self._chunks)
        
        return IndexStats(
            total_documents=0,
            total_chunks=len(self._chunks),
            total_vectors=len(self._vectors),
            vector_dimension=self.embedding_dimension,
            embedding_model='',
            vector_store_type='memory',
            index_size_mb=total_size / (1024 * 1024),
            last_updated=datetime.now()
        )
    
    def save(self, path: str = None) -> bool:
        """保存索引"""
        if not path:
            return False
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        save_data = {
            'ids': self._ids,
            'vectors': self._vectors,
            'chunks': [c.to_dict() for c in self._chunks],
            'embedding_dimension': self.embedding_dimension
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False)
        
        return True
    
    def load(self, path: str = None) -> bool:
        """加载索引"""
        if not path or not Path(path).exists():
            return False
        
        with open(path, 'r', encoding='utf-8') as f:
            save_data = json.load(f)
        
        self._ids = save_data['ids']
        self._vectors = save_data['vectors']
        self._chunks = [Chunk.from_dict(c) for c in save_data['chunks']]
        self.embedding_dimension = save_data.get('embedding_dimension', 1024)
        
        return True
    
    def clear(self) -> bool:
        """清空索引"""
        self._vectors = []
        self._chunks = []
        self._ids = []
        return True
    
    def get_all_chunks(self) -> List[Chunk]:
        """获取所有块"""
        return self._chunks.copy()
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[Chunk]:
        """根据ID获取块"""
        if chunk_id in self._ids:
            idx = self._ids.index(chunk_id)
            return self._chunks[idx]
        return None


VectorStoreRegistry.register(VectorStoreType.MEMORY, MemoryStore)
