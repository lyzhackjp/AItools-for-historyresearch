"""
语义文本分块器

基于语义相似度进行文本分割，保持语义完整性。
"""

from typing import List, Dict, Any, Optional
import re

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.splitters.base_splitter import BaseSplitter, SplitterRegistry
from rag_module.core.types import Document, Chunk, ChunkStrategy


class SemanticSplitter(BaseSplitter):
    """语义文本分块器"""
    
    SENTENCE_ENDINGS = ['。', '！', '？', '.', '!', '?', '\n']
    
    def __init__(self,
                 chunk_size: int = 512,
                 chunk_overlap: int = 50,
                 min_chunk_size: int = 100,
                 similarity_threshold: float = 0.7,
                 embedding_model: str = None,
                 **kwargs):
        super().__init__(chunk_size, chunk_overlap, **kwargs)
        self.min_chunk_size = min_chunk_size
        self.similarity_threshold = similarity_threshold
        self.embedding_model = embedding_model
        self._embedder = None
    
    def split(self, document: Document) -> List[Chunk]:
        """
        分割文档
        
        Args:
            document: 要分割的文档
            
        Returns:
            List[Chunk]: 分割后的块列表
        """
        sentences = self._split_into_sentences(document.content)
        
        if self._embedder is None:
            self._init_embedder()
        
        chunks = []
        current_sentences = []
        current_length = 0
        
        for i, sentence in enumerate(sentences):
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.chunk_size and current_sentences:
                chunk_text = ''.join(current_sentences)
                
                if len(chunk_text) >= self.min_chunk_size:
                    chunk = self._create_chunk(document, chunk_text, len(chunks))
                    chunks.append(chunk)
                
                if self.chunk_overlap > 0 and current_sentences:
                    overlap_sentences = self._get_overlap_sentences(current_sentences)
                    current_sentences = overlap_sentences
                    current_length = sum(len(s) for s in overlap_sentences)
                else:
                    current_sentences = []
                    current_length = 0
            
            current_sentences.append(sentence)
            current_length += sentence_length
        
        if current_sentences:
            chunk_text = ''.join(current_sentences)
            if len(chunk_text) >= self.min_chunk_size or not chunks:
                chunk = self._create_chunk(document, chunk_text, len(chunks))
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
        sentences = self._split_into_sentences(text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunks.append(''.join(current_chunk))
                current_chunk = []
                current_length = 0
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        if current_chunk:
            chunks.append(''.join(current_chunk))
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """分割成句子"""
        sentences = []
        current_sentence = []
        
        for char in text:
            current_sentence.append(char)
            
            if char in self.SENTENCE_ENDINGS:
                sentence = ''.join(current_sentence).strip()
                if sentence:
                    sentences.append(sentence)
                current_sentence = []
        
        if current_sentence:
            sentence = ''.join(current_sentence).strip()
            if sentence:
                sentences.append(sentence)
        
        return sentences
    
    def _init_embedder(self):
        """初始化嵌入模型"""
        try:
            from modules.embedding_manager import EmbeddingManager
            self._embedder = EmbeddingManager()
        except ImportError:
            self._embedder = None
    
    def _get_sentence_embedding(self, sentence: str):
        """获取句子嵌入向量"""
        if self._embedder:
            return self._embedder._get_embedding(sentence)
        return None
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """计算语义相似度"""
        if self._embedder is None:
            return 0.5
        
        try:
            emb1 = self._get_sentence_embedding(text1)
            emb2 = self._get_sentence_embedding(text2)
            
            if emb1 is not None and emb2 is not None:
                import numpy as np
                similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
                return float(similarity)
        except Exception:
            pass
        
        return 0.5
    
    def _get_overlap_sentences(self, sentences: List[str]) -> List[str]:
        """获取重叠句子"""
        if not sentences:
            return []
        
        overlap_length = 0
        overlap_sentences = []
        
        for sentence in reversed(sentences):
            if overlap_length + len(sentence) > self.chunk_overlap:
                break
            overlap_sentences.insert(0, sentence)
            overlap_length += len(sentence)
        
        return overlap_sentences
    
    def _create_chunk(self, document: Document, content: str, index: int) -> Chunk:
        """创建块对象"""
        chunk_id = self._generate_chunk_id(document.id, index, content)
        
        start_pos = document.content.find(content[:50]) if content else 0
        
        return Chunk(
            id=chunk_id,
            document_id=document.id,
            content=content,
            metadata={
                **document.metadata,
                'chunk_index': index,
                'chunk_size': len(content),
                'splitter': 'semantic'
            },
            chunk_index=index,
            start_char=start_pos,
            end_char=start_pos + len(content)
        )
    
    def semantic_chunking_with_embeddings(self, document: Document) -> List[Chunk]:
        """基于嵌入向量的语义分块"""
        if self._embedder is None:
            return self.split(document)
        
        sentences = self._split_into_sentences(document.content)
        
        if len(sentences) <= 1:
            return [self._create_chunk(document, document.content, 0)]
        
        breakpoints = [0]
        
        for i in range(1, len(sentences)):
            prev_text = sentences[i-1]
            curr_text = sentences[i]
            
            similarity = self._calculate_semantic_similarity(prev_text, curr_text)
            
            if similarity < self.similarity_threshold:
                breakpoints.append(i)
        
        breakpoints.append(len(sentences))
        
        chunks = []
        for i in range(len(breakpoints) - 1):
            start = breakpoints[i]
            end = breakpoints[i + 1]
            
            chunk_sentences = sentences[start:end]
            chunk_text = ''.join(chunk_sentences)
            
            if len(chunk_text) >= self.min_chunk_size:
                chunk = self._create_chunk(document, chunk_text, len(chunks))
                chunks.append(chunk)
        
        return chunks


SplitterRegistry.register(ChunkStrategy.SEMANTIC, SemanticSplitter)
