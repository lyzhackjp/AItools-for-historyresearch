"""
RAG统一接口模块

提供统一的RAG接口，支持在自研RAG、Dify、Ragflow之间切换。
"""

from rag_module.adapters.base_adapter import BaseRAGAdapter
from rag_module.adapters.built_in_adapter import BuiltInRAGAdapter
from rag_module.adapters.dify_adapter import DifyRAGAdapter
from rag_module.adapters.ragflow_adapter import RagflowRAGAdapter
from rag_module.adapters.rag_factory import RAGFactory, RAGBackend

__all__ = [
    'BaseRAGAdapter',
    'BuiltInRAGAdapter',
    'DifyRAGAdapter',
    'RagflowRAGAdapter',
    'RAGFactory',
    'RAGBackend'
]
