"""
历史研究论文全流程工作流编排行

按顺序调用 Stage 1~7 的各阶段模块，
管理跨阶段数据传递，支持断点续做和阶段跳过

Phase 1 实现：
    Stage 1: 搜集材料 (Stage1Collect)
    Stage 5: 撰写论文 (Stage5Write)

Phase 2 实现：
    Stage 2: 整理史料 (Stage2Organize)
    Stage 3: 提取信息 (Stage3Extract)
    Stage 4: 史料考察 (Stage4Examine)
"""

import os
import sys
from typing import List, Optional, Dict, Any

# 确保 AItools 路径可用
_AI_TOOLS = os.path.dirname(os.path.dirname(__file__))
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import ResearchProject, StageStatus
from tools.workflow.stages.stage1_collect import Stage1Collect
from tools.workflow.stages.stage2_organize import Stage2Organize
from tools.workflow.stages.stage3_extract import Stage3Extract
from tools.workflow.stages.stage4_examine import Stage4Examine
from tools.workflow.stages.stage5_write import Stage5Write


class WorkflowOrchestrator:
    """
    历史研究论文全流程工作流编排行

    使用方法：
        from tools.workflow import WorkflowOrchestrator

        # 基本用法
        wf = WorkflowOrchestrator(
            topic="Tudor England",
            language="en",
            bilingual=True
        )
        result = wf.run_all()

        # 单阶段执行
        wf.run_stage(1)   # 搜集材料
        wf.run_stage(5)   # 撰写论文

        # 断点续做
        wf = WorkflowOrchestrator.load("project.json")
        wf.run_stage(5)   # 继续撰写

        # 导出结果
        wf.export("output.md")
    """

    STAGES = [
        (1, "搜集材料", "stage1_collect"),
        (2, "整理史料", "stage2_organize"),
        (3, "提取信息", "stage3_extract"),
        (4, "史料考察", "stage4_examine"),
        (5, "撰写论文", "stage5_write"),
        (6, "论文修改润色", "stage6_polish"),
        (7, "注释格式修改", "stage7_format"),
    ]

    def __init__(
        self,
        topic: str,
        language: str = "en",
        bilingual: bool = True,
        citation_format: str = "chicago",
        output_dir: str = "./workflow_output",
    ):
        """
        初始化工作流编排行

        Args:
            topic: 研究主题
            language: 主要语言 (en/ja/zh)
            bilingual: 是否生成双语版本
            citation_format: 目标引用格式 (chicago/apa/gb7714/mla)
            output_dir: 输出目录
        """
        self.project = ResearchProject(
            topic=topic,
            language=language,
            bilingual=bilingual,
            citation_format=citation_format,
        )
        self.output_dir = output_dir
        self._stage_handlers = {
            1: self._run_stage1,
            2: self._run_stage2,
            3: self._run_stage3,
            4: self._run_stage4,
            5: self._run_stage5,
        }
        os.makedirs(self.output_dir, exist_ok=True)

    # ─────────────────────────────────────────────────────────
    #  公共接口
    # ─────────────────────────────────────────────────────────

    def run_all(self) -> ResearchProject:
        """
        全自动执行所有已实现的阶段（Phase 1+2: Stage 1~5）

        Returns:
            ResearchProject: 完整项目（含各阶段产出）
        """
        print("=" * 60)
        print(f"WorkflowOrchestrator 开始执行 | 主题: {self.project.topic}")
        print(f"语言: {self.project.language} | 双语: {self.project.bilingual}")
        print("=" * 60)

        for stage_num, stage_name, _ in self.STAGES:
            if stage_num not in self._stage_handlers:
                print(f"\n[Stage {stage_num}] {stage_name} — 暂未实现，跳过")
                self._skip_stage(stage_num)
                continue

            # 检查是否已执行（断点续做）
            status = getattr(self.project, f'stage{stage_num}_status')
            if status == StageStatus.DONE:
                print(f"\n[Stage {stage_num}] {stage_name} — 已完成，跳过")
                continue

            print(f"\n{'─' * 60}")
            print(f"[Stage {stage_num}] {stage_name}")
            print('─' * 60)

            try:
                self.run_stage(stage_num)
            except Exception as e:
                print(f"[Stage {stage_num}] 执行失败: {e}")
                self.project.mark_stage_failed(stage_num, str(e))
                # 遇到错误继续到下一阶段（Graceful degradation）
                continue

        print("\n" + "=" * 60)
        print("WorkflowOrchestrator 执行完毕")
        print("=" * 60)
        print(self.project.summary())

        # 自动保存断点
        save_path = self._get_save_path()
        self.project.save(save_path)
        print(f"断点已保存: {save_path}")

        return self.project

    def run_stage(self, stage_num: int, **kwargs) -> Any:
        """
        执行单个阶段

        Args:
            stage_num: 阶段编号 (1~7)
            **kwargs: 透传给各阶段 handler

        Returns:
            Any: 阶段输出（类型因阶段而异）
        """
        handler = self._stage_handlers.get(stage_num)
        if handler is None:
            print(f"[Stage {stage_num}] 暂未实现，跳过")
            self._skip_stage(stage_num)
            return None

        self.project.mark_stage_start(stage_num)
        result = handler(**kwargs)
        return result

    def get_output(self, stage_num: int) -> Any:
        """获取指定阶段的产出"""
        attrs = {
            1: 'literature',
            2: 'book_metadata',
            3: 'entities',
            4: 'citation_network',
            5: 'paper_draft',
            6: 'polished_draft',
            7: 'final_paper',
        }
        attr = attrs.get(stage_num)
        if attr is None:
            return None
        return getattr(self.project, attr, None)

    def export(self, path: str = "", fmt: str = "markdown") -> str:
        """
        导出最终论文

        Args:
            path: 输出文件路径（默认自动生成）
            fmt: 格式 (markdown / text)

        Returns:
            str: 文件路径
        """
        content = self.project.final_paper or self.project.paper_draft
        if not content:
            print("[Export] 无论文内容可导出")
            return ""

        if not path:
            import datetime
            ts = datetime.datetime.now().strftime('%Y%m%d')
            safe = "".join(c if c.isalnum() else '_' for c in self.project.topic[:20])
            path = os.path.join(self.output_dir, f"{safe}_{ts}.md")

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[Export] 论文已导出: {path}")
        return path

    @classmethod
    def load(cls, path: str) -> 'WorkflowOrchestrator':
        """从断点文件恢复工作流"""
        project = ResearchProject.load(path)
        wf = cls(
            topic=project.topic,
            language=project.language,
            bilingual=project.bilingual,
            citation_format=project.citation_format,
        )
        wf.project = project
        print(f"[Load] 项目已恢复: {project.id} | {project.topic}")
        print(wf.project.summary())
        return wf

    # ─────────────────────────────────────────────────────────
    #  阶段 Handler（Phase 1 实现）
    # ─────────────────────────────────────────────────────────

    def _run_stage1(self, **kwargs) -> Any:
        """Stage 1: 搜集材料"""
        stage = Stage1Collect(self.project)
        search_limit = kwargs.get('search_limit', 60)
        result = stage.run(search_limit=search_limit)
        # 保存 explorer 实例供 Stage 5 复用
        self._shared_explorer = getattr(stage, 'explorer', None)
        return result

    def _run_stage2(self, **kwargs) -> Any:
        """Stage 2: 整理史料"""
        stage = Stage2Organize(self.project)
        result = stage.run(**kwargs)
        return result

    def _run_stage3(self, **kwargs) -> Any:
        """Stage 3: 提取信息"""
        stage = Stage3Extract(self.project)
        result = stage.run(**kwargs)
        return result

    def _run_stage4(self, **kwargs) -> Any:
        """Stage 4: 史料考察"""
        stage = Stage4Examine(self.project)
        result = stage.run(**kwargs)
        return result

    def _run_stage5(self, **kwargs) -> Any:
        """Stage 5: 撰写论文"""
        # 复用 Stage 1 的 explorer（避免重复探索）
        stage = Stage5Write(self.project, explorer=getattr(self, '_shared_explorer', None))
        topic = kwargs.get('topic', self.project.topic)
        style = kwargs.get('style', 'academic_history')
        result = stage.run(topic=topic, style=style)
        # 导出论文文件
        stage.save_paper(os.path.join(self.output_dir, "paper_draft.md"))
        return result

    # ─────────────────────────────────────────────────────────
    #  辅助方法
    # ─────────────────────────────────────────────────────────

    def _skip_stage(self, stage_num: int) -> None:
        """标记阶段为跳过"""
        attr = f'stage{stage_num}_status'
        if hasattr(self.project, attr):
            setattr(self.project, attr, StageStatus.SKIPPED)

    def _get_save_path(self) -> str:
        """生成断点保存路径"""
        safe = "".join(c if c.isalnum() else '_' for c in self.project.topic[:20])
        return os.path.join(self.output_dir, f"project_{safe}_{self.project.id}.json")
