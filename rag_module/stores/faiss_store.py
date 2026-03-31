"""
FAISS向量存储

使用FAISS作为向量检索引擎。
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


class FAISSStore(BaseVectorStore):
    """FAISS向量存储"""
    
    def __init__(self,
                 store_path: str = './data/rag_vectors/faiss',
                 embedding_dimension: int = 1024,
                 index_type: str = 'IndexFlatIP',
                 **kwargs):
        super().__init__(store_path, embedding_dimension, **kwargs)
        self.index_type = index_type
        self._index = None
        self._id_to_chunk: Dict[int, Chunk] = {}
        self._next_id = 0
        self._init_index()
    
    def _init_index(self):
        """初始化FAISS索引"""
        try:
            import faiss
            
            if self.index_type == 'IndexFlatIP':
                self._index = faiss.IndexFlatIP(self.embedding_dimension)
            elif self.index_type == 'IndexFlatL2':
                self._index = faiss.IndexFlatL2(self.embedding_dimension)
            elif self.index_type == 'IndexIVFFlat':
                quantizer = faiss.IndexFlatIP(self.embedding_dimension)
                self._index = faiss.IndexIVFFlat(
                    quantizer, 
                    self.embedding_dimension, 
                    100
                )
            else:
                self._index = faiss.IndexFlatIP(self.embedding_dimension)
            
        except ImportError:
            print("警告: faiss未安装，使用numpy实现")
            self._index = None
            self._numpy_vectors = []
            self._numpy_ids = []
    
    def add_vectors(self, 
                   vectors: List[List[float]], 
                   chunks: List[Chunk]) -> Dict[str, Any]:
        """添加向量"""
        if len(vectors) != len(chunks):
            raise ValueError("向量数量与块数量不匹配")
        
        import numpy as np
        
        vectors_np = np.array(vectors).astype('float32')
        
        if self._index is not None:
            import faiss
            
            if self.index_type == 'IndexIVFFlat' and not self._index.is_trained:
                self._index.train(vectors_np)
            
            start_id = self._next_id
            self._index.add(vectors_np)
            
            for i, chunk in enumerate(chunks):
                self._id_to_chunk[start_id + i] = chunk
            
            self._next_id += len(vectors)
            
            return {
                'success': True,
                'added_count': len(vectors),
                'total_count': self._index.ntotal
            }
        else:
            for i, (vector, chunk) in enumerate(zip(vectors, chunks)):
                self._numpy_vectors.append(vector)
                self._numpy_ids.append(self._next_id)
                self._id_to_chunk[self._next_id] = chunk
                self._next_id += 1
            
            return {
                'success': True,
                'added_count': len(vectors),
                'total_count': len(self._numpy_vectors)
            }
    
    def search(self, 
              query_vector: List[float], 
              top_k: int = 5,
              filter_dict: Dict[str, Any] = None) -> List[Tuple[Chunk, float]]:
        """搜索相似向量"""
        import numpy as np
        
        if self._index is not None:
            query_np = np.array([query_vector]).astype('float32')
            
            distances, indices = self._index.search(query_np, top_k)
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx >= 0 and idx in self._id_to_chunk:
                    chunk = self._id_to_chunk[idx]
                    score = float(distances[0][i])
                    
                    if self.index_type == 'IndexFlatL2':
                        score = 1 / (1 + score)
                    
                    results.append((chunk, score))
            
            return results
        else:
            if not self._numpy_vectors:
                return []
            
            similarities = self._compute_cosine_similarity(
                query_vector,
                self._numpy_vectors
            )
            
            indexed = list(enumerate(similarities))
            indexed.sort(key=lambda x: x[1], reverse=True)
            
            results = []
            for idx, score in indexed[:top_k]:
                chunk = self._id_to_chunk.get(self._numpy_ids[idx])
                if chunk:
                    results.append((chunk, score))
            
            return results
    
    def delete(self, chunk_ids: List[str]) -> Dict[str, Any]:
        """删除向量（FAISS不支持直接删除，需要重建索引）"""
        ids_to_remove = []
        for internal_id, chunk in self._id_to_chunk.items():
            if chunk.id in chunk_ids:
                ids_to_remove.append(internal_id)
        
        for internal_id in ids_to_remove:
            del self._id_to_chunk[internal_id]
        
        return {
            'success': True,
            'deleted_count': len(ids_to_remove),
            'remaining_count': len(self._id_to_chunk),
            'note': 'FAISS索引需要重建以完全删除向量'
        }
    
    def get_stats(self) -> IndexStats:
        """获取统计信息"""
        if self._index is not None:
            count = self._index.ntotal
        else:
            count = len(self._numpy_vectors)
        
        return IndexStats(
            total_documents=0,
            total_chunks=len(self._id_to_chunk),
            total_vectors=count,
            vector_dimension=self.embedding_dimension,
            embedding_model='',
            vector_store_type='faiss',
            index_size_mb=0.0,
            last_updated=datetime.now()
        )
    
    def save(self, path: str = None) -> bool:
        """保存索引"""
        save_path = path or self.store_path
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        
        if self._index is not None:
            import faiss
            faiss.write_index(self._index, f"{save_path}.index")
        
        chunk_data = {
            str(k): v.to_dict() for k, v in self._id_to_chunk.items()
        }
        with open(f"{save_path}_chunks.json", 'w', encoding='utf-8') as f:
            json.dump(chunk_data, f, ensure_ascii=False)
        
        meta_data = {
            'next_id': self._next_id,
            'embedding_dimension': self.embedding_dimension,
            'index_type': self.index_type
        }
        with open(f"{save_path}_meta.json", 'w', encoding='utf-8') as f:
            json.dump(meta_data, f)
        
        return True
    
    def load(self, path: str = None) -> bool:
        """加载索引"""
        load_path = path or self.store_path
        
        if self._index is not None:
            import faiss
            index_path = f"{load_path}.index"
            if Path(index_path).exists():
                self._index = faiss.read_index(index_path)
        
        chunks_path = f"{load_path}_chunks.json"
        if Path(chunks_path).exists():
            with open(chunks_path, 'r', encoding='utf-8') as f:
                chunk_data = json.load(f)
            
            self._id_to_chunk = {
                int(k): Chunk.from_dict(v) for k, v in chunk_data.items()
            }
        
        meta_path = f"{load_path}_meta.json"
        if Path(meta_path).exists():
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
            
            self._next_id = meta_data.get('next_id', 0)
        
        return True
    
    def clear(self) -> bool:
        """清空索引"""
        self._init_index()
        self._id_to_chunk = {}
        self._next_id = 0
        
        if hasattr(self, '_numpy_vectors'):
            self._numpy_vectors = []
            self._numpy_ids = []
        
        return True


VectorStoreRegistry.register(VectorStoreType.FAISS, FAISSStore)
