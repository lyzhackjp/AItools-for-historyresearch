"""
Markdown文档加载器

支持Markdown文档的加载和解析。
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import re

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.loaders.base_loader import BaseLoader, LoaderRegistry
from rag_module.core.types import Document, DocumentType


class MarkdownLoader(BaseLoader):
    """Markdown文档加载器"""
    
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```', re.MULTILINE)
    LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.extract_links = self.config.get('markdown_extract_links', True)
        self.extract_code_blocks = self.config.get('markdown_extract_code_blocks', True)
        self.preserve_formatting = self.config.get('preserve_formatting', True)
    
    def load(self, source: str) -> List[Document]:
        """
        加载Markdown文档
        
        Args:
            source: Markdown文件路径
            
        Returns:
            List[Document]: 加载的文档列表
        """
        if not self.supports(source):
            raise ValueError(f"不支持的文件类型: {source}")
        
        content = self._read_file(source)
        file_metadata = self._get_file_metadata(source)
        
        sections = self._extract_sections(content)
        
        documents = []
        
        if sections:
            for i, section in enumerate(sections):
                metadata = {
                    **file_metadata,
                    'section_index': i,
                    'section_title': section['title'],
                    'section_level': section['level'],
                    'total_sections': len(sections),
                    'loader': 'markdown'
                }
                
                if self.extract_links:
                    metadata['links'] = self._extract_links(section['content'])
                
                if self.extract_code_blocks:
                    metadata['code_blocks'] = self._extract_code_blocks(section['content'])
                
                doc_id = self._generate_doc_id(section['content'], f"{source}:{i}")
                
                document = Document(
                    id=doc_id,
                    content=section['content'],
                    metadata=metadata,
                    doc_type=DocumentType.MARKDOWN,
                    source_path=source
                )
                
                documents.append(document)
        else:
            metadata = {
                **file_metadata,
                'loader': 'markdown'
            }
            
            if self.extract_links:
                metadata['links'] = self._extract_links(content)
            
            if self.extract_code_blocks:
                metadata['code_blocks'] = self._extract_code_blocks(content)
            
            doc_id = self._generate_doc_id(content, source)
            
            document = Document(
                id=doc_id,
                content=content,
                metadata=metadata,
                doc_type=DocumentType.MARKDOWN,
                source_path=source
            )
            
            documents.append(document)
        
        return documents
    
    def supports(self, source: str) -> bool:
        """检查是否支持Markdown格式"""
        suffix = Path(source).suffix.lower()
        return suffix in ['.md', '.markdown']
    
    def _extract_sections(self, content: str) -> List[Dict[str, Any]]:
        """提取Markdown章节"""
        sections = []
        lines = content.split('\n')
        
        current_section = {
            'title': 'Document Start',
            'level': 0,
            'content': [],
            'start_line': 0
        }
        
        for i, line in enumerate(lines):
            heading_match = self.HEADING_PATTERN.match(line)
            
            if heading_match:
                if current_section['content']:
                    sections.append({
                        'title': current_section['title'],
                        'level': current_section['level'],
                        'content': '\n'.join(current_section['content']).strip(),
                        'start_line': current_section['start_line'],
                        'end_line': i - 1
                    })
                
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                current_section = {
                    'title': title,
                    'level': level,
                    'content': [line],
                    'start_line': i
                }
            else:
                current_section['content'].append(line)
        
        if current_section['content']:
            sections.append({
                'title': current_section['title'],
                'level': current_section['level'],
                'content': '\n'.join(current_section['content']).strip(),
                'start_line': current_section['start_line'],
                'end_line': len(lines) - 1
            })
        
        return sections
    
    def _extract_links(self, content: str) -> List[Dict[str, str]]:
        """提取链接"""
        links = []
        for match in self.LINK_PATTERN.finditer(content):
            links.append({
                'text': match.group(1),
                'url': match.group(2)
            })
        return links
    
    def _extract_code_blocks(self, content: str) -> List[Dict[str, Any]]:
        """提取代码块"""
        code_blocks = []
        for i, match in enumerate(self.CODE_BLOCK_PATTERN.finditer(content)):
            block_content = match.group(0)
            lines = block_content.split('\n')
            
            language = ''
            if lines[0].startswith('```'):
                language = lines[0][3:].strip()
            
            code_blocks.append({
                'index': i,
                'language': language,
                'line_count': len(lines) - 2,
                'content_preview': '\n'.join(lines[1:4])[:100]
            })
        
        return code_blocks
    
    def extract_outline(self, content: str) -> List[Dict[str, Any]]:
        """提取文档大纲"""
        outline = []
        
        for match in self.HEADING_PATTERN.finditer(content):
            level = len(match.group(1))
            title = match.group(2).strip()
            
            outline.append({
                'level': level,
                'title': title,
                'position': match.start()
            })
        
        return outline


LoaderRegistry.register(DocumentType.MARKDOWN, MarkdownLoader)
