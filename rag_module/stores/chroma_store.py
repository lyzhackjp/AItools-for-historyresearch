"""
ChromaDB向量存储

使用ChromaDB作为向量数据库后端。
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.stores.base_store import BaseVectorStore, VectorStoreRegistry
from rag_module.core.types import Chunk, IndexStats, VectorStoreType


class ChromaStore(BaseVectorStore):
    """ChromaDB向量存储"""
    
    def __init__(self,
                 store_path: str = './data/rag_vectors/chroma',
                 embedding_dimension: int = 1024,
                 collection_name: str = 'rag_collection',
                 **kwargs):
        super().__init__(store_path, embedding_dimension, **kwargs)
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._init_client()
    
    def _init_client(self):
        """初始化ChromaDB客户端"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            Path(self.store_path).parent.mkdir(parents=True, exist_ok=True)
            
            self._client = chromadb.PersistentClient(
                path=self.store_path,
                settings=Settings(anonymized_telemetry=False)
            )
            
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={'hnsw:space': 'cosine'}
            )
            
        except ImportError:
            print("警告: chromadb未安装，使用内存存储模式")
            self._client = None
            self._collection = None
            self._memory_store = {
                'vectors': [],
                'chunks': [],
                'ids': []
            }
    
    def add_vectors(self, 
                   vectors: List[List[float]], 
                   chunks: List[Chunk]) -> Dict[str, Any]:
        """添加向量"""
        if len(vectors) != len(chunks):
            raise ValueError("向量数量与块数量不匹配")
        
        if self._collection is not None:
            ids = [chunk.id for chunk in chunks]
            metadatas = [chunk.metadata for chunk in chunks]
            documents = [chunk.content for chunk in chunks]
            
            self._collection.add(
                ids=ids,
                embeddings=vectors,
                metadatas=metadatas,
                documents=documents
            )
            
            return {
                'success': True,
                'added_count': len(vectors),
                'total_count': self._collection.count()
            }
        else:
            for i, (vector, chunk) in enumerate(zip(vectors, chunks)):
                self._memory_store['vectors'].append(vector)
                self._memory_store['chunks'].append(chunk)
                self._memory_store['ids'].append(chunk.id)
            
            return {
                'success': True,
                'added_count': len(vectors),
                'total_count': len(self._memory_store['ids'])
            }
    
    def search(self, 
              query_vector: List[float], 
              top_k: int = 5,
              filter_dict: Dict[str, Any] = None) -> List[Tuple[Chunk, float]]:
        """搜索相似向量"""
        if self._collection is not None:
            where = None
            if filter_dict:
                where = {k: v for k, v in filter_dict.items()}
            
            results = self._collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=where,
                include=['documents', 'metadatas', 'distances']
            )
            
            chunks_with_scores = []
            
            if results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    chunk = Chunk(
                        id=doc_id,
                        document_id=results['metadatas'][0][i].get('document_id', ''),
                        content=results['documents'][0][i],
                        metadata=results['metadatas'][0][i]
                    )
                    distance = results['distances'][0][i]
                    similarity = 1 - distance
                    chunks_with_scores.append((chunk, similarity))
            
            return chunks_with_scores
        else:
            if not self._memory_store['vectors']:
                return []
            
            similarities = self._compute_cosine_similarity(
                query_vector, 
                self._memory_store['vectors']
            )
            
            indexed = list(enumerate(similarities))
            indexed.sort(key=lambda x: x[1], reverse=True)
            
            results = []
            for idx, score in indexed[:top_k]:
                chunk = self._memory_store['chunks'][idx]
                results.append((chunk, score))
            
            return results
    
    def delete(self, chunk_ids: List[str]) -> Dict[str, Any]:
        """删除向量"""
        if self._collection is not None:
            self._collection.delete(ids=chunk_ids)
            
            return {
                'success': True,
                'deleted_count': len(chunk_ids),
                'remaining_count': self._collection.count()
            }
        else:
            indices_to_remove = []
            for chunk_id in chunk_ids:
                if chunk_id in self._memory_store['ids']:
                    idx = self._memory_store['ids'].index(chunk_id)
                    indices_to_remove.append(idx)
            
            for idx in sorted(indices_to_remove, reverse=True):
                self._memory_store['ids'].pop(idx)
                self._memory_store['vectors'].pop(idx)
                self._memory_store['chunks'].pop(idx)
            
            return {
                'success': True,
                'deleted_count': len(indices_to_remove),
                'remaining_count': len(self._memory_store['ids'])
            }
    
    def get_stats(self) -> IndexStats:
        """获取统计信息"""
        if self._collection is not None:
            count = self._collection.count()
        else:
            count = len(self._memory_store['ids'])
        
        return IndexStats(
            total_documents=0,
            total_chunks=count,
            total_vectors=count,
            vector_dimension=self.embedding_dimension,
            embedding_model='',
            vector_store_type='chroma',
            index_size_mb=0.0,
            last_updated=datetime.now()
        )
    
    def save(self, path: str = None) -> bool:
        """保存索引（ChromaDB自动持久化）"""
        if self._collection is not None:
            return True
        
        if path:
            import json
            save_data = {
                'ids': self._memory_store['ids'],
                'vectors': self._memory_store['vectors'],
                'chunks': [c.to_dict() for c in self._memory_store['chunks']]
            }
            
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False)
            
            return True
        
        return False
    
    def load(self, path: str = None) -> bool:
        """加载索引"""
        if self._collection is not None:
            return True
        
        if path and Path(path).exists():
            import json
            with open(path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            self._memory_store['ids'] = save_data['ids']
            self._memory_store['vectors'] = save_data['vectors']
            self._memory_store['chunks'] = [
                Chunk.from_dict(c) for c in save_data['chunks']
            ]
            
            return True
        
        return False
    
    def clear(self) -> bool:
        """清空索引"""
        if self._collection is not None:
            all_ids = self._collection.get()['ids']
            if all_ids:
                self._collection.delete(ids=all_ids)
        else:
            self._memory_store = {
                'vectors': [],
                'chunks': [],
                'ids': []
            }
        
        return True


VectorStoreRegistry.register(VectorStoreType.CHROMA, ChromaStore)
