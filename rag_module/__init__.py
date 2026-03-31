"""
RAG (Retrieval-Augmented Generation) 模块

提供完整的检索增强生成功能，支持文档加载、文本分块、向量检索和生成式问答。

核心组件：
- RAGEngine: RAG引擎主类
- DocumentLoaders: 文档加载器（PDF、Markdown、TXT等）
- TextSplitters: 文本分块器（递归、语义分块）
- VectorStores: 向量存储（ChromaDB、FAISS）
- Retrievers: 检索器（向量检索、混合检索）

使用示例：
    from rag_module import RAGEngine, RAGConfig
    
    config = RAGConfig(
        embedding_model='bge-m3',
        vector_store='chroma',
        chunk_size=512,
        chunk_overlap=50
    )
    
    engine = RAGEngine(config)
    engine.add_documents(['doc1.pdf', 'doc2.md'])
    
    result = engine.query('什么是明治维新？')
    print(result.answer)
"""

__version__ = '1.0.0'
__author__ = 'AItools-for-historyresearch'

from .core.rag_engine import RAGEngine
from .core.config import RAGConfig
from .core.types import Document, Chunk, QueryResult

__all__ = [
    'RAGEngine',
    'RAGConfig',
    'Document',
    'Chunk',
    'QueryResult'
]
