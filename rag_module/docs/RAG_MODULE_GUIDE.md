# RAG模块使用指南

## 概述

RAG（Retrieval-Augmented Generation）模块为AItools-for-historyresearch项目提供完整的检索增强生成功能，支持文档加载、文本分块、向量检索和生成式问答。

## 核心功能

- **多格式文档加载**：支持PDF、Markdown、TXT等格式
- **智能文本分块**：递归分块、语义分块等多种策略
- **高效向量检索**：支持ChromaDB、FAISS、内存存储
- **混合检索**：结合向量检索和关键词检索
- **LLM集成**：与项目现有LLM客户端无缝集成

## 快速开始

### 基本使用

```python
from rag_module import RAGEngine, RAGConfig

# 创建RAG引擎
config = RAGConfig.default()
engine = RAGEngine(config)

# 添加文档
engine.add_documents(['document.pdf', 'notes.md'])

# 或直接添加文本
engine.add_text('明治维新是日本历史上的重要改革运动。')

# 执行查询
result = engine.query('明治维新是什么？')
print(result.answer)
```

### 预设配置

```python
# 日本史研究专用配置
config = RAGConfig.for_japanese_history()

# 学术论文专用配置
config = RAGConfig.for_academic_papers()

# 轻量级配置（测试用）
config = RAGConfig.lightweight()
```

## 配置说明

### RAGConfig参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| embedding_model | str | 'bge-m3' | 嵌入模型 |
| embedding_dimension | int | 1024 | 向量维度 |
| vector_store | VectorStoreType | CHROMA | 向量存储类型 |
| chunk_size | int | 512 | 块大小 |
| chunk_overlap | int | 50 | 块重叠 |
| retrieval_top_k | int | 5 | 检索返回数量 |
| retrieval_threshold | float | 0.0 | 相似度阈值 |
| llm_provider | str | 'qwen' | LLM服务商 |
| llm_model | str | 'qwen-turbo' | LLM模型 |

## 文档加载器

### PDF加载

```python
from rag_module.loaders import PDFLoader

loader = PDFLoader({
    'extract_tables': True,
    'pdf_use_ocr': False
})

documents = loader.load('document.pdf')
```

### Markdown加载

```python
from rag_module.loaders import MarkdownLoader

loader = MarkdownLoader({
    'markdown_extract_links': True,
    'markdown_extract_code_blocks': True
})

documents = loader.load('notes.md')
```

### 批量加载

```python
from rag_module.loaders import DocumentLoaderManager

manager = DocumentLoaderManager()

# 加载多个文件
documents = manager.load_batch(['doc1.pdf', 'doc2.md', 'doc3.txt'])

# 加载目录
documents = manager.load_directory('./documents', recursive=True)
```

## 文本分块

### 递归分块

```python
from rag_module.splitters import RecursiveSplitter

splitter = RecursiveSplitter(
    chunk_size=512,
    chunk_overlap=50,
    language='japanese'
)

chunks = splitter.split(document)
```

### 语义分块

```python
from rag_module.splitters import SemanticSplitter

splitter = SemanticSplitter(
    chunk_size=512,
    similarity_threshold=0.7
)

chunks = splitter.split(document)
```

## 向量存储

### ChromaDB存储

```python
from rag_module.stores import ChromaStore

store = ChromaStore(
    store_path='./data/vectors',
    embedding_dimension=1024
)

# 添加向量
store.add_vectors(vectors, chunks)

# 搜索
results = store.search(query_vector, top_k=5)
```

### FAISS存储

```python
from rag_module.stores import FAISSStore

store = FAISSStore(
    store_path='./data/faiss',
    embedding_dimension=1024,
    index_type='IndexFlatIP'
)
```

### 内存存储

```python
from rag_module.stores import MemoryStore

store = MemoryStore(embedding_dimension=384)
```

## 检索器

### 向量检索

```python
from rag_module.retrievers import VectorRetriever

retriever = VectorRetriever(
    vector_store=store,
    embedder=embedder,
    top_k=5
)

result = retriever.retrieve('查询文本')
```

### 混合检索

```python
from rag_module.retrievers import HybridRetriever

retriever = HybridRetriever(
    vector_store=store,
    embedder=embedder,
    alpha=0.5  # 向量检索权重
)

result = retriever.retrieve('查询文本')
```

## 高级用法

### 自定义提示词

```python
class CustomRAGEngine(RAGEngine):
    def _build_prompt(self, question, context):
        return f"""你是日本史研究专家。请根据以下资料回答问题。

资料：
{context}

问题：{question}

请提供专业、准确的回答。"""
```

### 带过滤的检索

```python
result = engine._retriever_manager._retriever.retrieve_with_filter(
    query='明治维新',
    filter_dict={'topic': '日本史'},
    top_k=10
)
```

### 索引管理

```python
# 保存索引
engine.save_index('./saved_index')

# 加载索引
engine.load_index('./saved_index')

# 清空索引
engine.clear_index()

# 删除特定文档
engine.delete_document('doc_id')

# 获取统计信息
stats = engine.get_stats()
```

## 与项目集成

### 与LLM客户端集成

```python
from modules.llm_client import LLMClient

llm = LLMClient({'provider': 'qwen'})

config = RAGConfig(
    llm_provider='qwen',
    llm_model='qwen-turbo'
)

engine = RAGEngine(config)
```

### 与嵌入管理器集成

```python
from modules.embedding_manager import EmbeddingManager

embedder = EmbeddingManager()
embedder.load_embedding_model('bge-m3')

config = RAGConfig(embedding_model='bge-m3')
engine = RAGEngine(config)
```

## 性能优化

### 批量处理

```python
# 批量添加文档
engine.add_documents([
    'doc1.pdf', 'doc2.pdf', 'doc3.pdf'
])
```

### 调整块大小

```python
# 大块：适合长文档
config = RAGConfig(chunk_size=1024, chunk_overlap=150)

# 小块：适合精确检索
config = RAGConfig(chunk_size=256, chunk_overlap=30)
```

### 使用混合检索

```python
config = RAGConfig(
    retrieval_strategy='hybrid',
    enable_reranking=True
)
```

## 错误处理

```python
try:
    result = engine.query('问题')
except Exception as e:
    print(f"查询失败: {e}")
```

## 最佳实践

1. **选择合适的块大小**：根据文档类型调整，学术论文建议1024，普通文本建议512
2. **使用适当的重叠**：保持上下文连贯性，建议10-20%的重叠
3. **定期保存索引**：避免重复处理文档
4. **监控检索质量**：调整top_k和threshold参数
5. **使用混合检索**：提高检索准确性

## 常见问题

### Q: 如何处理日文文档？

```python
config = RAGConfig(
    chunk_size=768,
    chunk_overlap=100
)
splitter = RecursiveSplitter(language='japanese')
```

### Q: 如何提高检索准确性？

```python
config = RAGConfig(
    retrieval_top_k=10,
    enable_reranking=True,
    retrieval_strategy='hybrid'
)
```

### Q: 如何处理大型文档集？

```python
# 使用FAISS存储
config = RAGConfig(
    vector_store='faiss',
    batch_size=64
)
```

## 版本历史

- v1.0.0 (2026-03-31): 初始版本
  - 文档加载器（PDF、Markdown、TXT）
  - 文本分块器（递归、语义）
  - 向量存储（ChromaDB、FAISS、内存）
  - 检索器（向量、混合）
  - RAG引擎

## 许可证

与主项目保持一致。
