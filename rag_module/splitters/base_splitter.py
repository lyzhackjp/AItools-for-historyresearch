"""
文本分块器基类

定义文本分块器的统一接口和基础功能。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import hashlib

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.core.types import Document, Chunk, ChunkStrategy


class BaseSplitter(ABC):
    """文本分块器基类"""
    
    def __init__(self, 
                 chunk_size: int = 512,
                 chunk_overlap: int = 50,
                 **kwargs):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    @abstractmethod
    def split(self, document: Document) -> List[Chunk]:
        """
        分割文档
        
        Args:
            document: 要分割的文档
            
        Returns:
            List[Chunk]: 分割后的块列表
        """
        pass
    
    @abstractmethod
    def split_text(self, text: str) -> List[str]:
        """
        分割文本
        
        Args:
            text: 要分割的文本
            
        Returns:
            List[str]: 分割后的文本片段列表
        """
        pass
    
    def _generate_chunk_id(self, document_id: str, chunk_index: int, content: str) -> str:
        """生成块ID"""
        hash_input = f"{document_id}:{chunk_index}:{content[:50]}"
        return hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:16]
    
    def _calculate_length(self, text: str, method: str = 'character') -> int:
        """计算文本长度"""
        if method == 'character':
            return len(text)
        elif method == 'token':
            return self._count_tokens(text)
        return len(text)
    
    def _count_tokens(self, text: str) -> int:
        """估算token数量"""
        try:
            import tiktoken
            enc = tiktoken.get_encoding('cl100k_base')
            return len(enc.encode(text))
        except ImportError:
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            other_chars = len(text) - chinese_chars
            return chinese_chars + other_chars // 4


class SplitterRegistry:
    """分块器注册表"""
    
    _splitters: Dict[ChunkStrategy, type] = {}
    
    @classmethod
    def register(cls, strategy: ChunkStrategy, splitter_class: type):
        """注册分块器"""
        cls._splitters[strategy] = splitter_class
    
    @classmethod
    def get_splitter(cls, strategy: ChunkStrategy, **kwargs) -> Optional[BaseSplitter]:
        """获取分块器实例"""
        splitter_class = cls._splitters.get(strategy)
        if splitter_class:
            return splitter_class(**kwargs)
        return None
    
    @classmethod
    def get_supported_strategies(cls) -> List[ChunkStrategy]:
        """获取支持的策略"""
        return list(cls._splitters.keys())


class TextSplitterManager:
    """文本分块器管理器"""
    
    def __init__(self, 
                 strategy: ChunkStrategy = ChunkStrategy.RECURSIVE,
                 chunk_size: int = 512,
                 chunk_overlap: int = 50,
                 **kwargs):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.kwargs = kwargs
        self._init_splitters()
    
    def _init_splitters(self):
        """初始化分块器"""
        from rag_module.splitters.recursive_splitter import RecursiveSplitter
        from rag_module.splitters.semantic_splitter import SemanticSplitter
        
        SplitterRegistry.register(ChunkStrategy.RECURSIVE, RecursiveSplitter)
        SplitterRegistry.register(ChunkStrategy.SEMANTIC, SemanticSplitter)
    
    def split(self, document: Document) -> List[Chunk]:
        """
        分割文档
        
        Args:
            document: 要分割的文档
            
        Returns:
            List[Chunk]: 分割后的块列表
        """
        splitter = SplitterRegistry.get_splitter(
            self.strategy,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            **self.kwargs
        )
        
        if splitter is None:
            raise ValueError(f"未找到策略 {self.strategy} 的分块器")
        
        return splitter.split(document)
    
    def split_documents(self, documents: List[Document]) -> List[Chunk]:
        """
        批量分割文档
        
        Args:
            documents: 文档列表
            
        Returns:
            List[Chunk]: 所有分割后的块列表
        """
        all_chunks = []
        
        for document in documents:
            chunks = self.split(document)
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def split_text(self, text: str) -> List[str]:
        """
        分割文本
        
        Args:
            text: 要分割的文本
            
        Returns:
            List[str]: 分割后的文本片段列表
        """
        splitter = SplitterRegistry.get_splitter(
            self.strategy,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            **self.kwargs
        )
        
        if splitter is None:
            raise ValueError(f"未找到策略 {self.strategy} 的分块器")
        
        return splitter.split_text(text)
