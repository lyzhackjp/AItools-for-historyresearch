"""
文本文件加载器

支持纯文本文件的加载和解析。
"""

from typing import List, Dict, Any, Optional
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.loaders.base_loader import BaseLoader, LoaderRegistry
from rag_module.core.types import Document, DocumentType


class TextLoader(BaseLoader):
    """文本文件加载器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.encoding = self.config.get('encoding', 'utf-8')
        self.autodetect_encoding = self.config.get('autodetect_encoding', True)
        self.split_by_paragraph = self.config.get('split_by_paragraph', False)
        self.min_paragraph_length = self.config.get('min_paragraph_length', 100)
    
    def load(self, source: str) -> List[Document]:
        """
        加载文本文件
        
        Args:
            source: 文本文件路径
            
        Returns:
            List[Document]: 加载的文档列表
        """
        if not self.supports(source):
            raise ValueError(f"不支持的文件类型: {source}")
        
        if self.autodetect_encoding:
            content = self._read_file(source)
        else:
            content = self._read_file(source, self.encoding)
        
        file_metadata = self._get_file_metadata(source)
        
        line_count = len(content.split('\n'))
        word_count = len(content.split())
        char_count = len(content)
        
        metadata = {
            **file_metadata,
            'line_count': line_count,
            'word_count': word_count,
            'char_count': char_count,
            'loader': 'text'
        }
        
        if self.split_by_paragraph:
            return self._split_by_paragraphs(content, source, metadata)
        
        doc_id = self._generate_doc_id(content, source)
        
        document = Document(
            id=doc_id,
            content=content,
            metadata=metadata,
            doc_type=DocumentType.TEXT,
            source_path=source
        )
        
        return [document]
    
    def supports(self, source: str) -> bool:
        """检查是否支持文本格式"""
        suffix = Path(source).suffix.lower()
        return suffix in ['.txt', '.text', '']
    
    def _split_by_paragraphs(self, content: str, source: str, 
                            base_metadata: Dict[str, Any]) -> List[Document]:
        """按段落分割文档"""
        documents = []
        
        paragraphs = self._extract_paragraphs(content)
        
        for i, paragraph in enumerate(paragraphs):
            if len(paragraph) < self.min_paragraph_length:
                continue
            
            metadata = {
                **base_metadata,
                'paragraph_index': i,
                'total_paragraphs': len(paragraphs),
                'paragraph_length': len(paragraph)
            }
            
            doc_id = self._generate_doc_id(paragraph, f"{source}:{i}")
            
            document = Document(
                id=doc_id,
                content=paragraph,
                metadata=metadata,
                doc_type=DocumentType.TEXT,
                source_path=source
            )
            
            documents.append(document)
        
        return documents
    
    def _extract_paragraphs(self, content: str) -> List[str]:
        """提取段落"""
        paragraphs = []
        current_paragraph = []
        
        for line in content.split('\n'):
            stripped = line.strip()
            
            if stripped:
                current_paragraph.append(stripped)
            else:
                if current_paragraph:
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
        
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        return paragraphs


LoaderRegistry.register(DocumentType.TEXT, TextLoader)
