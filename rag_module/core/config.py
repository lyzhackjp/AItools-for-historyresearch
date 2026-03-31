"""
RAG模块配置管理

定义RAG引擎的配置参数和默认值。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from .types import ChunkStrategy, VectorStoreType, RetrievalStrategy


@dataclass
class RAGConfig:
    """RAG引擎配置"""
    
    embedding_model: str = 'bge-m3'
    embedding_dimension: int = 1024
    
    vector_store: VectorStoreType = VectorStoreType.CHROMA
    vector_store_path: str = './data/rag_vectors'
    
    chunk_strategy: ChunkStrategy = ChunkStrategy.RECURSIVE
    chunk_size: int = 512
    chunk_overlap: int = 50
    
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.VECTOR
    retrieval_top_k: int = 5
    retrieval_threshold: float = 0.0
    
    llm_provider: str = 'qwen'
    llm_model: str = 'qwen-turbo'
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    
    enable_cache: bool = True
    cache_ttl: int = 3600
    
    enable_reranking: bool = False
    rerank_top_n: int = 3
    
    max_workers: int = 4
    batch_size: int = 32
    
    enable_logging: bool = True
    log_level: str = 'INFO'
    
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.vector_store, str):
            self.vector_store = VectorStoreType(self.vector_store)
        if isinstance(self.chunk_strategy, str):
            self.chunk_strategy = ChunkStrategy(self.chunk_strategy)
        if isinstance(self.retrieval_strategy, str):
            self.retrieval_strategy = RetrievalStrategy(self.retrieval_strategy)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'embedding_model': self.embedding_model,
            'embedding_dimension': self.embedding_dimension,
            'vector_store': self.vector_store.value,
            'vector_store_path': self.vector_store_path,
            'chunk_strategy': self.chunk_strategy.value,
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
            'retrieval_strategy': self.retrieval_strategy.value,
            'retrieval_top_k': self.retrieval_top_k,
            'retrieval_threshold': self.retrieval_threshold,
            'llm_provider': self.llm_provider,
            'llm_model': self.llm_model,
            'llm_temperature': self.llm_temperature,
            'llm_max_tokens': self.llm_max_tokens,
            'enable_cache': self.enable_cache,
            'cache_ttl': self.cache_ttl,
            'enable_reranking': self.enable_reranking,
            'rerank_top_n': self.rerank_top_n,
            'max_workers': self.max_workers,
            'batch_size': self.batch_size,
            'enable_logging': self.enable_logging,
            'log_level': self.log_level,
            'custom_settings': self.custom_settings
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RAGConfig':
        return cls(
            embedding_model=data.get('embedding_model', 'bge-m3'),
            embedding_dimension=data.get('embedding_dimension', 1024),
            vector_store=VectorStoreType(data.get('vector_store', 'chroma')),
            vector_store_path=data.get('vector_store_path', './data/rag_vectors'),
            chunk_strategy=ChunkStrategy(data.get('chunk_strategy', 'recursive')),
            chunk_size=data.get('chunk_size', 512),
            chunk_overlap=data.get('chunk_overlap', 50),
            retrieval_strategy=RetrievalStrategy(data.get('retrieval_strategy', 'vector')),
            retrieval_top_k=data.get('retrieval_top_k', 5),
            retrieval_threshold=data.get('retrieval_threshold', 0.0),
            llm_provider=data.get('llm_provider', 'qwen'),
            llm_model=data.get('llm_model', 'qwen-turbo'),
            llm_temperature=data.get('llm_temperature', 0.7),
            llm_max_tokens=data.get('llm_max_tokens', 2048),
            enable_cache=data.get('enable_cache', True),
            cache_ttl=data.get('cache_ttl', 3600),
            enable_reranking=data.get('enable_reranking', False),
            rerank_top_n=data.get('rerank_top_n', 3),
            max_workers=data.get('max_workers', 4),
            batch_size=data.get('batch_size', 32),
            enable_logging=data.get('enable_logging', True),
            log_level=data.get('log_level', 'INFO'),
            custom_settings=data.get('custom_settings', {})
        )
    
    @classmethod
    def default(cls) -> 'RAGConfig':
        return cls()
    
    @classmethod
    def for_japanese_history(cls) -> 'RAGConfig':
        return cls(
            embedding_model='bge-m3',
            chunk_size=768,
            chunk_overlap=100,
            retrieval_top_k=7,
            llm_provider='qwen',
            llm_model='qwen-turbo',
            enable_reranking=True
        )
    
    @classmethod
    def for_academic_papers(cls) -> 'RAGConfig':
        return cls(
            embedding_model='bge-m3',
            chunk_size=1024,
            chunk_overlap=150,
            retrieval_top_k=10,
            llm_provider='qwen',
            llm_model='qwen-max',
            enable_reranking=True,
            rerank_top_n=5
        )
    
    @classmethod
    def lightweight(cls) -> 'RAGConfig':
        return cls(
            embedding_model='bge-m3',
            vector_store=VectorStoreType.MEMORY,
            chunk_size=256,
            chunk_overlap=30,
            retrieval_top_k=3,
            enable_cache=False,
            enable_reranking=False
        )


@dataclass
class LoaderConfig:
    """文档加载器配置"""
    
    extract_images: bool = False
    extract_tables: bool = True
    preserve_formatting: bool = True
    encoding: str = 'utf-8'
    
    pdf_use_ocr: bool = False
    pdf_ocr_language: str = 'jpn+eng'
    
    markdown_extract_links: bool = True
    markdown_extract_code_blocks: bool = True
    
    custom_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SplitterConfig:
    """文本分块器配置"""
    
    chunk_size: int = 512
    chunk_overlap: int = 50
    
    separators: List[str] = field(default_factory=lambda: ['\n\n', '\n', '。', '！', '？', '.', '!', '?', ' ', ''])
    
    length_function: str = 'token'
    
    keep_separator: bool = True
    strip_whitespace: bool = True
    
    semantic_min_chunk_size: int = 100
    semantic_similarity_threshold: float = 0.7
    
    custom_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrieverConfig:
    """检索器配置"""
    
    top_k: int = 5
    threshold: float = 0.0
    
    hybrid_alpha: float = 0.5
    
    rerank_enabled: bool = False
    rerank_model: str = 'bge-reranker'
    rerank_top_n: int = 3
    
    filter_metadata: Dict[str, Any] = field(default_factory=dict)
    
    custom_settings: Dict[str, Any] = field(default_factory=dict)
