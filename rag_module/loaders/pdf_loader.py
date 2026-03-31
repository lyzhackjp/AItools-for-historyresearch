"""
PDF文档加载器

支持PDF文档的加载和解析。
"""

from typing import List, Dict, Any, Optional
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.loaders.base_loader import BaseLoader, LoaderRegistry
from rag_module.core.types import Document, DocumentType


class PDFLoader(BaseLoader):
    """PDF文档加载器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.use_ocr = self.config.get('pdf_use_ocr', False)
        self.ocr_language = self.config.get('pdf_ocr_language', 'jpn+eng')
        self.extract_images = self.config.get('extract_images', False)
        self.extract_tables = self.config.get('extract_tables', True)
    
    def load(self, source: str) -> List[Document]:
        """
        加载PDF文档
        
        Args:
            source: PDF文件路径
            
        Returns:
            List[Document]: 加载的文档列表
        """
        if not self.supports(source):
            raise ValueError(f"不支持的文件类型: {source}")
        
        documents = []
        
        try:
            import fitz
            documents = self._load_with_pymupdf(source)
        except ImportError:
            try:
                import pdfplumber
                documents = self._load_with_pdfplumber(source)
            except ImportError:
                documents = self._load_with_basic(source)
        
        return documents
    
    def supports(self, source: str) -> bool:
        """检查是否支持PDF格式"""
        return Path(source).suffix.lower() == '.pdf'
    
    def _load_with_pymupdf(self, source: str) -> List[Document]:
        """使用PyMuPDF加载PDF"""
        import fitz
        
        documents = []
        doc = fitz.open(source)
        
        file_metadata = self._get_file_metadata(source)
        
        for page_num, page in enumerate(doc):
            text = page.get_text()
            
            if not text.strip() and self.use_ocr:
                text = self._ocr_page(page)
            
            tables = []
            if self.extract_tables:
                tables = self._extract_tables_pymupdf(page)
            
            images = []
            if self.extract_images:
                images = self._extract_images_pymupdf(page)
            
            metadata = {
                **file_metadata,
                'page_number': page_num + 1,
                'total_pages': len(doc),
                'tables': tables,
                'images': images,
                'loader': 'pymupdf'
            }
            
            doc_id = self._generate_doc_id(text, f"{source}:{page_num}")
            
            document = Document(
                id=doc_id,
                content=text,
                metadata=metadata,
                doc_type=DocumentType.PDF,
                source_path=source
            )
            
            documents.append(document)
        
        doc.close()
        return documents
    
    def _load_with_pdfplumber(self, source: str) -> List[Document]:
        """使用pdfplumber加载PDF"""
        import pdfplumber
        
        documents = []
        file_metadata = self._get_file_metadata(source)
        
        with pdfplumber.open(source) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text() or ''
                
                tables = []
                if self.extract_tables:
                    tables = page.extract_tables() or []
                
                metadata = {
                    **file_metadata,
                    'page_number': page_num + 1,
                    'total_pages': len(pdf.pages),
                    'tables': tables,
                    'loader': 'pdfplumber'
                }
                
                doc_id = self._generate_doc_id(text, f"{source}:{page_num}")
                
                document = Document(
                    id=doc_id,
                    content=text,
                    metadata=metadata,
                    doc_type=DocumentType.PDF,
                    source_path=source
                )
                
                documents.append(document)
        
        return documents
    
    def _load_with_basic(self, source: str) -> List[Document]:
        """基础PDF加载方法"""
        try:
            import fitz
            return self._load_with_pymupdf(source)
        except ImportError:
            pass
        
        file_metadata = self._get_file_metadata(source)
        
        return [Document(
            id=self._generate_doc_id('', source),
            content='[PDF内容需要安装PyMuPDF或pdfplumber库才能提取]',
            metadata={**file_metadata, 'loader': 'basic'},
            doc_type=DocumentType.PDF,
            source_path=source
        )]
    
    def _ocr_page(self, page) -> str:
        """对页面进行OCR"""
        try:
            import pytesseract
            from PIL import Image
            
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang=self.ocr_language)
            return text
        except ImportError:
            return ""
    
    def _extract_tables_pymupdf(self, page) -> List[Dict[str, Any]]:
        """提取表格"""
        tables = []
        try:
            import fitz
            
            for table in page.find_tables():
                table_data = table.extract()
                tables.append({
                    'bbox': table.bbox,
                    'row_count': len(table_data),
                    'col_count': len(table_data[0]) if table_data else 0,
                    'data': table_data
                })
        except Exception:
            pass
        
        return tables
    
    def _extract_images_pymupdf(self, page) -> List[Dict[str, Any]]:
        """提取图片信息"""
        images = []
        try:
            import fitz
            
            for img_index, img in enumerate(page.get_images()):
                xref = img[0]
                base_image = page.parent.extract_image(xref)
                
                images.append({
                    'index': img_index,
                    'width': base_image['width'],
                    'height': base_image['height'],
                    'colorspace': base_image.get('colorspace', 0),
                    'xref': xref
                })
        except Exception:
            pass
        
        return images


LoaderRegistry.register(DocumentType.PDF, PDFLoader)
