"""
Stage 6: 论文修改润色

输入：
    project.paper_draft: str — 论文草稿（Stage 5 产出）
    project.outline_review: OutlineReview — 审视报告（Stage 4 产出，可选）
    project.language: str — 主要语言

输出：
    project.polished_draft: str — 精简后草稿
    project.style_transferred_draft: str — 文风调整版（可选）
    project.outline_review: OutlineReview — 更新后的逻辑审视报告

依赖模块：
    modules.paper_polisher.PaperPolisher
    modules.style_transfer.StyleTransfer
    modules.reverse_outline_analyzer.ReverseOutlineAnalyzer
"""

import sys
import os
from typing import Dict, Any, Optional

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..')
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import ResearchProject, OutlineReview


class Stage6Polish:
    """
    Stage 6: 论文修改润色

    使用方法：
        stage = Stage6Polish(project)
        result = stage.run()

        # 只精简
        polished = stage.polish_paper(paper_text)

        # 只文风迁移
        styled = stage.transfer_style(paper_text, target_author="G.R. Elton")
    """

    NAME = "polish"
    STAGE_NUM = 6

    def __init__(self, project: ResearchProject):
        self.project = project
        self.polisher = None
        self.style_transfer = None
        self.outline_analyzer = None

    def _get_polisher(self):
        """延迟创建论文精简器"""
        if self.polisher is None:
            from modules.paper_polisher import PaperPolisher
            self.polisher = PaperPolisher(api_provider="qwen")
        return self.polisher

    def _get_style_transfer(self):
        """延迟创建文风迁移器"""
        if self.style_transfer is None:
            from modules.style_transfer import StyleTransfer
            self.style_transfer = StyleTransfer(api_provider="qwen", test_mode=False)
        return self.style_transfer

    def _get_outline_analyzer(self):
        """延迟创建逆向大纲审视器"""
        if self.outline_analyzer is None:
            from modules.reverse_outline_analyzer import ReverseOutlineAnalyzer
            self.outline_analyzer = ReverseOutlineAnalyzer(
                api_provider="qwen",
                test_mode=False
            )
        return self.outline_analyzer

    def run(self, **kwargs) -> Dict[str, Any]:
        """
        执行 Stage 6：论文修改润色

        Returns:
            Dict 含 'polished_draft', 'style_transferred_draft', 'outline_review'
        """
        if not self.project.paper_draft:
            print("[Stage 6] 无论文草稿可润色（Stage 5 未完成），跳过")
            self.project.mark_stage_skipped()
            return {}

        print(f"[Stage 6] 开始论文润色 | 原文: {len(self.project.paper_draft)} 字符")
        self.project.mark_stage_start(self.STAGE_NUM)

        results = {}

        # ── 6a. 精简论文 ────────────────────────────────────────
        try:
            polished = self.polish_paper(self.project.paper_draft)
            self.project.polished_draft = polished
            results['polished_draft'] = polished
            print(f"[Stage 6] 精简完成: {len(self.project.paper_draft)} → {len(polished)} 字符 "
                  f"({len(polished)/max(len(self.project.paper_draft),1):.1%})")
        except Exception as e:
            print(f"[Stage 6] 精简失败: {e}，保留原文")
            self.project.polished_draft = self.project.paper_draft
            results['polished_draft'] = self.project.paper_draft

        # ── 6b. 文风迁移（可选）────────────────────────────────
        target_style = kwargs.get('target_style', '')
        if target_style:
            try:
                styled = self.transfer_style(self.project.paper_draft, target_style=target_style)
                self.project.style_transferred_draft = styled
                results['style_transferred_draft'] = styled
                print(f"[Stage 6] 文风迁移完成: {len(styled)} 字符")
            except Exception as e:
                print(f"[Stage 6] 文风迁移失败: {e}，跳过")
                results['style_transferred_draft'] = None
        else:
            print("[Stage 6] 未指定 target_style，跳过文风迁移")
            results['style_transferred_draft'] = None

        # ── 6c. 更新逻辑审视 ───────────────────────────────────
        try:
            review = self._recheck_outline(self.project.paper_draft)
            self.project.outline_review = review
            results['outline_review'] = review
        except Exception as e:
            print(f"[Stage 6] 逻辑审视失败: {e}")

        self.project.mark_stage_done(self.STAGE_NUM)
        print(f"[Stage 6] 完成！")
        return results

    def polish_paper(self, paper_text: str) -> str:
        """
        精简论文（删除冗余内容）

        Args:
            paper_text: 原始论文

        Returns:
            str: 精简后的论文
        """
        print("[Stage 6] 开始精简论文...")

        # 如果太短，直接返回
        if len(paper_text) < 500:
            print("[Stage 6] 论文过短，跳过精简")
            return paper_text

        # 按段落分割处理
        paragraphs = self._split_paragraphs(paper_text)
        polished_paras = []
        total_deleted = 0

        try:
            polisher = self._get_polisher()
            polisher._init_llm_client()
        except Exception as e:
            print(f"[Stage 6] LLM 客户端初始化失败: {e}，使用简化精简")
            return self._simple_polish(paper_text)

        for i, para in enumerate(paragraphs):
            if len(para) < 50:
                polished_paras.append(para)
                continue

            try:
                result = polisher.polish_paragraph(para)
                modified = result[0]  # (modified_text, changes)
                polished_paras.append(modified)

                # 统计删除
                if len(result) > 1 and result[1]:
                    changes = result[1]
                    if isinstance(changes, list):
                        total_deleted += len(changes)
            except Exception as e:
                # 单段失败保留原文
                polished_paras.append(para)

            if (i + 1) % 20 == 0:
                print(f"[Stage 6] 精简进度: {i+1}/{len(paragraphs)}")

        polished_text = '\n\n'.join(polished_paras)
        print(f"[Stage 6] 精简统计: 删除 {total_deleted} 处冗余")
        return polished_text

    def _split_paragraphs(self, text: str) -> list:
        """按段落分割文本"""
        # 优先用双换行分割
        paras = text.split('\n\n')
        if len(paras) > 1:
            return [p.strip() for p in paras if p.strip()]
        # 否则按单换行
        return [p.strip() for p in text.split('\n') if p.strip()]

    def _simple_polish(self, paper_text: str) -> str:
        """
        简化精简（LLM 不可用时的兜底）
        基于规则的简单冗余检测
        """
        import re

        text = paper_text

        # 删除连续重复的词（如 "非常非常" → "非常"）
        text = re.sub(r'(.{2,})\1{2,}', r'\1\1', text)

        # 删除连续空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 删除句末连续重复的句子（简单启发式）
        # 这是一个很粗略的实现
        lines = text.split('\n\n')
        deduped = []
        seen = set()
        for line in lines:
            key = line.lower().strip()[:50]
            if key and key not in seen:
                seen.add(key)
                deduped.append(line)
            elif key:
                pass  # 重复行跳过

        return '\n\n'.join(deduped)

    def transfer_style(
        self,
        paper_text: str,
        target_style: str = "",
        style_reference: str = ""
    ) -> str:
        """
        文风迁移/调整

        Args:
            paper_text: 原始论文
            target_style: 目标风格关键词（如 'academic_history', 'historiographical'）
            style_reference: 参考风格文本（可选）

        Returns:
            str: 风格调整后的论文
        """
        print(f"[Stage 6] 开始文风迁移: {target_style}")

        try:
            st = self._get_style_transfer()
            st._init_llm_client()
        except Exception as e:
            print(f"[Stage 6] StyleTransfer LLM 初始化失败: {e}，跳过")
            return paper_text

        # 确定目标风格的描述
        style_descriptions = {
            'academic_history': '学术历史论文风格：严谨的论证逻辑，使用历史学专业术语，避免口语化表达',
            'historiographical': 'Historiographical review style: 主要回顾史学史和学术流派，而非原创论证',
            'source_analysis': '史料分析风格：注重一手史料的批判性分析，强调史料鉴定的过程',
            'narrative': '叙事史风格：在严谨论证基础上注重叙事流畅性，可读性更强',
        }

        style_desc = style_descriptions.get(target_style, target_style or '学术历史论文风格')

        # 构建 prompt
        prompt = f"""请将以下学术论文的文风调整为：{style_desc}

要求：
1. 保持所有核心学术内容和论点
2. 调整句式结构和词汇选择以匹配目标风格
3. 保留所有引用和注释
4. 翻译或改写时不改变学术准确性

原文：

{paper_text}

改写后的论文："""

        try:
            client = st.llm_client
            response = client._call_llm(prompt, max_tokens=4000)
            # 清理响应
            response = response.strip()
            if response.startswith('```'):
                response = response.split('```')[1]
                if response.startswith('markdown') or response.startswith('md'):
                    response = response[markdown_len:]
            return response.strip()
        except Exception as e:
            print(f"[Stage 6] 文风迁移失败: {e}")
            return paper_text

    def _recheck_outline(self, paper_text: str) -> Optional[OutlineReview]:
        """重新审视论文逻辑"""
        try:
            analyzer = self._get_outline_analyzer()
            result = analyzer.analyze(paper_text, language=self.project.language)

            if isinstance(result, dict):
                return OutlineReview(
                    section_word_counts=result.get('section_word_counts', {}),
                    section_ratios=result.get('section_ratios', {}),
                    logical_gaps=result.get('logical_gaps', []),
                    deviation_flags=result.get('deviation_flags', []),
                    suggestions=result.get('suggestions', []),
                )
            return None
        except Exception as e:
            print(f"[Stage 6] 逻辑审视失败: {e}")
            return None
