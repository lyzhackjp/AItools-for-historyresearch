"""
RAG适配器基类

定义统一的RAG接口规范，所有RAG后端实现都需要继承此类。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class RAGBackend(Enum):
    """RAG后端类型"""
    BUILT_IN = 'built_in'
    DIFY = 'dify'
    RAGFLOW = 'ragflow'


@dataclass
class RAGDocument:
    """统一文档格式"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None


@dataclass
class RAGQueryResult:
    """统一查询结果格式"""
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None


@dataclass
class RAGResponse:
    """统一响应格式"""
    answer: str
    sources: List[RAGQueryResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGIndexStats:
    """索引统计信息"""
    total_documents: int = 0
    total_chunks: int = 0
    index_size_mb: float = 0.0
    backend_type: str = ''


class BaseRAGAdapter(ABC):
    """RAG适配器抽象基类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化适配器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self._is_initialized = False
    
    @property
    @abstractmethod
    def backend_type(self) -> RAGBackend:
        """返回后端类型"""
        pass
    
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._is_initialized
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        初始化RAG后端
        
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        检查后端健康状态
        
        Returns:
            Dict包含status和message
        """
        pass
    
    @abstractmethod
    def load_document(self, 
                      file_path: str, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        加载文档到索引
        
        Args:
            file_path: 文档路径
            metadata: 文档元数据
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def load_documents(self,
                       file_paths: List[str],
                       metadata_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, bool]:
        """
        批量加载文档
        
        Args:
            file_paths: 文档路径列表
            metadata_list: 元数据列表
            
        Returns:
            Dict[str, bool]: 文件路径到成功状态的映射
        """
        pass
    
    @abstractmethod
    def retrieve(self,
                 query: str,
                 top_k: int = 5,
                 threshold: float = 0.0,
                 filters: Optional[Dict[str, Any]] = None) -> List[RAGQueryResult]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            threshold: 相似度阈值
            filters: 过滤条件
            
        Returns:
            List[RAGQueryResult]: 检索结果列表
        """
        pass
    
    @abstractmethod
    def query(self,
              question: str,
              top_k: int = 5,
              include_sources: bool = True) -> RAGResponse:
        """
        执行RAG查询（检索+生成）
        
        Args:
            question: 问题文本
            top_k: 检索文档数量
            include_sources: 是否包含来源信息
            
        Returns:
            RAGResponse: 包含答案和来源的响应
        """
        pass
    
    @abstractmethod
    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def clear_index(self) -> bool:
        """
        清空索引
        
        Returns:
            bool: 是否成功
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> RAGIndexStats:
        """
        获取索引统计信息
        
        Returns:
            RAGIndexStats: 统计信息
        """
        pass
    
    def __enter__(self):
        """上下文管理器入口"""
        if not self._is_initialized:
            self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        pass
