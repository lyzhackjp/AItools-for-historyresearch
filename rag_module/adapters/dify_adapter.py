"""
Dify RAG适配器

封装Dify平台的RAG功能，提供统一接口。
"""

from typing import List, Dict, Any, Optional
import os
import json

from rag_module.adapters.base_adapter import (
    BaseRAGAdapter, RAGBackend,
    RAGQueryResult, RAGResponse, RAGIndexStats
)


class DifyRAGAdapter(BaseRAGAdapter):
    """Dify RAG适配器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._api_key = config.get('api_key', '') if config else ''
        self._base_url = config.get('base_url', 'http://localhost/v1') if config else 'http://localhost/v1'
        self._dataset_id = config.get('dataset_id', '') if config else ''
        self._client = None
    
    @property
    def backend_type(self) -> RAGBackend:
        return RAGBackend.DIFY
    
    def _check_dify_available(self) -> bool:
        """检查Dify是否可用"""
        dify_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'external', 'dify'
        )
        return os.path.exists(dify_path)
    
    def initialize(self) -> bool:
        """初始化Dify连接"""
        if not self._check_dify_available():
            print("Dify未安装在external目录中")
            return False
        
        if not self._api_key:
            print("未配置Dify API密钥")
            return False
        
        try:
            import requests
            
            response = requests.get(
                f"{self._base_url}/datasets",
                headers={
                    'Authorization': f'Bearer {self._api_key}',
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                self._is_initialized = True
                return True
            else:
                print(f"Dify连接失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"初始化Dify连接失败: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """检查Dify健康状态"""
        if not self._is_initialized:
            return {'status': 'error', 'message': 'Dify未初始化'}
        
        try:
            import requests
            
            response = requests.get(
                f"{self._base_url}/health",
                timeout=5
            )
            
            if response.status_code == 200:
                return {'status': 'healthy', 'message': 'Dify服务运行正常'}
            else:
                return {'status': 'error', 'message': f'Dify服务异常: {response.status_code}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def load_document(self, 
                      file_path: str, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """通过Dify API上传文档"""
        if not self._is_initialized:
            raise RuntimeError("Dify未初始化")
        
        try:
            import requests
            
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                data = {
                    'data': json.dumps({
                        'indexing_technique': 'high_quality',
                        'process_rule': {
                            'mode': 'automatic'
                        }
                    })
                }
                
                response = requests.post(
                    f"{self._base_url}/datasets/{self._dataset_id}/document/create_by_file",
                    headers={'Authorization': f'Bearer {self._api_key}'},
                    files=files,
                    data=data,
                    timeout=60
                )
            
            return response.status_code == 200
        except Exception as e:
            print(f"Dify上传文档失败: {e}")
            return False
    
    def load_documents(self,
                       file_paths: List[str],
                       metadata_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, bool]:
        """批量上传文档"""
        results = {}
        for i, file_path in enumerate(file_paths):
            metadata = metadata_list[i] if metadata_list and i < len(metadata_list) else None
            results[file_path] = self.load_document(file_path, metadata)
        return results
    
    def retrieve(self,
                 query: str,
                 top_k: int = 5,
                 threshold: float = 0.0,
                 filters: Optional[Dict[str, Any]] = None) -> List[RAGQueryResult]:
        """通过Dify检索"""
        if not self._is_initialized:
            raise RuntimeError("Dify未初始化")
        
        try:
            import requests
            
            response = requests.post(
                f"{self._base_url}/datasets/{self._dataset_id}/retrieve",
                headers={
                    'Authorization': f'Bearer {self._api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'query': query,
                    'retrieval_setting': {
                        'top_k': top_k,
                        'score_threshold': threshold
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('records', []):
                    results.append(RAGQueryResult(
                        content=item.get('content', ''),
                        score=item.get('score', 0.0),
                        metadata=item.get('metadata', {}),
                        source=item.get('document_name', '')
                    ))
                return results
            return []
        except Exception as e:
            print(f"Dify检索失败: {e}")
            return []
    
    def query(self,
              question: str,
              top_k: int = 5,
              include_sources: bool = True) -> RAGResponse:
        """执行Dify RAG查询"""
        if not self._is_initialized:
            raise RuntimeError("Dify未初始化")
        
        try:
            import requests
            
            response = requests.post(
                f"{self._base_url}/chat-messages",
                headers={
                    'Authorization': f'Bearer {self._api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'inputs': {},
                    'query': question,
                    'response_mode': 'blocking',
                    'conversation_id': '',
                    'user': 'rag-adapter'
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                
                sources = []
                if include_sources:
                    sources = self.retrieve(question, top_k=top_k)
                
                return RAGResponse(
                    answer=answer,
                    sources=sources,
                    metadata={'backend': 'dify', 'conversation_id': data.get('conversation_id')}
                )
            
            return RAGResponse(
                answer=f"Dify查询失败: {response.status_code}",
                sources=[],
                metadata={'error': str(response.status_code)}
            )
        except Exception as e:
            return RAGResponse(
                answer=f"查询失败: {str(e)}",
                sources=[],
                metadata={'error': str(e)}
            )
    
    def delete_document(self, doc_id: str) -> bool:
        """删除Dify文档"""
        if not self._is_initialized:
            raise RuntimeError("Dify未初始化")
        
        try:
            import requests
            
            response = requests.delete(
                f"{self._base_url}/datasets/{self._dataset_id}/documents/{doc_id}",
                headers={'Authorization': f'Bearer {self._api_key}'},
                timeout=10
            )
            
            return response.status_code == 200
        except Exception as e:
            print(f"Dify删除文档失败: {e}")
            return False
    
    def clear_index(self) -> bool:
        """清空Dify数据集"""
        return False
    
    def get_stats(self) -> RAGIndexStats:
        """获取Dify统计信息"""
        if not self._is_initialized:
            return RAGIndexStats(backend_type='dify')
        
        try:
            import requests
            
            response = requests.get(
                f"{self._base_url}/datasets/{self._dataset_id}",
                headers={'Authorization': f'Bearer {self._api_key}'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return RAGIndexStats(
                    total_documents=data.get('document_count', 0),
                    total_chunks=data.get('segment_count', 0),
                    index_size_mb=0.0,
                    backend_type='dify'
                )
        except Exception:
            pass
        
        return RAGIndexStats(backend_type='dify')
