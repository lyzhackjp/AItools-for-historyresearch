"""
RAG模块测试

测试RAG引擎的核心功能。
"""

import unittest
import tempfile
import os
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from rag_module import RAGEngine, RAGConfig
from rag_module.core.types import Document, Chunk, DocumentType, ChunkStrategy
from rag_module.loaders import TextLoader, MarkdownLoader
from rag_module.splitters import RecursiveSplitter, SemanticSplitter
from rag_module.stores import MemoryStore


class TestRAGConfig(unittest.TestCase):
    """测试RAG配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = RAGConfig.default()
        
        self.assertEqual(config.embedding_model, 'bge-m3')
        self.assertEqual(config.chunk_size, 512)
        self.assertEqual(config.chunk_overlap, 50)
        self.assertEqual(config.retrieval_top_k, 5)
    
    def test_config_for_japanese_history(self):
        """测试日本史专用配置"""
        config = RAGConfig.for_japanese_history()
        
        self.assertEqual(config.chunk_size, 768)
        self.assertEqual(config.chunk_overlap, 100)
        self.assertEqual(config.retrieval_top_k, 7)
        self.assertTrue(config.enable_reranking)
    
    def test_config_to_dict(self):
        """测试配置序列化"""
        config = RAGConfig.default()
        data = config.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data['embedding_model'], 'bge-m3')
        self.assertEqual(data['chunk_size'], 512)


class TestDocumentTypes(unittest.TestCase):
    """测试文档类型"""
    
    def test_document_creation(self):
        """测试文档创建"""
        doc = Document(
            id='test_doc_1',
            content='这是一段测试文本。',
            metadata={'source': 'test'},
            doc_type=DocumentType.TEXT
        )
        
        self.assertEqual(doc.id, 'test_doc_1')
        self.assertEqual(doc.content, '这是一段测试文本。')
        self.assertEqual(doc.doc_type, DocumentType.TEXT)
    
    def test_document_serialization(self):
        """测试文档序列化"""
        doc = Document(
            id='test_doc_2',
            content='测试内容',
            metadata={'key': 'value'},
            doc_type=DocumentType.MARKDOWN
        )
        
        data = doc.to_dict()
        restored = Document.from_dict(data)
        
        self.assertEqual(restored.id, doc.id)
        self.assertEqual(restored.content, doc.content)
        self.assertEqual(restored.metadata, doc.metadata)
    
    def test_chunk_creation(self):
        """测试块创建"""
        chunk = Chunk(
            id='chunk_1',
            document_id='doc_1',
            content='块内容',
            chunk_index=0,
            start_char=0,
            end_char=4
        )
        
        self.assertEqual(chunk.id, 'chunk_1')
        self.assertEqual(chunk.document_id, 'doc_1')
        self.assertEqual(chunk.chunk_index, 0)


class TestTextLoader(unittest.TestCase):
    """测试文本加载器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, 'test.txt')
        
        with open(self.test_file, 'w', encoding='utf-8') as f:
            f.write('这是第一段测试文本。\n\n这是第二段测试文本。')
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_text_file(self):
        """测试加载文本文件"""
        loader = TextLoader()
        documents = loader.load(self.test_file)
        
        self.assertEqual(len(documents), 1)
        self.assertIn('第一段', documents[0].content)
        self.assertEqual(documents[0].doc_type, DocumentType.TEXT)
    
    def test_load_with_paragraph_split(self):
        """测试按段落分割"""
        loader = TextLoader({'split_by_paragraph': True, 'min_paragraph_length': 10})
        documents = loader.load(self.test_file)
        
        self.assertGreaterEqual(len(documents), 1)


class TestMarkdownLoader(unittest.TestCase):
    """测试Markdown加载器"""
    
    def setUp(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, 'test.md')
        
        content = """# 标题一

这是第一段内容。

## 标题二

这是第二段内容。

[链接](https://example.com)
"""
        with open(self.test_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_markdown_file(self):
        """测试加载Markdown文件"""
        loader = MarkdownLoader()
        documents = loader.load(self.test_file)
        
        self.assertGreater(len(documents), 0)
        self.assertEqual(documents[0].doc_type, DocumentType.MARKDOWN)
    
    def test_extract_sections(self):
        """测试提取章节"""
        loader = MarkdownLoader()
        documents = loader.load(self.test_file)
        
        section_titles = [doc.metadata.get('section_title') for doc in documents]
        self.assertIn('标题一', section_titles)
    
    def test_extract_links(self):
        """测试提取链接"""
        loader = MarkdownLoader({'markdown_extract_links': True})
        documents = loader.load(self.test_file)
        
        has_links = any('links' in doc.metadata for doc in documents)
        self.assertTrue(has_links)


class TestRecursiveSplitter(unittest.TestCase):
    """测试递归分块器"""
    
    def test_split_short_text(self):
        """测试分割短文本"""
        doc = Document(
            id='doc_1',
            content='这是一段短文本。',
            doc_type=DocumentType.TEXT
        )
        
        splitter = RecursiveSplitter(chunk_size=512, chunk_overlap=50)
        chunks = splitter.split(doc)
        
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].content, '这是一段短文本。')
    
    def test_split_long_text(self):
        """测试分割长文本"""
        long_text = '这是测试句子。' * 100
        
        doc = Document(
            id='doc_2',
            content=long_text,
            doc_type=DocumentType.TEXT
        )
        
        splitter = RecursiveSplitter(chunk_size=100, chunk_overlap=20)
        chunks = splitter.split(doc)
        
        self.assertGreater(len(chunks), 1)
        
        for chunk in chunks:
            self.assertLessEqual(len(chunk.content), 150)
    
    def test_chunk_metadata(self):
        """测试块元数据"""
        doc = Document(
            id='doc_3',
            content='测试内容',
            metadata={'source': 'test'},
            doc_type=DocumentType.TEXT
        )
        
        splitter = RecursiveSplitter()
        chunks = splitter.split(doc)
        
        self.assertEqual(chunks[0].document_id, 'doc_3')
        self.assertIn('source', chunks[0].metadata)


class TestMemoryStore(unittest.TestCase):
    """测试内存存储"""
    
    def test_add_vectors(self):
        """测试添加向量"""
        store = MemoryStore(embedding_dimension=384)
        
        chunks = [
            Chunk(id='c1', document_id='d1', content='内容1'),
            Chunk(id='c2', document_id='d1', content='内容2')
        ]
        
        vectors = [
            [0.1] * 384,
            [0.2] * 384
        ]
        
        result = store.add_vectors(vectors, chunks)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['added_count'], 2)
    
    def test_search(self):
        """测试搜索"""
        store = MemoryStore(embedding_dimension=384)
        
        chunks = [
            Chunk(id='c1', document_id='d1', content='关于机器学习的内容'),
            Chunk(id='c2', document_id='d1', content='关于历史研究的内容')
        ]
        
        vectors = [
            [0.1] * 384,
            [0.9] * 384
        ]
        
        store.add_vectors(vectors, chunks)
        
        query_vector = [0.9] * 384
        results = store.search(query_vector, top_k=2)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0].id, 'c2')
    
    def test_delete(self):
        """测试删除"""
        store = MemoryStore(embedding_dimension=384)
        
        chunks = [
            Chunk(id='c1', document_id='d1', content='内容1'),
            Chunk(id='c2', document_id='d1', content='内容2')
        ]
        
        vectors = [[0.1] * 384, [0.2] * 384]
        store.add_vectors(vectors, chunks)
        
        result = store.delete(['c1'])
        
        self.assertTrue(result['success'])
        self.assertEqual(result['remaining_count'], 1)


class TestRAGEngine(unittest.TestCase):
    """测试RAG引擎"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = RAGConfig.lightweight()
        self.engine = RAGEngine(self.config)
    
    def test_add_text(self):
        """测试添加文本"""
        result = self.engine.add_text(
            '明治维新是日本历史上的重要改革运动。',
            metadata={'topic': '日本史'}
        )
        
        self.assertTrue(result['success'])
        self.assertGreater(result['chunks_added'], 0)
    
    def test_query(self):
        """测试查询"""
        self.engine.add_text(
            '明治维新发生在1868年，是日本从封建社会向现代国家转变的重要时期。'
            '这次改革废除了幕府制度，建立了以天皇为中心的新政府。'
        )
        
        result = self.engine.query('明治维新是什么时候发生的？')
        
        self.assertIsNotNone(result.answer)
        self.assertGreater(len(result.answer), 0)
    
    def test_retrieve(self):
        """测试检索"""
        self.engine.add_text(
            '伊藤博文是明治维新的重要人物，曾担任日本第一任首相。'
        )
        
        chunks = self.engine.retrieve('伊藤博文')
        
        self.assertGreater(len(chunks), 0)
    
    def test_get_stats(self):
        """测试获取统计信息"""
        self.engine.add_text('测试内容')
        
        stats = self.engine.get_stats()
        
        self.assertGreater(stats.total_chunks, 0)
    
    def test_save_and_load(self):
        """测试保存和加载"""
        self.engine.add_text('测试保存和加载的内容')
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            saved = self.engine.save_index(temp_dir)
            self.assertTrue(saved)
            
            new_engine = RAGEngine(self.config)
            loaded = new_engine.load_index(temp_dir)
            self.assertTrue(loaded)
            
            stats = new_engine.get_stats()
            self.assertGreater(stats.total_chunks, 0)
        finally:
            import shutil
            shutil.rmtree(temp_dir)
    
    def test_clear_index(self):
        """测试清空索引"""
        self.engine.add_text('测试内容')
        
        self.engine.clear_index()
        
        stats = self.engine.get_stats()
        self.assertEqual(stats.total_chunks, 0)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_full_workflow(self):
        """测试完整工作流"""
        config = RAGConfig.lightweight()
        engine = RAGEngine(config)
        
        documents = [
            '明治维新是日本历史上的重要改革运动，发生在1868年。',
            '伊藤博文是明治维新的重要人物，曾担任日本第一任首相。',
            '大久保利通是明治维新的核心人物之一，被称为"明治维新之父"。'
        ]
        
        for doc in documents:
            engine.add_text(doc)
        
        result = engine.query('明治维新有哪些重要人物？')
        
        self.assertIsNotNone(result.answer)
        self.assertGreater(len(result.source_chunks), 0)
        
        stats = engine.get_stats()
        self.assertGreater(stats.total_documents, 0)


if __name__ == '__main__':
    unittest.main()
