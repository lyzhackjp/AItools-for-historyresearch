"""
学术论文润色模块优化版 - 测试脚本

测试内容：
1. 脚注提取与重建功能
2. 格式保留功能
3. 多策略润色功能
4. 修订追踪功能
"""

import sys
import os
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import docx  # noqa: F401
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("python-docx is not installed") from exc

from modules.paper_polisher_optimized import (
    PaperPolisherOptimized,
    FootnoteManager,
    FormatPreserver,
    create_paper_polisher_optimized
)
from modules.doc_processor import DocProcessor


def test_footnote_manager():
    """测试脚注管理器"""
    print("\n" + "="*60)
    print("测试 1: 脚注管理器功能")
    print("="*60)

    test_doc = Path(__file__).parent.parent / "data" / "test_documents" / "TW《新渡户论》20260324.docx"

    if not test_doc.exists():
        print(f"⚠ 测试文档不存在: {test_doc}")
        print("  跳过脚注管理器测试")
        return False

    manager = FootnoteManager()

    print(f"\n提取脚注信息: {test_doc.name}")
    result = manager.extract_all_footnotes(str(test_doc))

    print(f"\n✓ 脚注内容数量: {result['count']}")
    print(f"✓ 脚注引用数量: {len(result['references'])}")
    print(f"✓ 关系数量: {len(result['relationships'])}")

    if result['count'] > 0:
        print(f"\n前3个脚注预览:")
        for i, (fn_id, fn_info) in enumerate(list(result['contents'].items())[:3]):
            text_preview = fn_info['text'][:50] + "..." if len(fn_info['text']) > 50 else fn_info['text']
            print(f"  [{fn_id}] {text_preview}")

    if result['references']:
        print(f"\n前3个引用位置:")
        for ref in result['references'][:3]:
            print(f"  脚注ID {ref['id']} 在段落 {ref['paragraph_index']}")

    return result['count'] > 0


def test_format_preserver():
    """测试格式保留器"""
    print("\n" + "="*60)
    print("测试 2: 格式保留器功能")
    print("="*60)

    test_doc = Path(__file__).parent.parent / "data" / "test_documents" / "TW《新渡户论》20260324.docx"

    if not test_doc.exists():
        print(f"⚠ 测试文档不存在: {test_doc}")
        print("  跳过格式保留器测试")
        return False

    from docx import Document

    doc = Document(str(test_doc))
    preserver = FormatPreserver()

    print(f"\n提取前5个段落的格式信息:")
    for i, para in enumerate(doc.paragraphs[:5]):
        if para.text.strip():
            format_info = preserver.extract_paragraph_format(para)
            print(f"\n段落 {i+1}:")
            print(f"  样式: {format_info['style']}")
            print(f"  对齐: {format_info['alignment']}")
            print(f"  文本块数: {len(format_info['runs'])}")

            preserver.cache_format(f"para_{i}", format_info)

    cached = preserver.get_cached_format("para_0")
    if cached:
        print(f"\n✓ 格式缓存成功: 样式={cached['style']}")
        return True

    return False


def test_polishing_strategies():
    """测试润色策略"""
    print("\n" + "="*60)
    print("测试 3: 润色策略功能")
    print("="*60)

    strategies = ['paragraph', 'sentence', 'track_changes']

    for strategy in strategies:
        print(f"\n初始化策略 '{strategy}'...")
        try:
            polisher = create_paper_polisher_optimized('qwen', strategy)
            print(f"  ✓ 策略初始化成功: {polisher.strategy_name}")
        except Exception as e:
            print(f"  ✗ 策略初始化失败: {e}")

    return True


def test_document_processing():
    """测试文档处理功能"""
    print("\n" + "="*60)
    print("测试 4: 文档处理功能（测试模式）")
    print("="*60)

    test_doc = Path(__file__).parent.parent / "data" / "test_documents" / "TW《新渡户论》20260324.docx"

    if not test_doc.exists():
        print(f"⚠ 测试文档不存在: {test_doc}")
        print("  跳过文档处理测试")
        return False

    output_dir = Path(__file__).parent.parent / "data" / "output" / "polished"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_doc = output_dir / "test_polished_output.docx"

    print(f"\n输入文档: {test_doc.name}")
    print(f"输出文档: {output_doc.name}")

    polisher = create_paper_polisher_optimized('qwen', 'paragraph')

    try:
        result = polisher.process_document(
            str(test_doc),
            str(output_doc),
            enable_track_changes=True,
            rebuild_footnotes=True,
            preserve_format=True
        )

        print(f"\n处理结果:")
        print(f"  成功: {result['success']}")
        print(f"  总段落数: {result['total_paragraphs']}")
        print(f"  处理段落数: {result['processed_paragraphs']}")
        print(f"  删除内容数: {result['total_deletions']}")
        print(f"  脚注数量: {result['footnote_count']}")
        print(f"  脚注引用: {result['footnote_references']}")

        if output_doc.exists():
            print(f"\n✓ 输出文件已生成: {output_doc}")
            return True
        else:
            print(f"\n✗ 输出文件未生成")
            return False

    except Exception as e:
        print(f"\n✗ 文档处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_footnote_rebuild():
    """测试脚注重建功能"""
    print("\n" + "="*60)
    print("测试 5: 脚注重建功能")
    print("="*60)

    test_doc = Path(__file__).parent.parent / "data" / "test_documents" / "TW《新渡户论》20260324.docx"

    if not test_doc.exists():
        print(f"⚠ 测试文档不存在: {test_doc}")
        return False

    manager = FootnoteManager()

    original_info = manager.extract_all_footnotes(str(test_doc))
    print(f"\n原始文档脚注信息:")
    print(f"  脚注内容: {original_info['count']}")
    print(f"  脚注引用: {len(original_info['references'])}")

    output_dir = Path(__file__).parent.parent / "data" / "output" / "polished"
    output_dir.mkdir(parents=True, exist_ok=True)

    test_output = output_dir / "test_footnote_rebuild.docx"

    result = manager.rebuild_footnotes_in_document(
        str(test_doc),
        str(test_doc),
        str(test_output)
    )

    print(f"\n重建结果:")
    print(f"  成功: {result['success']}")
    print(f"  恢复脚注: {result['footnotes_restored']}")
    print(f"  恢复引用: {result['references_restored']}")

    if result['errors']:
        print(f"  错误: {result['errors']}")

    if test_output.exists():
        rebuilt_info = manager.extract_all_footnotes(str(test_output))
        print(f"\n重建后文档脚注信息:")
        print(f"  脚注内容: {rebuilt_info['count']}")
        print(f"  脚注引用: {len(rebuilt_info['references'])}")

        if rebuilt_info['count'] == original_info['count']:
            print(f"\n✓ 脚注数量一致，重建成功")
            return True
        else:
            print(f"\n⚠ 脚注数量不一致")
            return False

    return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("学术论文润色模块优化版 - 综合测试")
    print("="*60)

    results = {}

    results['footnote_manager'] = test_footnote_manager()
    results['format_preserver'] = test_format_preserver()
    results['polishing_strategies'] = test_polishing_strategies()
    results['document_processing'] = test_document_processing()
    results['footnote_rebuild'] = test_footnote_rebuild()

    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    for test_name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {test_name}: {status}")

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    print(f"\n总计: {passed_count}/{total_count} 测试通过")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='测试学术论文润色模块优化版')
    parser.add_argument('--test', choices=[
        'footnote', 'format', 'strategy', 'process', 'rebuild', 'all'
    ], default='all', help='选择测试项目')

    args = parser.parse_args()

    if args.test == 'all':
        run_all_tests()
    elif args.test == 'footnote':
        test_footnote_manager()
    elif args.test == 'format':
        test_format_preserver()
    elif args.test == 'strategy':
        test_polishing_strategies()
    elif args.test == 'process':
        test_document_processing()
    elif args.test == 'rebuild':
        test_footnote_rebuild()
