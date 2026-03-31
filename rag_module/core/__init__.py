"""
RAG核心模块

提供核心配置、类型定义和RAG引擎。
"""

from .config import RAGConfig, LoaderConfig, SplitterConfig, RetrieverConfig
from .types import (
    Document, DocumentType, 
    Chunk, ChunkStrategy,
    QueryResult, RetrievalResult,
    IndexStats, VectorStoreType, RetrievalStrategy
)
from .rag_engine import RAGEngine

__all__ = [
    'RAGConfig',
    'LoaderConfig',
    'SplitterConfig',
    'RetrieverConfig',
    'Document',
    'DocumentType',
    'Chunk',
    'ChunkStrategy',
    'QueryResult',
    'RetrievalResult',
    'IndexStats',
    'VectorStoreType',
    'RetrievalStrategy',
    'RAGEngine'
]
