"""
Stage 4: 史料考察

分析引文网络 + 论文逻辑审视

输入：
    project.literature: List[PaperRecord] — 文献列表
    project.paper_draft: str — 论文草稿（Stage 5 产出，可选）
    project.language: str — 主要语言

输出：
    project.citation_network: CitationNetwork
    project.key_source_ids: List[str] — 核心文献 ID 列表
    project.outline_review: OutlineReview — 论文逻辑审视报告（草稿阶段）

依赖模块：
    modules.citation_network_analyzer.CitationNetworkAnalyzer
    modules.reverse_outline_analyzer.ReverseOutlineAnalyzer
"""

import sys
import os
from typing import List, Dict, Any, Optional

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..')
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import (
    ResearchProject, PaperRecord, CitationNetwork, OutlineReview
)


class Stage4Examine:
    """
    Stage 4: 史料考察

    使用方法：
        stage = Stage4Examine(project)
        result = stage.run()

        # 只分析引文网络
        network = stage.analyze_citation_network(literature)

        # 只审视论文逻辑
        review = stage.analyze_paper_outline(paper_draft)
    """

    NAME = "examine"
    STAGE_NUM = 4

    def __init__(self, project: ResearchProject):
        self.project = project
        self.cna = None  # CitationNetworkAnalyzer
        self.roa = None  # ReverseOutlineAnalyzer

    def _get_citation_analyzer(self):
        """延迟创建引文网络分析器"""
        if self.cna is None:
            from modules.citation_network_analyzer import CitationNetworkAnalyzer
            self.cna = CitationNetworkAnalyzer()
        return self.cna

    def _get_outline_analyzer(self):
        """延迟创建逆向大纲审视器"""
        if self.roa is None:
            from modules.reverse_outline_analyzer import ReverseOutlineAnalyzer
            self.roa = ReverseOutlineAnalyzer(
                api_provider="qwen",
                test_mode=False
            )
        return self.roa

    def run(self, **kwargs) -> Dict[str, Any]:
        """
        执行 Stage 4：史料考察

        Returns:
            Dict 含 'citation_network', 'key_sources', 'outline_review'
        """
        print(f"[Stage 4] 开始史料考察")
        print(f"[Stage 4] 文献: {len(self.project.literature)} 篇")

        self.project.mark_stage_start(self.STAGE_NUM)

        results = {}

        # ── 4a. 引文网络分析 ───────────────────────────────────
        if self.project.literature:
            network_result = self.analyze_citation_network(self.project.literature)
            results['citation_network'] = network_result['network']
            results['key_sources'] = network_result['key_source_ids']
            self.project.citation_network = network_result['network']
            self.project.key_source_ids = network_result['key_source_ids']
            print(f"[Stage 4] 引文网络: {len(network_result['network'].nodes)} 节点, "
                  f"{len(network_result['network'].edges)} 边")
            print(f"[Stage 4] 核心文献: {len(network_result['key_source_ids'])} 篇")
        else:
            print("[Stage 4] 无文献可分析引文网络")
            results['citation_network'] = None
            results['key_sources'] = []

        # ── 4b. 论文逻辑审视（草稿阶段可选）─────────────────────
        outline_review = None
        if self.project.paper_draft and len(self.project.paper_draft) > 200:
            try:
                outline_review = self.analyze_paper_outline(self.project.paper_draft)
                results['outline_review'] = outline_review
                self.project.outline_review = outline_review
                print(f"[Stage 4] 逻辑审视完成")
            except Exception as e:
                print(f"[Stage 4] 逻辑审视失败: {e}")
                results['outline_review'] = None
        else:
            print("[Stage 4] 无论文草稿可审视（Stage 5 未完成），跳过")

        self.project.mark_stage_done(self.STAGE_NUM)

        print(f"[Stage 4] 完成！")
        return results

    def analyze_citation_network(
        self,
        literature: List[PaperRecord]
    ) -> Dict[str, Any]:
        """
        分析引文网络

        Args:
            literature: 文献列表

        Returns:
            Dict 含 'network' (CitationNetwork) 和 'key_source_ids' (List[str])
        """
        print(f"[Stage 4] 分析引文网络: {len(literature)} 篇文献")

        cna = self._get_citation_analyzer()
        lang = self._detect_language()

        # ── 构建引文节点 ────────────────────────────────────────
        nodes = []
        for paper in literature:
            nodes.append({
                'id': paper.id,
                'title': paper.title,
                'authors': paper.authors,
                'year': paper.year,
                'cited_by_count': 0,  # CrossRef 不提供引用数，标记为 0
                'is_core': False,
                'source': paper.source,
                'journal': paper.journal,
                'abstract': (paper.abstract or '')[:200],
            })

        # ── 简单核心文献识别 ────────────────────────────────────
        # 策略：被多篇文献引用（从同主题推断）+ 年份早的经典文献
        # 由于无真实引用数据，使用启发式：
        # - 来自权威期刊 (Nature/Science 类 → 降权，因为是历史)
        # - 年份早 (15年以上) → 经典文献
        # - 有 DOI/URL → 质量有保障
        current_year = 2026
        key_ids = []

        for node in nodes:
            score = 0
            # 经典文献加分
            try:
                year = int(node['year']) if node['year'] else 0
                if 0 < year < current_year - 15:
                    score += (current_year - year) // 5  # 越老分越高
                if year >= current_year - 5:
                    score += 2  # 前沿研究加分
            except:
                pass

            # 有 DOI 保障
            if node.get('id') and len(str(node['id'])) > 5:
                score += 1

            node['network_score'] = score

        # 取分数最高的前 20% 作为核心文献
        if nodes:
            threshold = sorted((n['network_score'] for n in nodes), reverse=True)
            if threshold:
                cutoff = threshold[max(0, len(threshold) // 5 - 1)]
                for node in nodes:
                    if node['network_score'] >= cutoff and node['network_score'] > 0:
                        node['is_core'] = True
                        key_ids.append(node['id'])

        # ── 从摘要中提取引用关系 ────────────────────────────────
        edges = []
        cited_titles = {n['title'].lower(): n['id'] for n in nodes}

        for i, paper in enumerate(literature):
            abstract = (paper.abstract or '').lower()
            # 简单检测：paper i 被 paper j 引用 → 检测 paper i 的标题词是否在 paper j 的摘要中
            for j, other in enumerate(literature):
                if i == j:
                    continue
                other_abstract = (other.abstract or '').lower()
                # 如果 other 的摘要提到 paper i 的关键词（标题词）
                title_words = [w for w in paper.title.split() if len(w) > 4]
                matches = sum(1 for w in title_words if w in other_abstract)
                if matches >= 2:  # 至少 2 个关键词匹配
                    edges.append({
                        'from_id': other.id,
                        'to_id': paper.id,
                        'type': 'cites',
                    })

        # ── 构建 CitationNetwork ────────────────────────────────
        network = CitationNetwork(
            nodes=nodes,
            edges=edges[:500],  # 限制边数量
            key_source_ids=key_ids,
            orphan_ids=[n['id'] for n in nodes if not any(e['to_id'] == n['id'] for e in edges)],
        )

        print(f"[Stage 4] 引文网络: {len(nodes)} 节点, {len(edges)} 边, {len(key_ids)} 核心")
        if key_ids:
            key_titles = [n['title'] for n in nodes if n['id'] in key_ids[:5]]
            for t in key_titles:
                print(f"  ★ {t[:60]}")

        return {
            'network': network,
            'key_source_ids': key_ids,
        }

    def _detect_language(self) -> str:
        """检测项目语言"""
        lang = self.project.language.lower()
        if lang in ('en', 'english'):
            return 'english'
        if lang in ('ja', 'japanese'):
            return 'japanese'
        return 'chinese'

    def analyze_paper_outline(self, paper_text: str) -> Optional[OutlineReview]:
        """
        逆向审视论文逻辑

        Args:
            paper_text: 论文全文

        Returns:
            OutlineReview: 审视报告
        """
        print(f"[Stage 4] 审视论文逻辑: {len(paper_text)} 字符")

        try:
            roa = self._get_outline_analyzer()
            lang = self._detect_language()

            # 调用逆向大纲审视器
            result = roa.analyze(paper_text, language=lang)

            # 解析结果
            review = self._parse_outline_result(result, paper_text)
            return review

        except Exception as e:
            print(f"[Stage 4] 逻辑审视失败: {e}")
            return self._fallback_outline_review(paper_text)

    def _parse_outline_result(self, result: Any, paper_text: str) -> OutlineReview:
        """解析 OutlineAnalyzer 输出"""
        if isinstance(result, dict):
            section_word_counts = result.get('section_word_counts', {})
            section_ratios = result.get('section_ratios', {})
            logical_gaps = result.get('logical_gaps', [])
            deviation_flags = result.get('deviation_flags', [])
            suggestions = result.get('suggestions', [])
        else:
            # 结构未知，尝试从 result 提取基本信息
            section_word_counts = {}
            section_ratios = {}
            logical_gaps = []
            deviation_flags = []
            suggestions = []

        return OutlineReview(
            section_word_counts=section_word_counts,
            section_ratios=section_ratios,
            logical_gaps=logical_gaps,
            deviation_flags=deviation_flags,
            suggestions=suggestions,
        )

    def _fallback_outline_review(self, paper_text: str) -> OutlineReview:
        """
        兜底的论文审视（当 LLM 不可用时）
        基于规则的简单分析
        """
        import re

        # 识别章节
        section_headers = {
            'abstract': r'(摘要|Abstract)',
            'introduction': r'(序章|导论|Introduction|前言)',
            'literature_review': r'(文献综述|研究回顾|Literature Review)',
            'methodology': r'(研究方法|Methodology)',
            'analysis': r'(分析|Analysis|正文)',
            'discussion': r'(讨论|Discussion)',
            'conclusion': r'(结论|Conclusion|结语)',
            'references': r'(参考文献|References)',
        }

        section_word_counts = {}
        sections_found = set()

        for section_name, pattern in section_headers.items():
            matches = list(re.finditer(pattern, paper_text, re.IGNORECASE))
            if matches:
                start = matches[0].end()
                # 找下一个标题或参考文献之前
                next_pattern = '|'.join(section_headers.values())
                next_match = re.search(next_pattern, paper_text[start:], re.IGNORECASE)
                if next_match:
                    end = start + next_match.start()
                else:
                    end = len(paper_text)
                section_text = paper_text[start:end]
                word_count = len(section_text)
                section_word_counts[section_name] = word_count
                sections_found.add(section_name)

        # 计算比例
        total = sum(section_word_counts.values()) or 1
        section_ratios = {
            k: round(v / total, 3) for k, v in section_word_counts.items()
        }

        # 逻辑缺口检测
        logical_gaps = []
        if 'abstract' not in sections_found:
            logical_gaps.append('缺少摘要章节')
        if 'introduction' not in sections_found:
            logical_gaps.append('缺少引言章节')
        if 'conclusion' not in sections_found:
            logical_gaps.append('缺少结论章节')
        if 'literature_review' not in sections_found:
            logical_gaps.append('缺少文献综述章节')

        # 偏离检测
        deviation_flags = []
        for section, ratio in section_ratios.items():
            if section in ('references',) and ratio > 0.4:
                deviation_flags.append(f'{section} 章节占比过高 ({ratio:.1%})')

        suggestions = []
        if logical_gaps:
            suggestions.append('补充缺失章节：' + ', '.join(logical_gaps))
        if not sections_found:
            suggestions.append('无法识别论文章节结构，请检查格式')

        return OutlineReview(
            section_word_counts=section_word_counts,
            section_ratios=section_ratios,
            logical_gaps=logical_gaps,
            deviation_flags=deviation_flags,
            suggestions=suggestions,
        )

    def print_review_summary(self, review: OutlineReview) -> None:
        """打印审视报告摘要"""
        if not review:
            return

        print("\n[Stage 4] 论文审视报告")
        print("─" * 40)

        if review.section_word_counts:
            print("\n章节字数分布:")
            for sec, count in review.section_word_counts.items():
                ratio = review.section_ratios.get(sec, 0)
                print(f"  {sec}: {count} 字 ({ratio:.1%})")

        if review.logical_gaps:
            print("\n逻辑缺口:")
            for gap in review.logical_gaps:
                print(f"  ! {gap}")

        if review.deviation_flags:
            print("\n偏离警告:")
            for flag in review.deviation_flags:
                print(f"  ! {flag}")

        if review.suggestions:
            print("\n改进建议:")
            for sug in review.suggestions:
                print(f"  → {sug}")
