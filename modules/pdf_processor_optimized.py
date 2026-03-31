"""
PDF处理器模块 - 优化版

高效的PDF文档处理工具

优化内容 (v2.0.0):
- 添加分块处理：大文件分块读取，降低内存占用
- 优化内存使用：流式读取、及时释放资源
- 支持流式处理：支持迭代器模式处理大文件
- 添加进度回调：支持处理进度监控

核心功能：
- 分块读取：大PDF文件分块处理
- 内存优化：流式处理降低内存占用
- 元数据提取：提取PDF元数据信息
- 文本提取：高质量文本提取
- 表格提取：支持表格内容提取

支持的PDF解析引擎：
- PyMuPDF (fitz)
- pdfplumber
- PyPDF2
"""

import os
import re
import gc
from pathlib import Path
from typing import Dict, List, Optional, Any, Iterator, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging


class PDFEngine(Enum):
    """PDF解析引擎枚举"""
    PYMUPDF = 'pymupdf'
    PDFPLUMBER = 'pdfplumber'
    PYPDF2 = 'pypdf2'


@dataclass
class PDFMetadata:
    """PDF元数据"""
    title: str = ""
    author: str = ""
    subject: str = ""
    creator: str = ""
    producer: str = ""
    creation_date: str = ""
    modification_date: str = ""
    page_count: int = 0
    file_size: int = 0
    encrypted: bool = False


@dataclass
class PDFChunk:
    """PDF分块数据"""
    chunk_id: int
    page_start: int
    page_end: int
    text: str
    char_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PDFProcessingResult:
    """PDF处理结果"""
    success: bool
    text: str
    metadata: PDFMetadata
    page_count: int
    char_count: int
    word_count: int
    processing_time: float
    chunks_processed: int = 0
    errors: List[str] = field(default_factory=list)


class MemoryManager:
    """内存管理器"""
    
    def __init__(self, max_memory_mb: int = 512):
        """
        初始化内存管理器
        
        Args:
            max_memory_mb: 最大内存使用量(MB)
        """
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.current_usage = 0
        self.logger = logging.getLogger('MemoryManager')
    
    def check_memory(self) -> bool:
        """检查内存是否超限"""
        return self.current_usage < self.max_memory_bytes
    
    def add_usage(self, size: int):
        """增加内存使用记录"""
        self.current_usage += size
    
    def release(self, size: int = None):
        """释放内存"""
        if size:
            self.current_usage = max(0, self.current_usage - size)
        else:
            self.current_usage = 0
        gc.collect()
    
    def get_usage_mb(self) -> float:
        """获取当前内存使用量(MB)"""
        return self.current_usage / (1024 * 1024)


class PDFProcessorOptimized:
    """PDF处理器 - 优化版"""
    
    DEFAULT_CHUNK_SIZE = 50
    DEFAULT_MAX_MEMORY_MB = 512
    
    def __init__(self, engine: str = 'pymupdf',
                 chunk_size: int = None,
                 max_memory_mb: int = None):
        """
        初始化PDF处理器
        
        Args:
            engine: PDF解析引擎
            chunk_size: 分块大小（页数）
            max_memory_mb: 最大内存使用量(MB)
        """
        self.engine = PDFEngine(engine) if engine in [e.value for e in PDFEngine] else PDFEngine.PYMUPDF
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        self.memory_manager = MemoryManager(max_memory_mb or self.DEFAULT_MAX_MEMORY_MB)
        self.logger = logging.getLogger('PDFProcessorOptimized')
        
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def extract_metadata(self, pdf_path: str) -> PDFMetadata:
        """
        提取PDF元数据
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            PDFMetadata: 元数据对象
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        file_size = pdf_path.stat().st_size
        
        if self.engine == PDFEngine.PYMUPDF:
            return self._extract_metadata_pymupdf(str(pdf_path), file_size)
        elif self.engine == PDFEngine.PDFPLUMBER:
            return self._extract_metadata_pdfplumber(str(pdf_path), file_size)
        else:
            return self._extract_metadata_pypdf2(str(pdf_path), file_size)
    
    def _extract_metadata_pymupdf(self, pdf_path: str, file_size: int) -> PDFMetadata:
        """使用PyMuPDF提取元数据"""
        try:
            import fitz
            
            doc = fitz.open(pdf_path)
            meta = doc.metadata
            
            metadata = PDFMetadata(
                title=meta.get('title', ''),
                author=meta.get('author', ''),
                subject=meta.get('subject', ''),
                creator=meta.get('creator', ''),
                producer=meta.get('producer', ''),
                creation_date=meta.get('creationDate', ''),
                modification_date=meta.get('modDate', ''),
                page_count=doc.page_count,
                file_size=file_size,
                encrypted=doc.is_encrypted
            )
            
            doc.close()
            return metadata
            
        except ImportError:
            self.logger.warning("PyMuPDF未安装，尝试使用其他引擎")
            return self._extract_metadata_pypdf2(pdf_path, file_size)
    
    def _extract_metadata_pdfplumber(self, pdf_path: str, file_size: int) -> PDFMetadata:
        """使用pdfplumber提取元数据"""
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                meta = pdf.metadata or {}
                
                return PDFMetadata(
                    title=meta.get('Title', ''),
                    author=meta.get('Author', ''),
                    subject=meta.get('Subject', ''),
                    creator=meta.get('Creator', ''),
                    producer=meta.get('Producer', ''),
                    creation_date=meta.get('CreationDate', ''),
                    modification_date=meta.get('ModDate', ''),
                    page_count=len(pdf.pages),
                    file_size=file_size,
                    encrypted=False
                )
                
        except ImportError:
            self.logger.warning("pdfplumber未安装，尝试使用其他引擎")
            return self._extract_metadata_pypdf2(pdf_path, file_size)
    
    def _extract_metadata_pypdf2(self, pdf_path: str, file_size: int) -> PDFMetadata:
        """使用PyPDF2提取元数据"""
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(pdf_path)
            meta = reader.metadata or {}
            
            return PDFMetadata(
                title=meta.get('/Title', ''),
                author=meta.get('/Author', ''),
                subject=meta.get('/Subject', ''),
                creator=meta.get('/Creator', ''),
                producer=meta.get('/Producer', ''),
                creation_date=meta.get('/CreationDate', ''),
                modification_date=meta.get('/ModDate', ''),
                page_count=len(reader.pages),
                file_size=file_size,
                encrypted=reader.is_encrypted
            )
            
        except ImportError:
            raise ImportError("请安装PyPDF2: pip install PyPDF2")
    
    def extract_text_streaming(self, pdf_path: str,
                               progress_callback: Optional[Callable[[int, int], None]] = None
                               ) -> Iterator[PDFChunk]:
        """
        流式提取PDF文本（生成器模式）
        
        Args:
            pdf_path: PDF文件路径
            progress_callback: 进度回调函数
            
        Yields:
            PDFChunk: 文本分块
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        if self.engine == PDFEngine.PYMUPDF:
            yield from self._extract_text_streaming_pymupdf(str(pdf_path), progress_callback)
        elif self.engine == PDFEngine.PDFPLUMBER:
            yield from self._extract_text_streaming_pdfplumber(str(pdf_path), progress_callback)
        else:
            yield from self._extract_text_streaming_pypdf2(str(pdf_path), progress_callback)
    
    def _extract_text_streaming_pymupdf(self, pdf_path: str,
                                        progress_callback: Optional[Callable]
                                        ) -> Iterator[PDFChunk]:
        """使用PyMuPDF流式提取"""
        try:
            import fitz
            
            doc = fitz.open(pdf_path)
            total_pages = doc.page_count
            
            chunk_id = 0
            for start_page in range(0, total_pages, self.chunk_size):
                end_page = min(start_page + self.chunk_size, total_pages)
                
                chunk_text = []
                for page_num in range(start_page, end_page):
                    page = doc[page_num]
                    chunk_text.append(page.get_text())
                    
                    if progress_callback:
                        progress_callback(page_num + 1, total_pages)
                
                text = '\n'.join(chunk_text)
                
                yield PDFChunk(
                    chunk_id=chunk_id,
                    page_start=start_page,
                    page_end=end_page - 1,
                    text=text,
                    char_count=len(text)
                )
                
                chunk_id += 1
                self.memory_manager.release()
            
            doc.close()
            
        except ImportError:
            yield from self._extract_text_streaming_pypdf2(pdf_path, progress_callback)
    
    def _extract_text_streaming_pdfplumber(self, pdf_path: str,
                                           progress_callback: Optional[Callable]
                                           ) -> Iterator[PDFChunk]:
        """使用pdfplumber流式提取"""
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                chunk_id = 0
                for start_page in range(0, total_pages, self.chunk_size):
                    end_page = min(start_page + self.chunk_size, total_pages)
                    
                    chunk_text = []
                    for page_num in range(start_page, end_page):
                        page = pdf.pages[page_num]
                        chunk_text.append(page.extract_text() or '')
                        
                        if progress_callback:
                            progress_callback(page_num + 1, total_pages)
                    
                    text = '\n'.join(chunk_text)
                    
                    yield PDFChunk(
                        chunk_id=chunk_id,
                        page_start=start_page,
                        page_end=end_page - 1,
                        text=text,
                        char_count=len(text)
                    )
                    
                    chunk_id += 1
                    self.memory_manager.release()
                    
        except ImportError:
            yield from self._extract_text_streaming_pypdf2(pdf_path, progress_callback)
    
    def _extract_text_streaming_pypdf2(self, pdf_path: str,
                                       progress_callback: Optional[Callable]
                                       ) -> Iterator[PDFChunk]:
        """使用PyPDF2流式提取"""
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            
            chunk_id = 0
            for start_page in range(0, total_pages, self.chunk_size):
                end_page = min(start_page + self.chunk_size, total_pages)
                
                chunk_text = []
                for page_num in range(start_page, end_page):
                    page = reader.pages[page_num]
                    chunk_text.append(page.extract_text() or '')
                    
                    if progress_callback:
                        progress_callback(page_num + 1, total_pages)
                
                text = '\n'.join(chunk_text)
                
                yield PDFChunk(
                    chunk_id=chunk_id,
                    page_start=start_page,
                    page_end=end_page - 1,
                    text=text,
                    char_count=len(text)
                )
                
                chunk_id += 1
                self.memory_manager.release()
                
        except ImportError:
            raise ImportError("请安装PyPDF2: pip install PyPDF2")
    
    def extract_text(self, pdf_path: str,
                    progress_callback: Optional[Callable[[int, int], None]] = None
                    ) -> PDFProcessingResult:
        """
        提取PDF全部文本
        
        Args:
            pdf_path: PDF文件路径
            progress_callback: 进度回调函数
            
        Returns:
            PDFProcessingResult: 处理结果
        """
        import time
        start_time = time.time()
        
        try:
            metadata = self.extract_metadata(pdf_path)
            
            all_text = []
            chunks_processed = 0
            
            for chunk in self.extract_text_streaming(pdf_path, progress_callback):
                all_text.append(chunk.text)
                chunks_processed += 1
            
            full_text = '\n'.join(all_text)
            
            processing_time = time.time() - start_time
            
            return PDFProcessingResult(
                success=True,
                text=full_text,
                metadata=metadata,
                page_count=metadata.page_count,
                char_count=len(full_text),
                word_count=len(full_text.split()),
                processing_time=processing_time,
                chunks_processed=chunks_processed
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"PDF处理失败: {e}")
            
            return PDFProcessingResult(
                success=False,
                text='',
                metadata=PDFMetadata(),
                page_count=0,
                char_count=0,
                word_count=0,
                processing_time=processing_time,
                errors=[str(e)]
            )
    
    def extract_page_text(self, pdf_path: str, page_num: int) -> str:
        """
        提取指定页面的文本
        
        Args:
            pdf_path: PDF文件路径
            page_num: 页码（从0开始）
            
        Returns:
            str: 页面文本
        """
        if self.engine == PDFEngine.PYMUPDF:
            return self._extract_page_pymupdf(pdf_path, page_num)
        elif self.engine == PDFEngine.PDFPLUMBER:
            return self._extract_page_pdfplumber(pdf_path, page_num)
        else:
            return self._extract_page_pypdf2(pdf_path, page_num)
    
    def _extract_page_pymupdf(self, pdf_path: str, page_num: int) -> str:
        """使用PyMuPDF提取单页"""
        try:
            import fitz
            
            doc = fitz.open(pdf_path)
            if 0 <= page_num < doc.page_count:
                page = doc[page_num]
                text = page.get_text()
                doc.close()
                return text
            doc.close()
            return ''
            
        except ImportError:
            return self._extract_page_pypdf2(pdf_path, page_num)
    
    def _extract_page_pdfplumber(self, pdf_path: str, page_num: int) -> str:
        """使用pdfplumber提取单页"""
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                if 0 <= page_num < len(pdf.pages):
                    return pdf.pages[page_num].extract_text() or ''
                return ''
                
        except ImportError:
            return self._extract_page_pypdf2(pdf_path, page_num)
    
    def _extract_page_pypdf2(self, pdf_path: str, page_num: int) -> str:
        """使用PyPDF2提取单页"""
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(pdf_path)
            if 0 <= page_num < len(reader.pages):
                return reader.pages[page_num].extract_text() or ''
            return ''
            
        except ImportError:
            raise ImportError("请安装PyPDF2: pip install PyPDF2")
    
    def extract_tables(self, pdf_path: str,
                      pages: Optional[List[int]] = None) -> List[List[List[str]]]:
        """
        提取PDF中的表格
        
        Args:
            pdf_path: PDF文件路径
            pages: 要提取的页码列表（None表示全部）
            
        Returns:
            list: 表格列表
        """
        try:
            import pdfplumber
            
            tables = []
            
            with pdfplumber.open(pdf_path) as pdf:
                page_indices = pages if pages else range(len(pdf.pages))
                
                for page_num in page_indices:
                    if 0 <= page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        page_tables = page.extract_tables()
                        tables.extend(page_tables)
            
            return tables
            
        except ImportError:
            self.logger.warning("pdfplumber未安装，表格提取功能不可用")
            return []
    
    def get_page_count(self, pdf_path: str) -> int:
        """
        获取PDF页数
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            int: 页数
        """
        metadata = self.extract_metadata(pdf_path)
        return metadata.page_count
    
    def is_encrypted(self, pdf_path: str) -> bool:
        """
        检查PDF是否加密
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            bool: 是否加密
        """
        metadata = self.extract_metadata(pdf_path)
        return metadata.encrypted
    
    def set_chunk_size(self, size: int):
        """设置分块大小"""
        self.chunk_size = size
    
    def set_max_memory(self, max_memory_mb: int):
        """设置最大内存使用量"""
        self.memory_manager = MemoryManager(max_memory_mb)
    
    def get_memory_usage(self) -> float:
        """获取当前内存使用量(MB)"""
        return self.memory_manager.get_usage_mb()


def create_pdf_processor_optimized(engine: str = 'pymupdf',
                                   chunk_size: int = None,
                                   max_memory_mb: int = None) -> PDFProcessorOptimized:
    """
    工厂函数 - 创建优化版PDF处理器
    
    Args:
        engine: PDF解析引擎
        chunk_size: 分块大小
        max_memory_mb: 最大内存使用量
        
    Returns:
        PDFProcessorOptimized: PDF处理器实例
    """
    return PDFProcessorOptimized(engine, chunk_size, max_memory_mb)


if __name__ == "__main__":
    print("PDF处理器 - 优化版 v2.0.0")
    print("="*60)
    print("\n支持的引擎: pymupdf, pdfplumber, pypdf2")
    print("\n使用方法:")
    print("```python")
    print("from modules.pdf_processor_optimized import create_pdf_processor_optimized")
    print("")
    print("# 创建处理器")
    print("processor = create_pdf_processor_optimized(")
    print("    engine='pymupdf',")
    print("    chunk_size=50,")
    print("    max_memory_mb=512")
    print(")")
    print("")
    print("# 提取元数据")
    print("metadata = processor.extract_metadata('document.pdf')")
    print("print(f'页数: {metadata.page_count}')")
    print("")
    print("# 流式提取文本")
    print("for chunk in processor.extract_text_streaming('document.pdf'):")
    print("    print(f'处理分块 {chunk.chunk_id}: {chunk.char_count} 字符')")
    print("")
    print("# 提取全部文本")
    print("result = processor.extract_text('document.pdf')")
    print("print(f'总字符数: {result.char_count}')")
    print("")
    print("# 提取表格")
    print("tables = processor.extract_tables('document.pdf')")
    print("```")
