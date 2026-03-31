"""
递归文本分块器

使用递归策略分割文本，优先按段落、句子等自然边界分割。
"""

from typing import List, Dict, Any, Optional
import re

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.splitters.base_splitter import BaseSplitter, SplitterRegistry
from rag_module.core.types import Document, Chunk, ChunkStrategy


class RecursiveSplitter(BaseSplitter):
    """递归文本分块器"""
    
    DEFAULT_SEPARATORS = [
        '\n\n\n',
        '\n\n',
        '\n',
        '。',
        '！',
        '？',
        '.',
        '!',
        '?',
        '；',
        ';',
        '，',
        ',',
        ' ',
        ''
    ]
    
    JAPANESE_SEPARATORS = [
        '\n\n\n',
        '\n\n',
        '\n',
        '。',
        '！',
        '？',
        '・',
        '、',
        ' ',
        ''
    ]
    
    def __init__(self,
                 chunk_size: int = 512,
                 chunk_overlap: int = 50,
                 separators: List[str] = None,
                 keep_separator: bool = True,
                 length_function: str = 'character',
                 language: str = 'auto',
                 **kwargs):
        super().__init__(chunk_size, chunk_overlap, **kwargs)
        self.separators = separators or self.DEFAULT_SEPARATORS
        self.keep_separator = keep_separator
        self.length_function = length_function
        self.language = language
    
    def split(self, document: Document) -> List[Chunk]:
        """
        分割文档
        
        Args:
            document: 要分割的文档
            
        Returns:
            List[Chunk]: 分割后的块列表
        """
        text = document.content
        
        if self.language == 'auto':
            self._detect_language(text)
        
        text_chunks = self.split_text(text)
        
        chunks = []
        current_pos = 0
        
        for i, chunk_text in enumerate(text_chunks):
            start_pos = text.find(chunk_text, current_pos)
            end_pos = start_pos + len(chunk_text)
            current_pos = end_pos
            
            chunk_id = self._generate_chunk_id(document.id, i, chunk_text)
            
            chunk = Chunk(
                id=chunk_id,
                document_id=document.id,
                content=chunk_text,
                metadata={
                    **document.metadata,
                    'chunk_index': i,
                    'chunk_size': len(chunk_text),
                    'splitter': 'recursive'
                },
                chunk_index=i,
                start_char=start_pos,
                end_char=end_pos
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def split_text(self, text: str) -> List[str]:
        """
        分割文本
        
        Args:
            text: 要分割的文本
            
        Returns:
            List[str]: 分割后的文本片段列表
        """
        if self._calculate_length(text, self.length_function) <= self.chunk_size:
            return [text.strip()] if text.strip() else []
        
        chunks = []
        current_chunk = ''
        
        separators = self._get_separators(text)
        
        for separator in separators:
            if separator == '':
                return self._split_by_size(text)
            
            splits = self._split_by_separator(text, separator)
            
            valid = True
            for split in splits:
                if self._calculate_length(split, self.length_function) > self.chunk_size:
                    valid = False
                    break
            
            if valid:
                return self._merge_splits(splits, separator)
        
        return chunks
    
    def _get_separators(self, text: str) -> List[str]:
        """获取适合的分隔符"""
        if self.language == 'japanese':
            return self.JAPANESE_SEPARATORS
        elif self.language == 'chinese':
            return self.DEFAULT_SEPARATORS
        return self.separators
    
    def _detect_language(self, text: str):
        """检测文本语言"""
        japanese_chars = sum(1 for c in text if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        
        if japanese_chars > chinese_chars * 0.1:
            self.language = 'japanese'
        elif chinese_chars > len(text) * 0.3:
            self.language = 'chinese'
        else:
            self.language = 'general'
    
    def _split_by_separator(self, text: str, separator: str) -> List[str]:
        """按分隔符分割"""
        if separator:
            splits = text.split(separator)
            if self.keep_separator:
                splits = [s + separator for s in splits[:-1]] + [splits[-1]]
            return [s for s in splits if s.strip()]
        return [text]
    
    def _merge_splits(self, splits: List[str], separator: str) -> List[str]:
        """合并分割片段"""
        chunks = []
        current_chunk = ''
        
        for split in splits:
            split_length = self._calculate_length(split, self.length_function)
            current_length = self._calculate_length(current_chunk, self.length_function)
            
            if current_length + split_length <= self.chunk_size:
                current_chunk += split
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                if split_length > self.chunk_size:
                    sub_chunks = self._split_by_size(split)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ''
                else:
                    current_chunk = split
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        if self.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._add_overlap(chunks)
        
        return chunks
    
    def _split_by_size(self, text: str) -> List[str]:
        """按固定大小分割"""
        chunks = []
        
        if self.length_function == 'token':
            step = self.chunk_size - self.chunk_overlap
            for i in range(0, len(text), step):
                chunk = text[i:i + self.chunk_size]
                if chunk.strip():
                    chunks.append(chunk)
        else:
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunk = text[i:i + self.chunk_size]
                if chunk.strip():
                    chunks.append(chunk)
        
        return chunks
    
    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """添加重叠"""
        overlapped = []
        
        for i, chunk in enumerate(chunks):
            if i > 0 and self.chunk_overlap > 0:
                prev_chunk = chunks[i - 1]
                overlap_text = prev_chunk[-self.chunk_overlap:]
                chunk = overlap_text + chunk
            
            overlapped.append(chunk)
        
        return overlapped


SplitterRegistry.register(ChunkStrategy.RECURSIVE, RecursiveSplitter)
