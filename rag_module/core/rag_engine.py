"""
RAG引擎主模块

提供完整的检索增强生成功能。
"""

from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import time
import json

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module.core.config import RAGConfig
from rag_module.core.types import Document, Chunk, QueryResult, IndexStats
from rag_module.loaders import DocumentLoaderManager
from rag_module.splitters import TextSplitterManager
from rag_module.stores import VectorStoreManager
from rag_module.retrievers import RetrieverManager


class RAGEngine:
    """RAG引擎主类"""
    
    def __init__(self, config: RAGConfig = None):
        """
        初始化RAG引擎
        
        Args:
            config: RAG配置，如果为None则使用默认配置
        """
        self.config = config or RAGConfig.default()
        
        self._loader_manager = None
        self._splitter_manager = None
        self._vector_store = None
        self._retriever_manager = None
        self._embedder = None
        self._llm_client = None
        
        self._document_index: Dict[str, Document] = {}
        self._chunk_index: Dict[str, Chunk] = {}
        
        self._initialize()
    
    def _initialize(self):
        """初始化各组件"""
        self._loader_manager = DocumentLoaderManager()
        
        self._splitter_manager = TextSplitterManager(
            strategy=self.config.chunk_strategy,
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap
        )
        
        self._init_embedder()
        
        self._vector_store = VectorStoreManager(
            store_type=self.config.vector_store,
            store_path=self.config.vector_store_path,
            embedding_dimension=self.config.embedding_dimension
        )
        
        self._retriever_manager = RetrieverManager(
            strategy=self.config.retrieval_strategy,
            vector_store=self._vector_store,
            embedder=self._embedder,
            top_k=self.config.retrieval_top_k,
            threshold=self.config.retrieval_threshold
        )
        
        self._init_llm_client()
    
    def _init_embedder(self):
        """初始化嵌入模型"""
        try:
            from modules.embedding_manager import EmbeddingManager
            self._embedder = EmbeddingManager(default_model=self.config.embedding_model)
            self._embedder.load_embedding_model(self.config.embedding_model)
        except ImportError:
            self._embedder = None
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            from modules.llm_client import LLMClient
            
            provider_map = {
                'qwen': 'dashscope',
                'openai': 'openai',
                'zhipu': 'zhipu',
                'deepseek': 'deepseek',
                'ollama': 'ollama'
            }
            
            provider = provider_map.get(self.config.llm_provider, 'dashscope')
            
            self._llm_client = LLMClient({
                'provider': provider,
                'model': self.config.llm_model
            })
        except ImportError:
            self._llm_client = None
    
    def add_documents(self, 
                     sources: Union[str, List[str]], 
                     metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        添加文档到索引
        
        Args:
            sources: 文档源（文件路径或路径列表）
            metadata: 额外的元数据
            
        Returns:
            dict: 添加结果
        """
        if isinstance(sources, str):
            sources = [sources]
        
        all_documents = []
        
        for source in sources:
            try:
                documents = self._loader_manager.load(source)
                
                if metadata:
                    for doc in documents:
                        doc.metadata.update(metadata)
                
                all_documents.extend(documents)
                
                for doc in documents:
                    self._document_index[doc.id] = doc
                    
            except Exception as e:
                print(f"加载文档失败 {source}: {e}")
        
        if not all_documents:
            return {'success': False, 'error': '没有成功加载任何文档'}
        
        all_chunks = []
        
        for document in all_documents:
            chunks = self._splitter_manager.split(document)
            all_chunks.extend(chunks)
            
            for chunk in chunks:
                self._chunk_index[chunk.id] = chunk
        
        vectors = self._get_embeddings(all_chunks)
        
        if vectors:
            self._vector_store.add_vectors(vectors, all_chunks)
        
        return {
            'success': True,
            'documents_added': len(all_documents),
            'chunks_added': len(all_chunks),
            'total_chunks': len(self._chunk_index)
        }
    
    def add_text(self, 
                text: str, 
                metadata: Dict[str, Any] = None,
                doc_id: str = None) -> Dict[str, Any]:
        """
        添加文本到索引
        
        Args:
            text: 文本内容
            metadata: 元数据
            doc_id: 文档ID
            
        Returns:
            dict: 添加结果
        """
        import hashlib
        
        if doc_id is None:
            doc_id = hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
        
        from rag_module.core.types import DocumentType
        
        document = Document(
            id=doc_id,
            content=text,
            metadata=metadata or {},
            doc_type=DocumentType.TEXT
        )
        
        self._document_index[doc_id] = document
        
        chunks = self._splitter_manager.split(document)
        
        for chunk in chunks:
            self._chunk_index[chunk.id] = chunk
        
        vectors = self._get_embeddings(chunks)
        
        if vectors:
            self._vector_store.add_vectors(vectors, chunks)
        
        return {
            'success': True,
            'document_id': doc_id,
            'chunks_added': len(chunks),
            'total_chunks': len(self._chunk_index)
        }
    
    def query(self, 
             question: str, 
             top_k: int = None,
             include_sources: bool = True) -> QueryResult:
        """
        执行RAG查询
        
        Args:
            question: 查询问题
            top_k: 返回的相关文档数量
            include_sources: 是否包含来源信息
            
        Returns:
            QueryResult: 查询结果
        """
        start_time = time.time()
        
        retrieval_result = self._retriever_manager.retrieve(question, top_k)
        
        retrieval_time = time.time() - start_time
        
        generation_start = time.time()
        
        answer = self._generate_answer(question, retrieval_result.chunks)
        
        generation_time = time.time() - generation_start
        
        total_time = time.time() - start_time
        
        confidence = self._calculate_confidence(retrieval_result.scores)
        
        result = QueryResult(
            query=question,
            answer=answer,
            source_chunks=retrieval_result.chunks if include_sources else [],
            confidence=confidence,
            retrieval_time=retrieval_time,
            generation_time=generation_time,
            total_time=total_time,
            metadata={
                'retrieval_strategy': retrieval_result.retrieval_strategy.value,
                'total_candidates': retrieval_result.total_candidates,
                'top_k_used': len(retrieval_result.chunks)
            }
        )
        
        return result
    
    def retrieve(self, 
                query: str, 
                top_k: int = None) -> List[Chunk]:
        """
        仅执行检索（不生成答案）
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            List[Chunk]: 相关块列表
        """
        result = self._retriever_manager.retrieve(query, top_k)
        return result.chunks
    
    def _get_embeddings(self, chunks: List[Chunk]) -> List[List[float]]:
        """获取块的嵌入向量"""
        vectors = []
        
        for chunk in chunks:
            if self._embedder is not None:
                try:
                    if hasattr(self._embedder, '_get_embedding'):
                        vector = self._embedder._get_embedding(chunk.content)
                        vectors.append(vector.tolist() if hasattr(vector, 'tolist') else vector)
                    elif hasattr(self._embedder, 'encode'):
                        vector = self._embedder.encode(chunk.content)
                        vectors.append(vector.tolist() if hasattr(vector, 'tolist') else vector)
                except Exception:
                    vectors.append(self._mock_embedding(chunk.content))
            else:
                vectors.append(self._mock_embedding(chunk.content))
        
        return vectors
    
    def _mock_embedding(self, text: str) -> List[float]:
        """生成模拟嵌入向量"""
        import hashlib
        import numpy as np
        
        text_hash = hashlib.md5(text.encode('utf-8')).digest()
        seed = int.from_bytes(text_hash[:4], 'big')
        
        np.random.seed(seed)
        vector = np.random.randn(self.config.embedding_dimension)
        vector = vector / np.linalg.norm(vector)
        
        return vector.tolist()
    
    def _generate_answer(self, question: str, chunks: List[Chunk]) -> str:
        """生成答案"""
        if not chunks:
            return "抱歉，我没有找到相关信息来回答您的问题。"
        
        context = "\n\n".join([f"[文档{i+1}]\n{chunk.content}" 
                              for i, chunk in enumerate(chunks)])
        
        prompt = self._build_prompt(question, context)
        
        if self._llm_client is not None:
            try:
                result = self._llm_client._call_llm(prompt)
                if isinstance(result, dict):
                    return result.get('content', result.get('response', str(result)))
                return str(result)
            except Exception as e:
                return f"生成答案时出错: {e}\n\n参考信息:\n{context[:500]}..."
        
        return self._generate_basic_answer(question, chunks)
    
    def _build_prompt(self, question: str, context: str) -> str:
        """构建提示词"""
        return f"""你是一个专业的学术研究助手。请根据以下参考信息回答问题。

参考信息：
{context}

问题：{question}

请提供准确、详细的回答，并在适当的地方引用参考信息。如果参考信息不足以回答问题，请如实说明。"""
    
    def _generate_basic_answer(self, question: str, chunks: List[Chunk]) -> str:
        """生成基础答案（无LLM时）"""
        if not chunks:
            return "没有找到相关信息。"
        
        answer_parts = [f"根据检索到的{len(chunks)}个相关文档片段：\n"]
        
        for i, chunk in enumerate(chunks[:3]):
            source = chunk.metadata.get('file_name', chunk.metadata.get('source_path', '未知来源'))
            answer_parts.append(f"\n[来源{i+1}: {source}]\n{chunk.content[:300]}...")
        
        return "\n".join(answer_parts)
    
    def _calculate_confidence(self, scores: List[float]) -> float:
        """计算置信度"""
        if not scores:
            return 0.0
        
        return sum(scores) / len(scores)
    
    def get_stats(self) -> IndexStats:
        """获取索引统计信息"""
        stats = self._vector_store.get_stats()
        stats.total_documents = len(self._document_index)
        stats.embedding_model = self.config.embedding_model
        return stats
    
    def save_index(self, path: str = None) -> bool:
        """保存索引"""
        save_path = path or self.config.vector_store_path
        
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        
        vector_saved = self._vector_store.save(f"{save_path}/vectors")
        
        doc_data = {doc_id: doc.to_dict() for doc_id, doc in self._document_index.items()}
        with open(f"{save_path}/documents.json", 'w', encoding='utf-8') as f:
            json.dump(doc_data, f, ensure_ascii=False, indent=2)
        
        chunk_data = {chunk_id: chunk.to_dict() for chunk_id, chunk in self._chunk_index.items()}
        with open(f"{save_path}/chunks.json", 'w', encoding='utf-8') as f:
            json.dump(chunk_data, f, ensure_ascii=False, indent=2)
        
        config_data = self.config.to_dict()
        with open(f"{save_path}/config.json", 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        return vector_saved
    
    def load_index(self, path: str = None) -> bool:
        """加载索引"""
        load_path = path or self.config.vector_store_path
        
        vector_loaded = self._vector_store.load(f"{load_path}/vectors")
        
        doc_path = f"{load_path}/documents.json"
        if Path(doc_path).exists():
            with open(doc_path, 'r', encoding='utf-8') as f:
                doc_data = json.load(f)
            self._document_index = {doc_id: Document.from_dict(doc) for doc_id, doc in doc_data.items()}
        
        chunk_path = f"{load_path}/chunks.json"
        if Path(chunk_path).exists():
            with open(chunk_path, 'r', encoding='utf-8') as f:
                chunk_data = json.load(f)
            self._chunk_index = {chunk_id: Chunk.from_dict(chunk) for chunk_id, chunk in chunk_data.items()}
        
        return vector_loaded
    
    def clear_index(self) -> bool:
        """清空索引"""
        self._document_index = {}
        self._chunk_index = {}
        return self._vector_store.clear()
    
    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """删除文档"""
        if doc_id not in self._document_index:
            return {'success': False, 'error': '文档不存在'}
        
        chunks_to_delete = [
            chunk.id for chunk in self._chunk_index.values()
            if chunk.document_id == doc_id
        ]
        
        if chunks_to_delete:
            self._vector_store.delete(chunks_to_delete)
        
        for chunk_id in chunks_to_delete:
            del self._chunk_index[chunk_id]
        
        del self._document_index[doc_id]
        
        return {
            'success': True,
            'deleted_chunks': len(chunks_to_delete),
            'remaining_documents': len(self._document_index)
        }
    
    def update_config(self, **kwargs) -> None:
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        if 'retrieval_top_k' in kwargs or 'retrieval_threshold' in kwargs:
            self._retriever_manager.set_top_k(self.config.retrieval_top_k)
            self._retriever_manager.set_threshold(self.config.retrieval_threshold)
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取文档"""
        return self._document_index.get(doc_id)
    
    def get_chunk(self, chunk_id: str) -> Optional[Chunk]:
        """获取块"""
        return self._chunk_index.get(chunk_id)
    
    def list_documents(self) -> List[str]:
        """列出所有文档ID"""
        return list(self._document_index.keys())
    
    def list_chunks(self, doc_id: str = None) -> List[str]:
        """列出所有块ID"""
        if doc_id:
            return [chunk.id for chunk in self._chunk_index.values() 
                   if chunk.document_id == doc_id]
        return list(self._chunk_index.keys())
