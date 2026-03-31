"""
文档加载器模块

提供多种文档格式的加载能力。
"""

from .base_loader import BaseLoader, LoaderRegistry, DocumentLoaderManager
from .pdf_loader import PDFLoader
from .markdown_loader import MarkdownLoader
from .text_loader import TextLoader

__all__ = [
    'BaseLoader',
    'LoaderRegistry',
    'DocumentLoaderManager',
    'PDFLoader',
    'MarkdownLoader',
    'TextLoader'
]
