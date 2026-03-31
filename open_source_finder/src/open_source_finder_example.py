"""
OpenSourceFinder 使用示例

展示如何使用 OpenSourceFinder 模块搜索 GitHub 和 HuggingFace 上的开源模块，
并生成优化整合报告。
"""

from open_source_finder import OpenSourceFinder, SearchResult, IntegrationReport
import json


def example_basic_search():
    """基础搜索示例"""
    print("=" * 60)
    print("示例 1: 基础搜索功能")
    print("=" * 60)

    finder = OpenSourceFinder(api_provider='qwen', test_mode=True)

    results = finder.search_all(
        module_name='ocr_processor',
        context='日文史料OCR识别',
        keywords=['ocr', 'japanese ocr', 'handwriting recognition']
    )

    print(f"\n搜索到 {results.total_github_results} 个 GitHub 仓库")
    print(f"搜索到 {results.total_huggingface_results} 个 HuggingFace 模型")

    print("\nTop 5 GitHub 仓库:")
    for i, repo in enumerate(results.github_repos[:5], 1):
        print(f"{i}. {repo.full_name}")
        print(f"   ⭐ {repo.stars} | 🍴 {repo.forks} | 📊 Score: {repo.score}")
        print(f"   {repo.description[:80]}...")

    print("\nTop 5 HuggingFace 模型:")
    for i, model in enumerate(results.huggingface_models[:5], 1):
        print(f"{i}. {model.model_name}")
        print(f"   📥 {model.downloads:,} | ❤️ {model.likes} | 📊 Score: {model.score}")
        print(f"   {model.description[:80]}...")

    return results


def example_filter_and_rank():
    """过滤和排序示例"""
    print("\n" + "=" * 60)
    print("示例 2: 结果过滤和排序")
    print("=" * 60)

    finder = OpenSourceFinder(test_mode=True)

    results = finder.search_all(
        module_name='ner_processor',
        context='日文命名实体识别'
    )

    filtered = finder.rank_and_filter(
        results,
        min_stars=100,
        min_downloads=5000
    )

    print(f"\n过滤后结果:")
    print(f"- GitHub 仓库: {len(filtered.github_repos)} 个")
    print(f"- HuggingFace 模型: {len(filtered.huggingface_models)} 个")

    print("\n高质量 GitHub 仓库:")
    for repo in filtered.github_repos[:3]:
        print(f"  • {repo.full_name} (Score: {repo.score})")

    print("\n高质量 HuggingFace 模型:")
    for model in filtered.huggingface_models[:3]:
        print(f"  • {model.model_name} (Score: {model.score})")

    return filtered


def example_generate_report():
    """生成整合报告示例"""
    print("\n" + "=" * 60)
    print("示例 3: 生成优化整合报告")
    print("=" * 60)

    finder = OpenSourceFinder(api_provider='qwen', test_mode=True)

    results = finder.search_all(
        module_name='ocr_processor',
        context='日文史料OCR识别'
    )

    report = finder.generate_integration_report(
        results,
        module_name='ocr_processor',
        context='日文史料OCR识别'
    )

    print(f"\n报告摘要:\n{report.summary}")

    print("\nGitHub 推荐:")
    for rec in report.github_recommendations[:3]:
        print(f"  {rec['rank']}. {rec['name']}")
        print(f"     难度: {rec['integration_difficulty']} | 评分: {rec['score']}")

    print("\nHuggingFace 推荐:")
    for rec in report.huggingface_recommendations[:3]:
        print(f"  {rec['rank']}. {rec['name']}")
        print(f"     下载量: {rec['stars_downloads']:,} | 评分: {rec['score']}")

    print("\n整合建议:")
    for i, suggestion in enumerate(report.integration_suggestions[:3], 1):
        print(f"  {i}. {suggestion['suggestion'][:80]}...")

    print("\n优先级行动:")
    for action in report.priority_actions:
        print(f"  • {action}")

    print("\n工作量估算:")
    for level, estimate in report.estimated_effort.items():
        print(f"  {level}: {estimate}")

    return report


def example_save_results():
    """保存结果示例"""
    print("\n" + "=" * 60)
    print("示例 4: 保存搜索结果和报告")
    print("=" * 60)

    finder = OpenSourceFinder(api_provider='qwen', test_mode=True)

    results = finder.search_all(
        module_name='ner_processor',
        context='日文命名实体识别'
    )

    report = finder.generate_integration_report(
        results,
        module_name='ner_processor',
        context='日文命名实体识别'
    )

    finder.save_search_results(results, 'search_results.json')
    print("\n搜索结果已保存到: search_results.json")

    finder.save_report(report, 'integration_report.json')
    print("整合报告已保存到: integration_report.json")

    print("\n提示: 可以查看保存的 JSON 文件获取详细信息")


def example_optimization_workflow():
    """完整优化工作流示例"""
    print("\n" + "=" * 60)
    print("示例 5: 完整的优化工作流")
    print("=" * 60)

    finder = OpenSourceFinder(api_provider='qwen', test_mode=True)

    print("\n步骤 1: 搜索开源模块...")
    results = finder.search_all(
        module_name='ocr_processor',
        context='日文史料OCR识别'
    )
    print(f"✓ 搜索完成: {results.total_github_results} GitHub + {results.total_huggingface_results} HuggingFace")

    print("\n步骤 2: 过滤和排序...")
    filtered = finder.rank_and_filter(results, min_stars=50, min_downloads=1000)
    print(f"✓ 过滤完成: {len(filtered.github_repos)} GitHub + {len(filtered.huggingface_models)} HuggingFace")

    print("\n步骤 3: 生成优化整合报告...")
    report = finder.generate_integration_report(
        filtered,
        module_name='ocr_processor',
        context='日文史料OCR识别'
    )
    print(f"✓ 报告生成完成")

    print("\n步骤 4: 保存结果...")
    finder.save_search_results(filtered, 'ocr_optimization_search.json')
    finder.save_report(report, 'ocr_optimization_report.json')
    print(f"✓ 结果已保存")

    print("\n步骤 5: 准备优化实施...")
    target_module = 'modules/ocr_processor.py'
    optimization_plan = finder.execute_optimization(
        report,
        target_module_path=target_module,
        apply_changes=False
    )

    print(f"\n优化计划状态: {optimization_plan['status']}")
    print(f"计划实施的更改数量: {len(optimization_plan['changes_proposed'])}")

    if optimization_plan.get('errors'):
        print("\n遇到的问题:")
        for error in optimization_plan['errors']:
            print(f"  ⚠ {error}")

    print("\n完整的优化工作流已完成！")
    print("提示: 查看保存的 JSON 文件获取详细信息")


def example_custom_search():
    """自定义搜索示例"""
    print("\n" + "=" * 60)
    print("示例 6: 自定义搜索")
    print("=" * 60)

    finder = OpenSourceFinder(test_mode=True)

    print("\n仅搜索 GitHub...")
    github_results = finder.search_github(
        query='japanese ocr deep learning',
        limit=10,
        language='python'
    )

    print(f"\n找到 {len(github_results)} 个 GitHub 仓库:")
    for repo in github_results[:5]:
        print(f"  • {repo.full_name} (⭐ {repo.stars})")

    print("\n仅搜索 HuggingFace...")
    hf_results = finder.search_huggingface(
        query='japanese ocr',
        limit=10
    )

    print(f"\n找到 {len(hf_results)} 个 HuggingFace 模型:")
    for model in hf_results[:5]:
        print(f"  • {model.model_name} (📥 {model.downloads:,})")


if __name__ == '__main__':
    print("OpenSourceFinder 使用示例")
    print("=" * 60)

    example_basic_search()
    example_filter_and_rank()
    example_generate_report()
    example_save_results()
    example_optimization_workflow()
    example_custom_search()

    print("\n" + "=" * 60)
    print("所有示例执行完成！")
    print("=" * 60)
