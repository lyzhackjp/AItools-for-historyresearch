"""
文档加载器基类

定义文档加载器的统一接口和基础功能。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.core.types import Document, DocumentType


class BaseLoader(ABC):
    """文档加载器基类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    
    @abstractmethod
    def load(self, source: str) -> List[Document]:
        """
        加载文档
        
        Args:
            source: 文档源（文件路径、URL等）
            
        Returns:
            List[Document]: 加载的文档列表
        """
        pass
    
    @abstractmethod
    def supports(self, source: str) -> bool:
        """
        检查是否支持该文档类型
        
        Args:
            source: 文档源
            
        Returns:
            bool: 是否支持
        """
        pass
    
    def _generate_doc_id(self, content: str, source: str) -> str:
        """生成文档ID"""
        hash_input = f"{source}:{content[:100]}"
        return hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:16]
    
    def _detect_encoding(self, file_path: str) -> str:
        """检测文件编码"""
        try:
            import chardet
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)
                result = chardet.detect(raw_data)
                return result.get('encoding', 'utf-8')
        except ImportError:
            return 'utf-8'
    
    def _read_file(self, file_path: str, encoding: str = None) -> str:
        """读取文件内容"""
        if encoding is None:
            encoding = self._detect_encoding(file_path)
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    
    def _get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取文件元数据"""
        path = Path(file_path)
        stat = path.stat()
        
        return {
            'file_name': path.name,
            'file_extension': path.suffix.lower(),
            'file_size': stat.st_size,
            'created_time': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'parent_directory': str(path.parent)
        }


class LoaderRegistry:
    """文档加载器注册表"""
    
    _loaders: Dict[DocumentType, type] = {}
    
    @classmethod
    def register(cls, doc_type: DocumentType, loader_class: type):
        """注册加载器"""
        cls._loaders[doc_type] = loader_class
    
    @classmethod
    def get_loader(cls, doc_type: DocumentType, config: Dict[str, Any] = None) -> Optional[BaseLoader]:
        """获取加载器实例"""
        loader_class = cls._loaders.get(doc_type)
        if loader_class:
            return loader_class(config)
        return None
    
    @classmethod
    def get_supported_types(cls) -> List[DocumentType]:
        """获取支持的文档类型"""
        return list(cls._loaders.keys())
    
    @classmethod
    def detect_type(cls, source: str) -> DocumentType:
        """检测文档类型"""
        path = Path(source)
        suffix = path.suffix.lower()
        
        type_map = {
            '.pdf': DocumentType.PDF,
            '.md': DocumentType.MARKDOWN,
            '.markdown': DocumentType.MARKDOWN,
            '.txt': DocumentType.TEXT,
            '.html': DocumentType.HTML,
            '.htm': DocumentType.HTML,
            '.docx': DocumentType.DOCX
        }
        
        return type_map.get(suffix, DocumentType.UNKNOWN)


class DocumentLoaderManager:
    """文档加载器管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._loaders: Dict[DocumentType, BaseLoader] = {}
        self._init_loaders()
    
    def _init_loaders(self):
        """初始化加载器"""
        from rag_module.loaders.pdf_loader import PDFLoader
        from rag_module.loaders.markdown_loader import MarkdownLoader
        from rag_module.loaders.text_loader import TextLoader
        
        LoaderRegistry.register(DocumentType.PDF, PDFLoader)
        LoaderRegistry.register(DocumentType.MARKDOWN, MarkdownLoader)
        LoaderRegistry.register(DocumentType.TEXT, TextLoader)
    
    def load(self, source: str) -> List[Document]:
        """
        加载文档（自动检测类型）
        
        Args:
            source: 文档源
            
        Returns:
            List[Document]: 加载的文档列表
        """
        doc_type = LoaderRegistry.detect_type(source)
        
        if doc_type == DocumentType.UNKNOWN:
            raise ValueError(f"不支持的文档类型: {source}")
        
        loader = LoaderRegistry.get_loader(doc_type, self.config)
        if loader is None:
            raise ValueError(f"未找到文档类型 {doc_type} 的加载器")
        
        return loader.load(source)
    
    def load_batch(self, sources: List[str]) -> List[Document]:
        """
        批量加载文档
        
        Args:
            sources: 文档源列表
            
        Returns:
            List[Document]: 加载的文档列表
        """
        all_documents = []
        
        for source in sources:
            try:
                documents = self.load(source)
                all_documents.extend(documents)
            except Exception as e:
                print(f"加载文档失败 {source}: {e}")
        
        return all_documents
    
    def load_directory(self, directory: str, 
                       extensions: List[str] = None,
                       recursive: bool = True) -> List[Document]:
        """
        加载目录中的所有文档
        
        Args:
            directory: 目录路径
            extensions: 文件扩展名过滤
            recursive: 是否递归搜索
            
        Returns:
            List[Document]: 加载的文档列表
        """
        if extensions is None:
            extensions = ['.pdf', '.md', '.txt', '.markdown']
        
        dir_path = Path(directory)
        all_documents = []
        
        if recursive:
            pattern = '**/*'
        else:
            pattern = '*'
        
        for file_path in dir_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                try:
                    documents = self.load(str(file_path))
                    all_documents.extend(documents)
                except Exception as e:
                    print(f"加载文档失败 {file_path}: {e}")
        
        return all_documents
