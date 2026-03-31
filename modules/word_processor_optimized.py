"""
Word文档处理器模块 - 优化版

高效的Word文档处理工具

优化内容 (v2.0.0):
- 改进样式解析：完整解析段落、字符样式
- 支持表格处理：提取表格内容和结构
- 保留图片链接：提取图片信息和链接
- 支持批注和修订：提取批注和修订记录

核心功能：
- 样式解析：完整解析文档样式
- 表格处理：提取表格内容和结构
- 图片处理：提取图片信息和链接
- 批注提取：提取文档批注
- 修订追踪：提取修订记录

支持的文档格式：
- .docx (Office Open XML)
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging


class DocumentSection(Enum):
    """文档节类型枚举"""
    PARAGRAPH = 'paragraph'
    TABLE = 'table'
    HEADER = 'header'
    FOOTER = 'footer'
    IMAGE = 'image'


@dataclass
class TextStyle:
    """文本样式"""
    font_name: str = ""
    font_size: float = 0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: str = ""
    highlight: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'font_name': self.font_name,
            'font_size': self.font_size,
            'bold': self.bold,
            'italic': self.italic,
            'underline': self.underline,
            'color': self.color,
            'highlight': self.highlight
        }


@dataclass
class ParagraphStyle:
    """段落样式"""
    style_name: str = ""
    alignment: str = ""
    indent_left: float = 0
    indent_first_line: float = 0
    line_spacing: float = 0
    space_before: float = 0
    space_after: float = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'style_name': self.style_name,
            'alignment': self.alignment,
            'indent_left': self.indent_left,
            'indent_first_line': self.indent_first_line,
            'line_spacing': self.line_spacing,
            'space_before': self.space_before,
            'space_after': self.space_after
        }


@dataclass
class TableData:
    """表格数据"""
    table_id: int
    rows: List[List[str]]
    row_count: int
    col_count: int
    has_header: bool = False
    styles: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """转换为Markdown格式"""
        if not self.rows:
            return ""
        
        lines = []
        
        if self.rows:
            header = self.rows[0]
            lines.append("| " + " | ".join(str(cell) for cell in header) + " |")
            lines.append("| " + " | ".join("---" for _ in header) + " |")
            
            for row in self.rows[1:]:
                lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        
        return "\n".join(lines)


@dataclass
class ImageInfo:
    """图片信息"""
    image_id: str
    filename: str
    relationship_id: str = ""
    width: int = 0
    height: int = 0
    content_type: str = ""
    embedded: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'image_id': self.image_id,
            'filename': self.filename,
            'relationship_id': self.relationship_id,
            'width': self.width,
            'height': self.height,
            'content_type': self.content_type,
            'embedded': self.embedded
        }


@dataclass
class Comment:
    """批注数据"""
    comment_id: str
    author: str = ""
    date: str = ""
    text: str = ""
    target_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'comment_id': self.comment_id,
            'author': self.author,
            'date': self.date,
            'text': self.text,
            'target_text': self.target_text
        }


@dataclass
class Revision:
    """修订数据"""
    revision_id: str
    revision_type: str
    author: str = ""
    date: str = ""
    original_text: str = ""
    modified_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'revision_id': self.revision_id,
            'revision_type': self.revision_type,
            'author': self.author,
            'date': self.date,
            'original_text': self.original_text,
            'modified_text': self.modified_text
        }


@dataclass
class DocumentContent:
    """文档内容"""
    paragraphs: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[TableData] = field(default_factory=list)
    images: List[ImageInfo] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)
    revisions: List[Revision] = field(default_factory=list)
    styles: Dict[str, ParagraphStyle] = field(default_factory=dict)


@dataclass
class WordProcessingResult:
    """Word处理结果"""
    success: bool
    content: DocumentContent
    text: str
    char_count: int
    word_count: int
    paragraph_count: int
    table_count: int
    image_count: int
    processing_time: float
    errors: List[str] = field(default_factory=list)


class WordProcessorOptimized:
    """Word文档处理器 - 优化版"""
    
    NAMESPACES = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
        'v': 'urn:schemas-microsoft-com:vml',
        'o': 'urn:schemas-microsoft-com:office:office'
    }
    
    def __init__(self):
        """初始化Word处理器"""
        self.logger = logging.getLogger('WordProcessorOptimized')
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def _register_namespaces(self):
        """注册命名空间"""
        for prefix, uri in self.NAMESPACES.items():
            ET.register_namespace(prefix, uri)
    
    def process_document(self, docx_path: str) -> WordProcessingResult:
        """
        处理Word文档
        
        Args:
            docx_path: Word文档路径
            
        Returns:
            WordProcessingResult: 处理结果
        """
        import time
        start_time = time.time()
        
        docx_path = Path(docx_path)
        
        if not docx_path.exists():
            raise FileNotFoundError(f"Word文档不存在: {docx_path}")
        
        if not docx_path.suffix.lower() == '.docx':
            raise ValueError(f"不支持的文件格式: {docx_path.suffix}")
        
        try:
            content = self._extract_all_content(str(docx_path))
            
            text_parts = []
            for para in content.paragraphs:
                text_parts.append(para.get('text', ''))
            
            for table in content.tables:
                text_parts.append(table.to_markdown())
            
            full_text = '\n'.join(text_parts)
            
            processing_time = time.time() - start_time
            
            return WordProcessingResult(
                success=True,
                content=content,
                text=full_text,
                char_count=len(full_text),
                word_count=len(full_text.split()),
                paragraph_count=len(content.paragraphs),
                table_count=len(content.tables),
                image_count=len(content.images),
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Word文档处理失败: {e}")
            
            return WordProcessingResult(
                success=False,
                content=DocumentContent(),
                text='',
                char_count=0,
                word_count=0,
                paragraph_count=0,
                table_count=0,
                image_count=0,
                processing_time=processing_time,
                errors=[str(e)]
            )
    
    def _extract_all_content(self, docx_path: str) -> DocumentContent:
        """提取所有内容"""
        content = DocumentContent()
        
        with zipfile.ZipFile(docx_path, 'r') as zf:
            document_xml = zf.read('word/document.xml')
            document_root = ET.fromstring(document_xml)
            
            content.styles = self._extract_styles(zf)
            
            content.paragraphs = self._extract_paragraphs(document_root)
            
            content.tables = self._extract_tables(document_root)
            
            content.images = self._extract_images(zf, document_root)
            
            content.comments = self._extract_comments(zf)
            
            content.revisions = self._extract_revisions(document_root)
        
        return content
    
    def _extract_styles(self, zf: zipfile.ZipFile) -> Dict[str, ParagraphStyle]:
        """提取样式"""
        styles = {}
        
        try:
            styles_xml = zf.read('word/styles.xml')
            styles_root = ET.fromstring(styles_xml)
            
            for style_elem in styles_root.findall('.//w:style', self.NAMESPACES):
                style_id = style_elem.get(f'{{{self.NAMESPACES["w"]}}}styleId', '')
                style_name = ''
                
                name_elem = style_elem.find('w:name', self.NAMESPACES)
                if name_elem is not None:
                    style_name = name_elem.get(f'{{{self.NAMESPACES["w"]}}}val', '')
                
                pPr = style_elem.find('w:pPr', self.NAMESPACES)
                
                paragraph_style = ParagraphStyle(style_name=style_name or style_id)
                
                if pPr is not None:
                    jc = pPr.find('w:jc', self.NAMESPACES)
                    if jc is not None:
                        paragraph_style.alignment = jc.get(f'{{{self.NAMESPACES["w"]}}}val', '')
                    
                    ind = pPr.find('w:ind', self.NAMESPACES)
                    if ind is not None:
                        paragraph_style.indent_left = float(ind.get(f'{{{self.NAMESPACES["w"]}}}left', 0)) / 1440
                        paragraph_style.indent_first_line = float(ind.get(f'{{{self.NAMESPACES["w"]}}}firstLine', 0)) / 1440
                
                styles[style_id] = paragraph_style
                
        except KeyError:
            pass
        
        return styles
    
    def _extract_paragraphs(self, document_root: ET.Element) -> List[Dict[str, Any]]:
        """提取段落"""
        paragraphs = []
        
        for para_elem in document_root.findall('.//w:p', self.NAMESPACES):
            para_data = self._parse_paragraph(para_elem)
            if para_data.get('text', '').strip():
                paragraphs.append(para_data)
        
        return paragraphs
    
    def _parse_paragraph(self, para_elem: ET.Element) -> Dict[str, Any]:
        """解析单个段落"""
        text_parts = []
        runs_data = []
        
        for run_elem in para_elem.findall('.//w:r', self.NAMESPACES):
            run_text = ''
            for t_elem in run_elem.findall('.//w:t', self.NAMESPACES):
                if t_elem.text:
                    run_text += t_elem.text
            
            text_parts.append(run_text)
            
            text_style = self._parse_run_style(run_elem)
            runs_data.append({
                'text': run_text,
                'style': text_style.to_dict()
            })
        
        full_text = ''.join(text_parts)
        
        style_name = ''
        pPr = para_elem.find('w:pPr', self.NAMESPACES)
        if pPr is not None:
            pStyle = pPr.find('w:pStyle', self.NAMESPACES)
            if pStyle is not None:
                style_name = pStyle.get(f'{{{self.NAMESPACES["w"]}}}val', '')
        
        return {
            'text': full_text,
            'style_name': style_name,
            'runs': runs_data
        }
    
    def _parse_run_style(self, run_elem: ET.Element) -> TextStyle:
        """解析文本样式"""
        style = TextStyle()
        
        rPr = run_elem.find('w:rPr', self.NAMESPACES)
        if rPr is not None:
            rFonts = rPr.find('w:rFonts', self.NAMESPACES)
            if rFonts is not None:
                style.font_name = rFonts.get(f'{{{self.NAMESPACES["w"]}}}ascii', '')
            
            sz = rPr.find('w:sz', self.NAMESPACES)
            if sz is not None:
                style.font_size = float(sz.get(f'{{{self.NAMESPACES["w"]}}}val', 0)) / 2
            
            b = rPr.find('w:b', self.NAMESPACES)
            style.bold = b is not None
            
            i = rPr.find('w:i', self.NAMESPACES)
            style.italic = i is not None
            
            u = rPr.find('w:u', self.NAMESPACES)
            style.underline = u is not None
            
            color = rPr.find('w:color', self.NAMESPACES)
            if color is not None:
                style.color = color.get(f'{{{self.NAMESPACES["w"]}}}val', '')
            
            highlight = rPr.find('w:highlight', self.NAMESPACES)
            if highlight is not None:
                style.highlight = highlight.get(f'{{{self.NAMESPACES["w"]}}}val', '')
        
        return style
    
    def _extract_tables(self, document_root: ET.Element) -> List[TableData]:
        """提取表格"""
        tables = []
        
        for table_idx, table_elem in enumerate(document_root.findall('.//w:tbl', self.NAMESPACES)):
            rows = []
            
            for row_elem in table_elem.findall('w:tr', self.NAMESPACES):
                row_data = []
                
                for cell_elem in row_elem.findall('w:tc', self.NAMESPACES):
                    cell_text_parts = []
                    
                    for para_elem in cell_elem.findall('.//w:p', self.NAMESPACES):
                        para_data = self._parse_paragraph(para_elem)
                        cell_text_parts.append(para_data.get('text', ''))
                    
                    cell_text = '\n'.join(cell_text_parts)
                    row_data.append(cell_text)
                
                rows.append(row_data)
            
            if rows:
                table_data = TableData(
                    table_id=table_idx,
                    rows=rows,
                    row_count=len(rows),
                    col_count=max(len(row) for row in rows) if rows else 0,
                    has_header=True
                )
                tables.append(table_data)
        
        return tables
    
    def _extract_images(self, zf: zipfile.ZipFile, 
                       document_root: ET.Element) -> List[ImageInfo]:
        """提取图片信息"""
        images = []
        
        try:
            rels_xml = zf.read('word/_rels/document.xml.rels')
            rels_root = ET.fromstring(rels_xml)
            
            relationships = {}
            for rel in rels_root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                rel_id = rel.get('Id', '')
                target = rel.get('Target', '')
                rel_type = rel.get('Type', '')
                relationships[rel_id] = {
                    'target': target,
                    'type': rel_type
                }
            
            for drawing in document_root.findall('.//w:drawing', self.NAMESPACES):
                blip = drawing.find('.//a:blip', self.NAMESPACES)
                if blip is not None:
                    embed_id = blip.get(f'{{{self.NAMESPACES["r"]}}}embed', '')
                    
                    if embed_id in relationships:
                        rel_info = relationships[embed_id]
                        target = rel_info['target']
                        
                        image_filename = target.replace('media/', '')
                        
                        images.append(ImageInfo(
                            image_id=embed_id,
                            filename=image_filename,
                            relationship_id=embed_id,
                            embedded=True
                        ))
                        
        except KeyError:
            pass
        
        return images
    
    def _extract_comments(self, zf: zipfile.ZipFile) -> List[Comment]:
        """提取批注"""
        comments = []
        
        try:
            comments_xml = zf.read('word/comments.xml')
            comments_root = ET.fromstring(comments_xml)
            
            for comment_elem in comments_root.findall('w:comment', self.NAMESPACES):
                comment_id = comment_elem.get(f'{{{self.NAMESPACES["w"]}}}id', '')
                author = comment_elem.get(f'{{{self.NAMESPACES["w"]}}}author', '')
                date = comment_elem.get(f'{{{self.NAMESPACES["w"]}}}date', '')
                
                text_parts = []
                for t_elem in comment_elem.findall('.//w:t', self.NAMESPACES):
                    if t_elem.text:
                        text_parts.append(t_elem.text)
                
                comment_text = ''.join(text_parts)
                
                comments.append(Comment(
                    comment_id=comment_id,
                    author=author,
                    date=date,
                    text=comment_text
                ))
                
        except KeyError:
            pass
        
        return comments
    
    def _extract_revisions(self, document_root: ET.Element) -> List[Revision]:
        """提取修订记录"""
        revisions = []
        
        for del_elem in document_root.findall('.//w:del', self.NAMESPACES):
            rev_id = del_elem.get(f'{{{self.NAMESPACES["w"]}}}id', '')
            author = del_elem.get(f'{{{self.NAMESPACES["w"]}}}author', '')
            date = del_elem.get(f'{{{self.NAMESPACES["w"]}}}date', '')
            
            text_parts = []
            for delText in del_elem.findall('.//w:delText', self.NAMESPACES):
                if delText.text:
                    text_parts.append(delText.text)
            
            revisions.append(Revision(
                revision_id=rev_id,
                revision_type='delete',
                author=author,
                date=date,
                original_text=''.join(text_parts)
            ))
        
        for ins_elem in document_root.findall('.//w:ins', self.NAMESPACES):
            rev_id = ins_elem.get(f'{{{self.NAMESPACES["w"]}}}id', '')
            author = ins_elem.get(f'{{{self.NAMESPACES["w"]}}}author', '')
            date = ins_elem.get(f'{{{self.NAMESPACES["w"]}}}date', '')
            
            text_parts = []
            for t_elem in ins_elem.findall('.//w:t', self.NAMESPACES):
                if t_elem.text:
                    text_parts.append(t_elem.text)
            
            revisions.append(Revision(
                revision_id=rev_id,
                revision_type='insert',
                author=author,
                date=date,
                modified_text=''.join(text_parts)
            ))
        
        return revisions
    
    def extract_text(self, docx_path: str) -> str:
        """
        提取纯文本
        
        Args:
            docx_path: Word文档路径
            
        Returns:
            str: 提取的文本
        """
        result = self.process_document(docx_path)
        return result.text
    
    def extract_tables(self, docx_path: str) -> List[TableData]:
        """
        提取表格
        
        Args:
            docx_path: Word文档路径
            
        Returns:
            list: 表格列表
        """
        result = self.process_document(docx_path)
        return result.content.tables
    
    def extract_images(self, docx_path: str) -> List[ImageInfo]:
        """
        提取图片信息
        
        Args:
            docx_path: Word文档路径
            
        Returns:
            list: 图片信息列表
        """
        result = self.process_document(docx_path)
        return result.content.images
    
    def extract_comments(self, docx_path: str) -> List[Comment]:
        """
        提取批注
        
        Args:
            docx_path: Word文档路径
            
        Returns:
            list: 批注列表
        """
        result = self.process_document(docx_path)
        return result.content.comments
    
    def extract_revisions(self, docx_path: str) -> List[Revision]:
        """
        提取修订记录
        
        Args:
            docx_path: Word文档路径
            
        Returns:
            list: 修订记录列表
        """
        result = self.process_document(docx_path)
        return result.content.revisions
    
    def get_document_structure(self, docx_path: str) -> Dict[str, Any]:
        """
        获取文档结构
        
        Args:
            docx_path: Word文档路径
            
        Returns:
            dict: 文档结构信息
        """
        result = self.process_document(docx_path)
        
        return {
            'paragraph_count': result.paragraph_count,
            'table_count': result.table_count,
            'image_count': result.image_count,
            'char_count': result.char_count,
            'word_count': result.word_count,
            'styles': list(result.content.styles.keys()),
            'has_comments': len(result.content.comments) > 0,
            'has_revisions': len(result.content.revisions) > 0
        }


def create_word_processor_optimized() -> WordProcessorOptimized:
    """
    工厂函数 - 创建优化版Word处理器
    
    Returns:
        WordProcessorOptimized: Word处理器实例
    """
    return WordProcessorOptimized()


if __name__ == "__main__":
    print("Word文档处理器 - 优化版 v2.0.0")
    print("="*60)
    print("\n使用方法:")
    print("```python")
    print("from modules.word_processor_optimized import create_word_processor_optimized")
    print("")
    print("# 创建处理器")
    print("processor = create_word_processor_optimized()")
    print("")
    print("# 处理文档")
    print("result = processor.process_document('document.docx')")
    print("print(f'段落数: {result.paragraph_count}')")
    print("print(f'表格数: {result.table_count}')")
    print("print(f'图片数: {result.image_count}')")
    print("")
    print("# 提取纯文本")
    print("text = processor.extract_text('document.docx')")
    print("")
    print("# 提取表格")
    print("tables = processor.extract_tables('document.docx')")
    print("for table in tables:")
    print("    print(table.to_markdown())")
    print("")
    print("# 提取图片信息")
    print("images = processor.extract_images('document.docx')")
    print("for img in images:")
    print("    print(f'图片: {img.filename}')")
    print("")
    print("# 提取批注")
    print("comments = processor.extract_comments('document.docx')")
    print("")
    print("# 提取修订记录")
    print("revisions = processor.extract_revisions('document.docx')")
    print("```")
