"""
RAG模块快速启动示例

演示RAG模块的基本使用方法。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag_module import RAGEngine, RAGConfig


def basic_example():
    """基本使用示例"""
    print("=" * 60)
    print("RAG模块基本使用示例")
    print("=" * 60)
    
    config = RAGConfig.lightweight()
    engine = RAGEngine(config)
    
    sample_texts = [
        "明治维新是日本历史上的一次重要改革运动，发生在1868年。"
        "这次改革结束了幕府统治，建立了以天皇为中心的新政府。",
        
        "伊藤博文是明治维新的重要人物之一，他曾担任日本第一任首相，"
        "对日本的现代化进程产生了深远影响。",
        
        "大久保利通被称为'明治维新之父'，他推行了一系列现代化改革，"
        "包括地税改革、殖产兴业等政策。",
        
        "日本近代史上的甲午战争（1894-1895）标志着日本成为亚洲强国，"
        "这场战争后，日本获得了台湾和澎湖列岛。"
    ]
    
    print("\n添加示例文档...")
    for i, text in enumerate(sample_texts):
        result = engine.add_text(text, metadata={'doc_id': f'doc_{i+1}'})
        print(f"  文档{i+1}: 添加了 {result['chunks_added']} 个块")
    
    print("\n执行查询...")
    queries = [
        "明治维新是什么时候发生的？",
        "伊藤博文是谁？",
        "甲午战争的结果是什么？"
    ]
    
    for query in queries:
        print(f"\n问题: {query}")
        result = engine.query(query)
        print(f"回答: {result.answer[:200]}...")
        print(f"置信度: {result.confidence:.2f}")
        print(f"来源数量: {len(result.source_chunks)}")
    
    stats = engine.get_stats()
    print(f"\n索引统计:")
    print(f"  总文档数: {stats.total_documents}")
    print(f"  总块数: {stats.total_chunks}")


def document_loading_example():
    """文档加载示例"""
    print("\n" + "=" * 60)
    print("文档加载示例")
    print("=" * 60)
    
    from rag_module.loaders import TextLoader, MarkdownLoader
    from rag_module.core.types import DocumentType
    
    temp_dir = os.path.join(os.path.dirname(__file__), 'temp_docs')
    os.makedirs(temp_dir, exist_ok=True)
    
    txt_file = os.path.join(temp_dir, 'sample.txt')
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("这是一个测试文本文件。\n包含多行内容。\n用于演示文本加载功能。")
    
    md_file = os.path.join(temp_dir, 'sample.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# 测试标题\n\n这是Markdown内容。\n\n## 子标题\n\n更多内容。")
    
    print("\n加载文本文件...")
    txt_loader = TextLoader()
    txt_docs = txt_loader.load(txt_file)
    print(f"  加载了 {len(txt_docs)} 个文档")
    print(f"  类型: {txt_docs[0].doc_type.value}")
    
    print("\n加载Markdown文件...")
    md_loader = MarkdownLoader()
    md_docs = md_loader.load(md_file)
    print(f"  加载了 {len(md_docs)} 个文档")
    for doc in md_docs:
        print(f"  章节: {doc.metadata.get('section_title', 'N/A')}")
    
    import shutil
    shutil.rmtree(temp_dir)


def chunking_example():
    """文本分块示例"""
    print("\n" + "=" * 60)
    print("文本分块示例")
    print("=" * 60)
    
    from rag_module.splitters import RecursiveSplitter, SemanticSplitter
    from rag_module.core.types import Document, DocumentType
    
    long_text = """
    明治维新是日本历史上的一次重大改革运动。这场改革发生在19世纪下半叶，
    标志着日本从封建社会向现代国家的转变。改革的主要内容包括废除幕府制度、
    建立新政府、推行现代化政策等。
    
    改革的背景可以追溯到1853年，当时美国海军准将佩里率领舰队来到日本，
    迫使日本开放国门。这一事件被称为"黑船来航"，它打破了日本长达200多年的
    锁国政策，也暴露了幕府统治的软弱无力。
    
    在随后的几年里，日本国内出现了强烈的改革呼声。以萨摩藩和长州藩为首的
    倒幕派势力逐渐壮大，他们主张推翻幕府统治，建立以天皇为中心的新政府。
    1868年，倒幕派取得了胜利，明治天皇正式即位，开始了明治维新。
    """
    
    doc = Document(
        id='test_doc',
        content=long_text,
        doc_type=DocumentType.TEXT
    )
    
    print("\n递归分块 (chunk_size=200):")
    splitter = RecursiveSplitter(chunk_size=200, chunk_overlap=50)
    chunks = splitter.split(doc)
    print(f"  生成了 {len(chunks)} 个块")
    for i, chunk in enumerate(chunks[:3]):
        print(f"  块{i+1}: {chunk.content[:50]}...")
    
    print("\n语义分块 (chunk_size=200):")
    semantic_splitter = SemanticSplitter(chunk_size=200, chunk_overlap=50)
    semantic_chunks = semantic_splitter.split(doc)
    print(f"  生成了 {len(semantic_chunks)} 个块")


def vector_store_example():
    """向量存储示例"""
    print("\n" + "=" * 60)
    print("向量存储示例")
    print("=" * 60)
    
    from rag_module.stores import MemoryStore
    from rag_module.core.types import Chunk
    
    store = MemoryStore(embedding_dimension=384)
    
    chunks = [
        Chunk(id='c1', document_id='d1', content='明治维新发生在1868年'),
        Chunk(id='c2', document_id='d1', content='伊藤博文是第一任首相'),
        Chunk(id='c3', document_id='d1', content='大久保利通被称为维新之父')
    ]
    
    import numpy as np
    vectors = [
        np.random.randn(384).tolist(),
        np.random.randn(384).tolist(),
        np.random.randn(384).tolist()
    ]
    
    print("\n添加向量...")
    result = store.add_vectors(vectors, chunks)
    print(f"  添加了 {result['added_count']} 个向量")
    
    print("\n搜索向量...")
    query_vector = np.random.randn(384).tolist()
    results = store.search(query_vector, top_k=2)
    print(f"  找到 {len(results)} 个结果")
    for chunk, score in results:
        print(f"  - {chunk.content} (相似度: {score:.4f})")
    
    stats = store.get_stats()
    print(f"\n存储统计:")
    print(f"  总向量数: {stats.total_vectors}")
    print(f"  向量维度: {stats.vector_dimension}")


def config_presets_example():
    """配置预设示例"""
    print("\n" + "=" * 60)
    print("配置预设示例")
    print("=" * 60)
    
    configs = {
        '默认配置': RAGConfig.default(),
        '日本史研究': RAGConfig.for_japanese_history(),
        '学术论文': RAGConfig.for_academic_papers(),
        '轻量级': RAGConfig.lightweight()
    }
    
    for name, config in configs.items():
        print(f"\n{name}:")
        print(f"  块大小: {config.chunk_size}")
        print(f"  块重叠: {config.chunk_overlap}")
        print(f"  检索数量: {config.retrieval_top_k}")
        print(f"  重排序: {config.enable_reranking}")


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("RAG模块示例演示")
    print("=" * 60)
    
    basic_example()
    document_loading_example()
    chunking_example()
    vector_store_example()
    config_presets_example()
    
    print("\n" + "=" * 60)
    print("示例演示完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
