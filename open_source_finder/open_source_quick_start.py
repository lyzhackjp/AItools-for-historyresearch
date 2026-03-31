"""
OpenSourceFinder 快速启动脚本

快速搜索并优化指定模块的便捷脚本
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from open_source_finder import OpenSourceFinder


def quick_optimize(module_name: str, context: str, apply_changes: bool = False):
    """
    快速优化指定模块

    Args:
        module_name: 模块名称（如 'ocr_processor', 'ner_processor'）
        context: 应用上下文描述
        apply_changes: 是否直接应用更改
    """
    print(f"🔍 开始优化 {module_name} 模块")
    print(f"📝 上下文: {context}")
    print("=" * 60)

    finder = OpenSourceFinder(api_provider='qwen', test_mode=True)

    print("\n📡 步骤 1/5: 搜索开源模块...")
    results = finder.search_all(module_name=module_name, context=context)
    print(f"   ✓ 搜索完成")
    print(f"   - GitHub 仓库: {results.total_github_results} 个")
    print(f"   - HuggingFace 模型: {results.total_huggingface_results} 个")

    print("\n📊 步骤 2/5: 过滤和排序...")
    filtered = finder.rank_and_filter(results, min_stars=50, min_downloads=1000)
    print(f"   ✓ 过滤完成")
    print(f"   - 高质量 GitHub 仓库: {len(filtered.github_repos)} 个")
    print(f"   - 高质量 HuggingFace 模型: {len(filtered.huggingface_models)} 个")

    print("\n📝 步骤 3/5: 生成优化整合报告...")
    report = finder.generate_integration_report(filtered, module_name, context)
    print(f"   ✓ 报告生成完成")
    print(f"\n   报告摘要:")
    print(f"   {report.summary[:200]}...")

    print("\n💾 步骤 4/5: 保存结果...")
    results_file = f"{module_name}_search_results.json"
    report_file = f"{module_name}_optimization_report.json"

    finder.save_search_results(filtered, results_file)
    finder.save_report(report, report_file)
    print(f"   ✓ 结果已保存")
    print(f"   - 搜索结果: {results_file}")
    print(f"   - 整合报告: {report_file}")

    print("\n🔧 步骤 5/5: 生成优化计划...")
    target_module = f"modules/{module_name}.py"
    optimization_plan = finder.execute_optimization(
        report,
        target_module_path=target_module,
        apply_changes=apply_changes
    )
    print(f"   ✓ 优化计划已生成")
    print(f"   - 计划实施的更改: {len(optimization_plan['changes_proposed'])} 项")

    print("\n" + "=" * 60)
    print("✅ 优化搜索完成！")
    print("=" * 60)
    print("\n下一步:")
    print("1. 查看生成的优化报告")
    print("2. 评估推荐的仓库和模型")
    print("3. 制定具体的实施计划")
    print(f"4. 如需自动应用更改，请运行:")
    print(f"   quick_optimize('{module_name}', '{context}', apply_changes=True)")

    return {
        'results': filtered,
        'report': report,
        'optimization_plan': optimization_plan
    }


def main():
    """主函数"""
    if len(sys.argv) > 1:
        module_name = sys.argv[1]
        context = sys.argv[2] if len(sys.argv) > 2 else f"{module_name}模块优化"
        apply = '--apply' in sys.argv
    else:
        print("\n🔧 OpenSourceFinder 快速启动")
        print("=" * 60)
        print("\n用法:")
        print("  python open_source_quick_start.py <模块名> <上下文> [--apply]")
        print("\n示例:")
        print("  python open_source_quick_start.py ocr_processor '日文OCR识别'")
        print("  python open_source_quick_start.py ner_processor '日文NER' --apply")
        print("\n支持的模块:")
        print("  - ocr_processor (OCR识别)")
        print("  - ner_processor (命名实体识别)")
        print("  - pdf_processor (PDF处理)")
        print("  - doc_processor (文档处理)")
        print("  - llm_client (LLM客户端)")
        print("  - academic_note_generator (学术笔记生成)")
        print("\n按回车键使用默认示例...")

        module_name = 'ocr_processor'
        context = '日文史料OCR识别优化'

    quick_optimize(module_name, context)


if __name__ == '__main__':
    main()
