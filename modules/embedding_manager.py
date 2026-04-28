"""
嵌入模型配置与管理模块

管理和配置多种嵌入模型，支持向量数据库构建和语义检索
为RAG系统提供底层向量检索支持

核心功能：
- 加载指定嵌入模型
- 构建本地向量索引
- 高维向量相似度检索
- 对比不同嵌入模型效果
- 支持多种嵌入模型

支持的嵌入模型：
- BGE-M3（智源研究院）
- Qwen3-Embedding（阿里巴巴）
- Voyage-3-large
- OpenAI text-embedding-3
- Ollama本地模型

依赖模块：
- environment_checker.py
"""

import json
import hashlib
import math
import random
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import defaultdict
from datetime import datetime

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


class EmbeddingManager:
    """嵌入模型配置与管理器"""

    SUPPORTED_MODELS = {
        'bge-m3': {
            'name': 'BGE-M3',
            'provider': 'BAAI (智源研究院)',
            'max_tokens': 8192,
            'dimensions': 1024,
            'multilingual': True,
            'languages': '100+',
            'features': ['稠密检索', '稀疏检索', '多向量检索']
        },
        'qwen3-embedding': {
            'name': 'Qwen3-Embedding',
            'provider': 'Alibaba Cloud',
            'max_tokens': 32000,
            'dimensions': '32-4096 (MRL)',
            'multilingual': True,
            'languages': '100+',
            'features': ['长文本处理', '跨语言检索', '指令感知']
        },
        'voyage-3-large': {
            'name': 'Voyage-3-large',
            'provider': 'Voyage AI',
            'max_tokens': 32000,
            'dimensions': '256-2048 (MRL)',
            'multilingual': True,
            'languages': '多语言支持',
            'features': ['MRL', '量化感知训练', '高效存储']
        },
        'text-embedding-3-large': {
            'name': 'OpenAI text-embedding-3-large',
            'provider': 'OpenAI',
            'max_tokens': 8192,
            'dimensions': 3072,
            'multilingual': True,
            'languages': '多语言支持',
            'features': ['维度截断', '高性能']
        },
        'ollama-local': {
            'name': 'Ollama本地模型',
            'provider': '本地部署',
            'max_tokens': 4096,
            'dimensions': 2048,
            'multilingual': True,
            'languages': '取决于模型',
            'features': ['本地部署', '隐私保护', '离线使用']
        }
    }

    def __init__(self, default_model: str = 'bge-m3', auto_load_models: bool = False):
        """
        初始化嵌入模型管理器

        Args:
            default_model: 默认嵌入模型
            auto_load_models: 是否在建索引时自动加载重模型
        """
        self.default_model = default_model
        self.auto_load_models = auto_load_models
        self.current_model = None
        self.model_instance = None

        self.vector_index = {}
        self.document_store = {}

        self.available_models = self._check_available_models()

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a capability snapshot without loading heavy embedding models."""

        return {
            "module": "embedding_manager",
            "layer": "analysis_retrieval",
            "backend": "script" if not self.model_instance else self.model_instance.get("type", "embedding_model"),
            "provider": self._provider_for_model(self.current_model or self.default_model),
            "model": self.current_model or self.default_model,
            "tasks": [
                "embedding_index_build",
                "semantic_search",
                "embedding_model_comparison",
                "index_save_load",
            ],
            "output_types": ["embedding_index", "semantic_search"],
            "supported_models": self.SUPPORTED_MODELS,
            "available_models": list(self.available_models),
            "auto_load_models": self.auto_load_models,
            "safe_default": not self.auto_load_models,
            "supports": {
                "mock_embedding": True,
                "local_model": True,
                "remote_api": True,
                "package_output": True,
                "lazy_loading": True,
            },
            "privacy": {
                "local_first": True,
                "secrets_required": False if not self.model_instance else self.model_instance.get("type") == "api",
                "logs_raw_text": False,
            },
        }

    def load_embedding_model(self, model_name: str = 'bge-m3') -> bool:
        """
        加载指定的嵌入模型

        Args:
            model_name: 模型名称

        Returns:
            bool: 是否加载成功
        """
        if model_name not in self.SUPPORTED_MODELS:
            return False

        if model_name not in self.available_models:
            print(f"警告: {model_name} 不可用，使用模拟模式")

        self.current_model = model_name

        if model_name == 'ollama-local':
            return self._load_ollama_model()
        elif model_name in ['bge-m3', 'qwen3-embedding']:
            return self._load_transformers_model(model_name)
        elif model_name in ['text-embedding-3-large', 'voyage-3-large']:
            return self._load_api_model(model_name)
        else:
            return True

    def create_vector_index(self, documents: List[Dict[str, Any]],
                          batch_size: int = 32) -> Dict[str, Any]:
        """
        构建本地向量索引

        Args:
            documents: 文档列表，每项包含text和metadata
            batch_size: 批处理大小

        Returns:
            dict: 索引构建结果
        """
        if self.current_model is None:
            if self.auto_load_models:
                self.load_embedding_model(self.default_model)
            else:
                self.current_model = f"mock:{self.default_model}"

        vectors = []
        metadata_list = []

        for i, doc in enumerate(documents):
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})

            if self.model_instance:
                vector = self._get_embedding(text)
            else:
                vector = self._get_mock_embedding(text)

            vectors.append(vector)

            doc_id = self._generate_doc_id(text, i)
            metadata_list.append({
                'id': doc_id,
                'text': text[:200],
                'metadata': metadata,
                'vector_idx': i
            })

            self.document_store[doc_id] = {
                'text': text,
                'metadata': metadata,
                'vector': vector
            }

        self.vector_index['vectors'] = np.array(vectors) if np is not None else vectors
        self.vector_index['metadata'] = metadata_list
        self.vector_index['model'] = self.current_model
        self.vector_index['dimension'] = len(vectors[0]) if vectors else 0
        self.vector_index['count'] = len(vectors)

        return {
            'success': True,
            'document_count': len(documents),
            'dimension': self.vector_index['dimension'],
            'model': self.current_model
        }

    def create_vector_index_package(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 32,
        model_name: Optional[str] = None,
        force_load_model: bool = False,
    ) -> Dict[str, Any]:
        """Build an embedding index and return a workflow package envelope."""

        if model_name:
            self.default_model = model_name
        if force_load_model:
            self.load_embedding_model(self.default_model)

        quality_flags = []
        if not documents:
            quality_flags.append("empty_documents")
        if not force_load_model and not self.model_instance:
            quality_flags.append("mock_embedding_used")

        try:
            result = self.create_vector_index(documents, batch_size=batch_size)
            success = bool(result.get("success"))
        except Exception as exc:  # noqa: BLE001
            result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}
            success = False
            quality_flags.append("index_build_failed")

        stats = self.get_index_stats()
        return {
            "type": "embedding_index",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script" if not self.model_instance else self.model_instance.get("type", "embedding_model"),
            "provider": self._provider_for_model(self.current_model or self.default_model),
            "model": self.current_model or self.default_model,
            "confidence": self._package_confidence(success, quality_flags, stats),
            "needs_review": (not success) or bool(quality_flags),
            "quality_flags": quality_flags,
            "index": {
                "initialized": stats.get("initialized", False),
                "document_count": stats.get("document_count", 0),
                "dimension": stats.get("dimension", 0),
                "memory_usage_mb": stats.get("memory_usage_mb", 0.0),
            },
            "result": result,
            "capabilities": self.get_capabilities(),
            "error": "" if success else result.get("error", "index build failed"),
        }

    def semantic_search(self, query: str,
                      top_k: int = 5,
                      threshold: float = 0.0) -> List[Dict[str, Any]]:
        """
        执行语义搜索

        Args:
            query: 查询文本
            top_k: 返回的top-k结果
            threshold: 相似度阈值

        Returns:
            list: 搜索结果，按相似度降序排列
        """
        if not self.vector_index.get('vectors') is not None:
            return []

        if self.model_instance:
            query_vector = self._get_embedding(query)
        else:
            query_vector = self._get_mock_embedding(query)

        vectors = self.vector_index['vectors']

        similarities = self._compute_cosine_similarity(query_vector, vectors)

        results = []
        metadata_list = self.vector_index['metadata']

        ranked_indices = (
            np.argsort(similarities)[::-1][:top_k]
            if np is not None
            else sorted(range(len(similarities)), key=lambda item: similarities[item], reverse=True)[:top_k]
        )
        for idx in ranked_indices:
            score = float(similarities[idx])

            if score >= threshold:
                doc_info = metadata_list[idx]
                results.append({
                    'id': doc_info['id'],
                    'text': doc_info['text'],
                    'metadata': doc_info['metadata'],
                    'score': score,
                    'rank': len(results) + 1
                })

        return results

    def semantic_search_package(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> Dict[str, Any]:
        """Run semantic search and return a package envelope."""

        quality_flags = []
        if not str(query or "").strip():
            quality_flags.append("empty_query")
        if not self.vector_index.get("vectors") is not None:
            quality_flags.append("index_not_initialized")

        try:
            results = self.semantic_search(query or "", top_k=top_k, threshold=threshold)
            success = "index_not_initialized" not in quality_flags
        except Exception as exc:  # noqa: BLE001
            results = []
            success = False
            quality_flags.append("semantic_search_failed")
            error = f"{type(exc).__name__}: {exc}"
        else:
            error = ""

        if success and not results:
            quality_flags.append("no_results")

        return {
            "type": "semantic_search",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script" if not self.model_instance else self.model_instance.get("type", "embedding_model"),
            "provider": self._provider_for_model(self.current_model or self.default_model),
            "model": self.current_model or self.default_model,
            "query_length": len(query or ""),
            "confidence": self._package_confidence(success, quality_flags, self.get_index_stats()),
            "needs_review": (not success) or bool(quality_flags),
            "quality_flags": quality_flags,
            "results": results,
            "search_summary": {
                "top_k": top_k,
                "threshold": threshold,
                "result_count": len(results),
            },
            "capabilities": self.get_capabilities(),
            "error": error,
        }

    def add_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        向现有索引添加文档

        Args:
            documents: 文档列表

        Returns:
            dict: 添加结果
        """
        if not self.vector_index.get('vectors') is not None:
            return {'success': False, 'error': '索引未初始化'}

        start_idx = self.vector_index['count']
        new_vectors = []
        new_metadata = []

        for i, doc in enumerate(documents):
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})

            if self.model_instance:
                vector = self._get_embedding(text)
            else:
                vector = self._get_mock_embedding(text)

            new_vectors.append(vector)

            doc_id = self._generate_doc_id(text, start_idx + i)
            new_metadata.append({
                'id': doc_id,
                'text': text[:200],
                'metadata': metadata,
                'vector_idx': start_idx + i
            })

            self.document_store[doc_id] = {
                'text': text,
                'metadata': metadata,
                'vector': vector
            }

        existing_vectors = self.vector_index['vectors']
        if np is not None:
            self.vector_index['vectors'] = np.vstack([existing_vectors, np.array(new_vectors)])
        else:
            self.vector_index['vectors'] = list(existing_vectors) + new_vectors
        self.vector_index['metadata'].extend(new_metadata)
        self.vector_index['count'] += len(documents)

        return {
            'success': True,
            'added_count': len(documents),
            'total_count': self.vector_index['count']
        }

    def remove_documents(self, doc_ids: List[str]) -> Dict[str, Any]:
        """
        从索引中删除文档

        Args:
            doc_ids: 要删除的文档ID列表

        Returns:
            dict: 删除结果
        """
        if not self.vector_index.get('vectors') is not None:
            return {'success': False, 'error': '索引未初始化'}

        indices_to_remove = []

        for doc_id in doc_ids:
            for i, meta in enumerate(self.vector_index['metadata']):
                if meta['id'] == doc_id:
                    indices_to_remove.append(meta['vector_idx'])
                    break

        if not indices_to_remove:
            return {'success': False, 'error': '未找到指定文档'}

        if np is not None:
            keep_mask = np.ones(len(self.vector_index['vectors']), dtype=bool)
            keep_mask[indices_to_remove] = False
            self.vector_index['vectors'] = self.vector_index['vectors'][keep_mask]
        else:
            self.vector_index['vectors'] = [
                vector for idx, vector in enumerate(self.vector_index['vectors'])
                if idx not in indices_to_remove
            ]

        new_metadata = []
        new_vector_idx = 0
        for i, meta in enumerate(self.vector_index['metadata']):
            if i not in indices_to_remove:
                meta['vector_idx'] = new_vector_idx
                new_metadata.append(meta)
                new_vector_idx += 1

        self.vector_index['metadata'] = new_metadata
        self.vector_index['count'] = len(new_metadata)

        for doc_id in doc_ids:
            if doc_id in self.document_store:
                del self.document_store[doc_id]

        return {
            'success': True,
            'removed_count': len(indices_to_remove),
            'remaining_count': self.vector_index['count']
        }

    def model_comparison(self, test_queries: List[str],
                        ground_truth: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        对比不同嵌入模型的效果

        Args:
            test_queries: 测试查询列表
            ground_truth: 真实相关文档ID（可选）

        Returns:
            dict: 对比结果
        """
        results = {}

        models_to_test = ['bge-m3', 'qwen3-embedding', 'ollama-local']

        for model_name in models_to_test:
            if model_name not in self.available_models:
                continue

            self.load_embedding_model(model_name)

            model_results = {
                'model': model_name,
                'queries': []
            }

            for query in test_queries:
                search_results = self.semantic_search(query, top_k=3)

                model_results['queries'].append({
                    'query': query,
                    'top_results': [
                        {'id': r['id'], 'score': r['score']}
                        for r in search_results
                    ]
                })

            results[model_name] = model_results

        return {
            'test_date': datetime.now().isoformat(),
            'models_tested': list(results.keys()),
            'results': results
        }

    def get_index_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息

        Returns:
            dict: 统计信息
        """
        if not self.vector_index.get('vectors') is not None:
            return {
                'initialized': False,
                'message': '索引未初始化'
            }

        return {
            'initialized': True,
            'model': self.vector_index.get('model'),
            'document_count': self.vector_index.get('count', 0),
            'dimension': self.vector_index.get('dimension', 0),
            'memory_usage_mb': self._estimate_memory_usage()
        }

    def save_index(self, output_path: str) -> bool:
        """
        保存索引到文件

        Args:
            output_path: 输出文件路径

        Returns:
            bool: 是否保存成功
        """
        if not self.vector_index.get('vectors') is not None:
            return False

        try:
            save_data = {
                'model': self.vector_index.get('model'),
                'dimension': self.vector_index.get('dimension'),
                'count': self.vector_index.get('count'),
                'metadata': self.vector_index.get('metadata'),
                'vectors_path': output_path.replace('.json', '_vectors.npy')
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            if np is not None:
                np.save(save_data['vectors_path'], self.vector_index['vectors'])
            else:
                Path(save_data['vectors_path']).write_text(
                    json.dumps(self.vector_index['vectors'], ensure_ascii=False),
                    encoding='utf-8',
                )

            return True
        except Exception as e:
            print(f"保存索引失败: {e}")
            return False

    def load_index(self, input_path: str) -> bool:
        """
        从文件加载索引

        Args:
            input_path: 输入文件路径

        Returns:
            bool: 是否加载成功
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)

            vectors_path = input_path.replace('.json', '_vectors.npy')
            if np is not None:
                vectors = np.load(vectors_path)
            else:
                vectors = json.loads(Path(vectors_path).read_text(encoding='utf-8'))

            self.vector_index['model'] = save_data.get('model')
            self.vector_index['dimension'] = save_data.get('dimension')
            self.vector_index['count'] = save_data.get('count')
            self.vector_index['metadata'] = save_data.get('metadata', [])
            self.vector_index['vectors'] = vectors

            for meta in self.vector_index['metadata']:
                doc_id = meta['id']
                idx = meta['vector_idx']
                self.document_store[doc_id] = {
                    'text': meta.get('text', ''),
                    'metadata': meta.get('metadata', {}),
                    'vector': vectors[idx]
                }

            return True
        except Exception as e:
            print(f"加载索引失败: {e}")
            return False

    def clear_index(self):
        """清除索引和文档存储"""
        self.vector_index = {}
        self.document_store = {}

    def _check_available_models(self) -> List[str]:
        """检查可用的模型"""
        available = []

        try:
            import transformers
            available.extend(['bge-m3', 'qwen3-embedding'])
        except ImportError:
            pass

        try:
            import openai
            available.extend(['text-embedding-3-large'])
        except ImportError:
            pass

        available.append('ollama-local')

        return available

    def _load_ollama_model(self) -> bool:
        """加载Ollama模型"""
        try:
            import ollama

            self.model_instance = {
                'type': 'ollama',
                'client': ollama
            }

            return True
        except ImportError:
            print("警告: ollama库未安装，使用模拟模式")
            return False

    def _load_transformers_model(self, model_name: str) -> bool:
        """加载transformers模型"""
        try:
            from sentence_transformers import SentenceTransformer

            model_map = {
                'bge-m3': 'BAAI/bge-m3',
                'qwen3-embedding': 'Qwen/Qwen3-Embedding'
            }

            model_path = model_map.get(model_name, model_name)

            self.model_instance = {
                'type': 'transformers',
                'model': SentenceTransformer(model_path)
            }

            return True
        except ImportError:
            print("警告: sentence-transformers未安装，使用模拟模式")
            return False
        except Exception as e:
            print(f"警告: 加载模型失败 - {e}，使用模拟模式")
            return False

    def _load_api_model(self, model_name: str) -> bool:
        """加载API模型"""
        try:
            from openai import OpenAI

            self.model_instance = {
                'type': 'api',
                'client': OpenAI()
            }

            return True
        except ImportError:
            print("警告: openai库未安装，使用模拟模式")
            return False

    def _get_embedding(self, text: str):
        """获取文本嵌入向量"""
        if not self.model_instance:
            return self._get_mock_embedding(text)

        model_type = self.model_instance.get('type')

        if model_type == 'ollama':
            try:
                response = self.model_instance['client'].embeddings.create(
                    model='nomic-embed-text',
                    input=text
                )
                return np.array(response.data[0].embedding) if np is not None else list(response.data[0].embedding)
            except:
                return self._get_mock_embedding(text)

        elif model_type == 'transformers':
            try:
                embedding = self.model_instance['model'].encode(text)
                return embedding
            except:
                return self._get_mock_embedding(text)

        elif model_type == 'api':
            try:
                response = self.model_instance['client'].embeddings.create(
                    model='text-embedding-3-large',
                    input=text
                )
                return np.array(response.data[0].embedding) if np is not None else list(response.data[0].embedding)
            except:
                return self._get_mock_embedding(text)

        return self._get_mock_embedding(text)

    def _get_mock_embedding(self, text: str):
        """生成模拟嵌入向量"""
        text_hash = hashlib.md5(text.encode('utf-8')).digest()

        seed = int.from_bytes(text_hash[:4], 'big')

        dimension = 384

        if np is not None:
            np.random.seed(seed)
            vector = np.random.randn(dimension)
            vector = vector / np.linalg.norm(vector)
            return vector

        rng = random.Random(seed)
        vector = [rng.gauss(0, 1) for _ in range(dimension)]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _compute_cosine_similarity(self, query_vector, document_vectors):
        """计算余弦相似度"""
        if np is not None:
            query_norm = query_vector / np.linalg.norm(query_vector)
            doc_norms = np.linalg.norm(document_vectors, axis=1, keepdims=True)
            doc_norms = np.where(doc_norms == 0, 1, doc_norms)
            docs_normalized = document_vectors / doc_norms
            return np.dot(docs_normalized, query_norm)

        query_norm = math.sqrt(sum(value * value for value in query_vector)) or 1.0
        similarities = []
        for vector in document_vectors:
            doc_norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            dot = sum(left * right for left, right in zip(query_vector, vector))
            similarities.append(dot / (query_norm * doc_norm))
        return similarities

    def _generate_doc_id(self, text: str, index: int) -> str:
        """生成文档ID"""
        hash_obj = hashlib.md5(text.encode('utf-8'))
        return f"doc_{hash_obj.hexdigest()[:8]}_{index}"

    def _estimate_memory_usage(self) -> float:
        """估算内存使用（MB）"""
        if not self.vector_index.get('vectors') is not None:
            return 0.0

        vectors = self.vector_index['vectors']

        if np is not None and hasattr(vectors, "nbytes"):
            memory_bytes = vectors.nbytes
        else:
            dimension = len(vectors[0]) if vectors else 0
            memory_bytes = len(vectors) * dimension * 8

        memory_mb = memory_bytes / (1024 * 1024)

        return round(memory_mb, 2)

    def _provider_for_model(self, model_name: str) -> str:
        clean_name = (model_name or "").replace("mock:", "")
        if clean_name in self.SUPPORTED_MODELS:
            return str(self.SUPPORTED_MODELS[clean_name].get("provider", "unknown"))
        if clean_name.startswith("ollama"):
            return "ollama"
        return "unknown"

    def _package_confidence(
        self,
        success: bool,
        quality_flags: List[str],
        stats: Dict[str, Any],
    ) -> float:
        if not success:
            return 0.0
        score = 0.65
        if stats.get("initialized"):
            score += 0.15
        if stats.get("document_count", 0) > 0:
            score += 0.10
        if "mock_embedding_used" in quality_flags:
            score -= 0.20
        if "no_results" in quality_flags:
            score -= 0.10
        if "empty_documents" in quality_flags or "empty_query" in quality_flags:
            score -= 0.20
        return round(max(0.0, min(1.0, score)), 2)


def create_embedding_manager(default_model: str = 'bge-m3', auto_load_models: bool = False) -> EmbeddingManager:
    """
    工厂函数：创建嵌入模型管理器实例

    Args:
        default_model: 默认嵌入模型

    Returns:
        EmbeddingManager: 配置好的管理器实例
    """
    return EmbeddingManager(default_model=default_model, auto_load_models=auto_load_models)
