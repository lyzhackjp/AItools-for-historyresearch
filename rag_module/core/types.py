"""
RAG模块核心类型定义

定义文档、分块、查询结果等核心数据结构。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class DocumentType(Enum):
    """文档类型枚举"""
    PDF = 'pdf'
    MARKDOWN = 'markdown'
    TEXT = 'text'
    HTML = 'html'
    DOCX = 'docx'
    UNKNOWN = 'unknown'


class ChunkStrategy(Enum):
    """分块策略枚举"""
    RECURSIVE = 'recursive'
    SEMANTIC = 'semantic'
    FIXED = 'fixed'
    SENTENCE = 'sentence'
    PARAGRAPH = 'paragraph'


class VectorStoreType(Enum):
    """向量存储类型枚举"""
    CHROMA = 'chroma'
    FAISS = 'faiss'
    MEMORY = 'memory'


class RetrievalStrategy(Enum):
    """检索策略枚举"""
    VECTOR = 'vector'
    KEYWORD = 'keyword'
    HYBRID = 'hybrid'


@dataclass
class Document:
    """文档数据结构"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    doc_type: DocumentType = DocumentType.UNKNOWN
    source_path: str = ''
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'content': self.content,
            'metadata': self.metadata,
            'doc_type': self.doc_type.value,
            'source_path': self.source_path,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        return cls(
            id=data['id'],
            content=data['content'],
            metadata=data.get('metadata', {}),
            doc_type=DocumentType(data.get('doc_type', 'unknown')),
            source_path=data.get('source_path', ''),
            created_at=datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now()
        )


@dataclass
class Chunk:
    """文本分块数据结构"""
    id: str
    document_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'document_id': self.document_id,
            'content': self.content,
            'metadata': self.metadata,
            'chunk_index': self.chunk_index,
            'start_char': self.start_char,
            'end_char': self.end_char
        }


@dataclass
class QueryResult:
    """查询结果数据结构"""
    query: str
    answer: str
    source_chunks: List[Chunk] = field(default_factory=list)
    confidence: float = 0.0
    retrieval_time: float = 0.0
    generation_time: float = 0.0
    total_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'query': self.query,
            'answer': self.answer,
            'source_chunks': [c.to_dict() for c in self.source_chunks],
            'confidence': self.confidence,
            'retrieval_time': self.retrieval_time,
            'generation_time': self.generation_time,
            'total_time': self.total_time,
            'metadata': self.metadata
        }


@dataclass
class RetrievalResult:
    """检索结果数据结构"""
    chunks: List[Chunk]
    scores: List[float]
    query: str
    retrieval_strategy: RetrievalStrategy
    total_candidates: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'chunks': [c.to_dict() for c in self.chunks],
            'scores': self.scores,
            'query': self.query,
            'retrieval_strategy': self.retrieval_strategy.value,
            'total_candidates': self.total_candidates
        }


@dataclass
class IndexStats:
    """索引统计信息"""
    total_documents: int = 0
    total_chunks: int = 0
    total_vectors: int = 0
    vector_dimension: int = 0
    embedding_model: str = ''
    vector_store_type: str = ''
    index_size_mb: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_documents': self.total_documents,
            'total_chunks': self.total_chunks,
            'total_vectors': self.total_vectors,
            'vector_dimension': self.vector_dimension,
            'embedding_model': self.embedding_model,
            'vector_store_type': self.vector_store_type,
            'index_size_mb': self.index_size_mb,
            'last_updated': self.last_updated.isoformat()
        }
