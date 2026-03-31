"""
Ragflow RAG适配器

封装Ragflow平台的RAG功能，提供统一接口。
"""

from typing import List, Dict, Any, Optional
import os

from rag_module.adapters.base_adapter import (
    BaseRAGAdapter, RAGBackend,
    RAGQueryResult, RAGResponse, RAGIndexStats
)


class RagflowRAGAdapter(BaseRAGAdapter):
    """Ragflow RAG适配器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._api_key = config.get('api_key', '') if config else ''
        self._base_url = config.get('base_url', 'http://localhost') if config else 'http://localhost'
        self._dataset_name = config.get('dataset_name', 'default') if config else 'default'
        self._client = None
        self._dataset = None
    
    @property
    def backend_type(self) -> RAGBackend:
        return RAGBackend.RAGFLOW
    
    def _check_ragflow_available(self) -> bool:
        """检查Ragflow是否可用"""
        ragflow_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'external', 'ragflow'
        )
        return os.path.exists(ragflow_path)
    
    def initialize(self) -> bool:
        """初始化Ragflow连接"""
        if not self._check_ragflow_available():
            print("Ragflow未安装在external目录中")
            return False
        
        if not self._api_key:
            print("未配置Ragflow API密钥")
            return False
        
        try:
            from ragflow_sdk import RAGFlow
            
            self._client = RAGFlow(
                api_key=self._api_key,
                base_url=self._base_url
            )
            
            try:
                self._dataset = self._client.get_dataset(self._dataset_name)
            except Exception:
                self._dataset = self._client.create_dataset(
                    name=self._dataset_name,
                    description='RAG Adapter Dataset'
                )
            
            self._is_initialized = True
            return True
        except ImportError:
            print("Ragflow SDK未安装")
            return False
        except Exception as e:
            print(f"初始化Ragflow连接失败: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """检查Ragflow健康状态"""
        if not self._is_initialized:
            return {'status': 'error', 'message': 'Ragflow未初始化'}
        
        try:
            datasets = self._client.list_datasets(page_size=1)
            return {'status': 'healthy', 'message': 'Ragflow服务运行正常'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def load_document(self, 
                      file_path: str, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """通过Ragflow上传文档"""
        if not self._is_initialized:
            raise RuntimeError("Ragflow未初始化")
        
        try:
            self._dataset.upload_documents([file_path])
            return True
        except Exception as e:
            print(f"Ragflow上传文档失败: {e}")
            return False
    
    def load_documents(self,
                       file_paths: List[str],
                       metadata_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, bool]:
        """批量上传文档"""
        if not self._is_initialized:
            raise RuntimeError("Ragflow未初始化")
        
        try:
            self._dataset.upload_documents(file_paths)
            return {fp: True for fp in file_paths}
        except Exception as e:
            print(f"Ragflow批量上传失败: {e}")
            return {fp: False for fp in file_paths}
    
    def retrieve(self,
                 query: str,
                 top_k: int = 5,
                 threshold: float = 0.0,
                 filters: Optional[Dict[str, Any]] = None) -> List[RAGQueryResult]:
        """通过Ragflow检索"""
        if not self._is_initialized:
            raise RuntimeError("Ragflow未初始化")
        
        try:
            chunks = self._dataset.list_chunks(
                keywords=query,
                page_size=top_k
            )
            
            results = []
            for chunk in chunks:
                score = getattr(chunk, 'similarity', 1.0)
                if score >= threshold:
                    results.append(RAGQueryResult(
                        content=chunk.content_with_weight if hasattr(chunk, 'content_with_weight') else chunk.content,
                        score=score,
                        metadata={
                            'document_id': chunk.document_id if hasattr(chunk, 'document_id') else '',
                            'chunk_id': chunk.id if hasattr(chunk, 'id') else ''
                        },
                        source=chunk.document_name if hasattr(chunk, 'document_name') else ''
                    ))
            return results
        except Exception as e:
            print(f"Ragflow检索失败: {e}")
            return []
    
    def query(self,
              question: str,
              top_k: int = 5,
              include_sources: bool = True) -> RAGResponse:
        """执行Ragflow RAG查询"""
        if not self._is_initialized:
            raise RuntimeError("Ragflow未初始化")
        
        try:
            chat = self._client.create_chat(
                name='rag-adapter-chat',
                dataset_ids=[self._dataset.id]
            )
            
            answer = chat.query(question)
            
            sources = []
            if include_sources:
                sources = self.retrieve(question, top_k=top_k)
            
            return RAGResponse(
                answer=answer.content if hasattr(answer, 'content') else str(answer),
                sources=sources,
                metadata={'backend': 'ragflow', 'chat_id': chat.id if hasattr(chat, 'id') else ''}
            )
        except Exception as e:
            return RAGResponse(
                answer=f"查询失败: {str(e)}",
                sources=[],
                metadata={'error': str(e)}
            )
    
    def delete_document(self, doc_id: str) -> bool:
        """删除Ragflow文档"""
        if not self._is_initialized:
            raise RuntimeError("Ragflow未初始化")
        
        try:
            self._dataset.delete_documents([doc_id])
            return True
        except Exception as e:
            print(f"Ragflow删除文档失败: {e}")
            return False
    
    def clear_index(self) -> bool:
        """清空Ragflow数据集"""
        if not self._is_initialized:
            raise RuntimeError("Ragflow未初始化")
        
        try:
            self._client.delete_datasets(ids=[self._dataset.id])
            self._dataset = self._client.create_dataset(
                name=self._dataset_name,
                description='RAG Adapter Dataset'
            )
            return True
        except Exception as e:
            print(f"Ragflow清空数据集失败: {e}")
            return False
    
    def get_stats(self) -> RAGIndexStats:
        """获取Ragflow统计信息"""
        if not self._is_initialized:
            return RAGIndexStats(backend_type='ragflow')
        
        try:
            documents = self._dataset.list_documents(page_size=1000)
            chunks = self._dataset.list_chunks(page_size=1000)
            
            return RAGIndexStats(
                total_documents=len(documents) if documents else 0,
                total_chunks=len(chunks) if chunks else 0,
                index_size_mb=0.0,
                backend_type='ragflow'
            )
        except Exception:
            return RAGIndexStats(backend_type='ragflow')
