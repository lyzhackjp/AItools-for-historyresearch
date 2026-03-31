"""
OCR 模块优化测试脚本

测试使用 OpenSourceFinder 优化 ocr_processor 模块的完整流程
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from open_source_finder import OpenSourceFinder


def test_ocr_optimization():
    """测试 OCR 模块的优化流程"""
    print("=" * 70)
    print("OCR 模块优化测试")
    print("=" * 70)

    finder = OpenSourceFinder(api_provider='qwen', test_mode=True)

    print("\n📡 第一步: 搜索开源 OCR 解决方案")
    print("-" * 70)

    keywords = [
        'ocr',
        'japanese ocr',
        'handwriting recognition',
        'easyocr',
        'paddleocr',
        'tesseract improvement'
    ]

    results = finder.search_all(
        module_name='ocr_processor',
        context='日文史料OCR识别优化',
        keywords=keywords
    )

    print(f"\n搜索结果汇总:")
    print(f"  • GitHub 仓库: {results.total_github_results} 个")
    print(f"  • HuggingFace 模型: {results.total_huggingface_results} 个")
    print(f"  • 使用的关键词: {results.search_keywords}")

    print("\n📊 第二步: 过滤高质量项目")
    print("-" * 70)

    filtered = finder.rank_and_filter(
        results,
        min_stars=100,
        min_downloads=5000
    )

    print(f"\n过滤后结果:")
    print(f"  • GitHub 仓库: {len(filtered.github_repos)} 个")
    print(f"  • HuggingFace 模型: {len(filtered.huggingface_models)} 个")

    print("\nTop 3 GitHub 仓库:")
    for i, repo in enumerate(filtered.github_repos[:3], 1):
        print(f"\n  {i}. {repo.full_name}")
        print(f"     ⭐ Stars: {repo.stars:,}")
        print(f"     🍴 Forks: {repo.forks:,}")
        print(f"     📊 综合评分: {repo.score}")
        print(f"     🔗 {repo.url}")
        print(f"     📝 {repo.description[:100]}...")

    print("\nTop 3 HuggingFace 模型:")
    for i, model in enumerate(filtered.huggingface_models[:3], 1):
        print(f"\n  {i}. {model.model_name}")
        print(f"     📥 Downloads: {model.downloads:,}")
        print(f"     ❤️ Likes: {model.likes:,}")
        print(f"     📊 综合评分: {model.score}")
        print(f"     🔗 https://huggingface.co/{model.model_id}")
        print(f"     🏷️ Pipeline: {model.pipeline_tag}")
        print(f"     📝 {model.description[:100]}...")

    print("\n📝 第三步: 生成优化整合报告")
    print("-" * 70)

    report = finder.generate_integration_report(
        filtered,
        module_name='ocr_processor',
        context='日文史料OCR识别优化'
    )

    print(f"\n报告摘要:")
    print(f"  {report.summary}")

    print(f"\nGitHub 仓库推荐:")
    for rec in report.github_recommendations[:3]:
        print(f"  {rec['rank']}. {rec['name']}")
        print(f"     评分: {rec['score']} | 难度: {rec['integration_difficulty']}")
        print(f"     URL: {rec['url']}")

    print(f"\nHuggingFace 模型推荐:")
    for rec in report.huggingface_recommendations[:3]:
        print(f"  {rec['rank']}. {rec['name']}")
        print(f"     下载量: {rec['stars_downloads']:,} | 评分: {rec['score']}")
        print(f"     URL: {rec['url']}")

    print(f"\n整合建议:")
    for i, suggestion in enumerate(report.integration_suggestions[:3], 1):
        print(f"  {i}. {suggestion['suggestion'][:100]}...")
        print(f"     优先级: {suggestion['priority']}")

    print(f"\n优先级行动计划:")
    for action in report.priority_actions:
        print(f"  • {action}")

    print(f"\n工作量估算:")
    for level, estimate in report.estimated_effort.items():
        print(f"  • {level}: {estimate}")

    print("\n💾 第四步: 保存结果")
    print("-" * 70)

    finder.save_search_results(filtered, 'ocr_optimization_search_results.json')
    print("  ✓ 搜索结果已保存: ocr_optimization_search_results.json")

    finder.save_report(report, 'ocr_optimization_integration_report.json')
    print("  ✓ 整合报告已保存: ocr_optimization_integration_report.json")

    print("\n🔧 第五步: 准备优化实施")
    print("-" * 70)

    optimization_plan = finder.execute_optimization(
        report,
        target_module_path='modules/ocr_processor.py',
        apply_changes=False
    )

    print(f"\n优化计划状态: {optimization_plan['status']}")

    print(f"\n提议的优化措施:")
    for i, change in enumerate(optimization_plan['changes_proposed'], 1):
        print(f"\n  {i}. {change['type'].upper()}")
        print(f"     来源: {change['source']}")
        print(f"     描述: {change['description']}")
        print(f"     URL: {change['url']}")

    print("\n" + "=" * 70)
    print("✅ OCR 模块优化测试完成！")
    print("=" * 70)

    print("\n📋 下一步建议:")
    print("  1. 仔细审查生成的优化报告")
    print("  2. 评估推荐的仓库和模型与现有系统的兼容性")
    print("  3. 优先考虑高评分、低难度的整合方案")
    print("  4. 制定详细的实施计划和时间表")
    print("  5. 如需自动应用更改，请设置 apply_changes=True")

    return {
        'results': filtered,
        'report': report,
        'optimization_plan': optimization_plan
    }


def test_real_github_search():
    """测试实际的 GitHub 搜索（非测试模式）"""
    print("\n" + "=" * 70)
    print("真实 GitHub API 测试")
    print("=" * 70)

    github_token = os.getenv('GITHUB_TOKEN')

    finder = OpenSourceFinder(test_mode=False, github_token=github_token)

    print("\n搜索 GitHub 上的 OCR 相关项目...")

    results = finder.search_github('easyocr python', limit=5)

    print(f"\n找到 {len(results)} 个仓库:")
    for i, repo in enumerate(results, 1):
        print(f"\n  {i}. {repo.full_name}")
        print(f"     ⭐ {repo.stars:,} | 🍴 {repo.forks:,} | 📊 {repo.score}")
        print(f"     📝 {repo.description[:80]}...")

    return results


if __name__ == '__main__':
    test_ocr_optimization()

    print("\n\n提示: 要测试真实的 GitHub API，请设置 GITHUB_TOKEN 环境变量")
    print("export GITHUB_TOKEN='your-token'  # Linux/Mac")
    print("$env:GITHUB_TOKEN='your-token'    # Windows PowerShell")
