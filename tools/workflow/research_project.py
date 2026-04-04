"""
历史研究论文全流程 — 统一数据结构

定义 ResearchProject 及其所有子数据类型
贯穿 Stage 1~7 的完整生命周期数据管理
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional


class StageStatus(Enum):
    """各阶段执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


# ─────────────────────────────────────────────────────────────────
#  子数据类型
# ─────────────────────────────────────────────────────────────────

@dataclass
class PaperRecord:
    """单条文献记录（Stage 1 产出）"""
    id: str = ""                     # 内部UUID
    title: str = ""
    authors: List[str] = field(default_factory=list)
    year: str = ""
    source: str = ""                  # crossref / arxiv / ...
    url: str = ""
    doi: str = ""
    abstract: str = ""
    journal: str = ""
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> 'PaperRecord':
        return cls(**{k: v for k, v in d.items() if k in cls.__annotations__})


@dataclass
class BookMetadata:
    """图书元数据（Stage 2 产出）"""
    id: str = ""
    title: str = ""
    author: str = ""
    publisher: str = ""
    year: str = ""
    isbn: str = ""
    pages: str = ""
    edition: str = ""
    original_filename: str = ""
    new_filename: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HistoricalEntity:
    """历史实体（Stage 3 产出）"""
    id: str = ""
    name: str = ""
    name_zh: str = ""               # 中文译名（如有）
    category: str = ""               # person / location / event / concept / literature
    confidence: float = 0.0
    notes: str = ""
    related_entities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EntityRelation:
    """实体关系（Stage 3 产出）"""
    from_entity: str = ""
    to_entity: str = ""
    relation_type: str = ""          # father_of / colleague_of / fought_against / ...
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CitationNetwork:
    """引文网络（Stage 4 产出）"""
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    # [{id, title, cited_by_count, is_core}]
    edges: List[Dict[str, str]] = field(default_factory=list)
    # [{from_id, to_id, type}]
    key_source_ids: List[str] = field(default_factory=list)
    orphan_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OutlineReview:
    """论文逻辑审视报告（Stage 4/6 产出）"""
    section_word_counts: Dict[str, int] = field(default_factory=dict)
    # {章节名: 字数}
    section_ratios: Dict[str, float] = field(default_factory=dict)
    # {章节名: 占比}
    logical_gaps: List[str] = field(default_factory=list)
    deviation_flags: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StageResult:
    """单阶段执行结果"""
    stage: int
    name: str
    status: StageStatus
    output: Any = None
    error: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stage': self.stage,
            'name': self.name,
            'status': self.status.value,
            'output': self.output,
            'error': self.error,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
        }


# ─────────────────────────────────────────────────────────────────
#  ResearchProject — 完整研究项目
# ─────────────────────────────────────────────────────────────────

@dataclass
class ResearchProject:
    """
    一个历史研究项目的完整生命周期数据

    属性按阶段分组，便于序列化和断点续做

    使用方法：
        project = ResearchProject(topic="Tudor England", language="en")
        project.run_stage(1)
        print(project.literature)
        project.save("project.json")
    """

    # ── 基本信息 ──────────────────────────────────────────────
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = ""
    language: str = "en"          # en / ja / zh
    bilingual: bool = True
    citation_format: str = "chicago"  # chicago / apa / gb7714 / mla
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec='seconds')
    )
    updated_at: str = ""

    # ── Stage 1: 搜集材料 ──────────────────────────────────────
    stage1_status: StageStatus = StageStatus.PENDING
    literature: List[PaperRecord] = field(default_factory=list)

    # ── Stage 2: 整理史料 ──────────────────────────────────────
    stage2_status: StageStatus = StageStatus.PENDING
    book_metadata: List[BookMetadata] = field(default_factory=list)
    obsidian_notes: List[Dict[str, Any]] = field(default_factory=list)
    formatted_citations: List[str] = field(default_factory=list)

    # ── Stage 3: 提取信息 ──────────────────────────────────────
    stage3_status: StageStatus = StageStatus.PENDING
    entities: List[HistoricalEntity] = field(default_factory=list)
    entity_relations: List[EntityRelation] = field(default_factory=list)

    # ── Stage 4: 史料考察 ─────────────────────────────────────
    stage4_status: StageStatus = StageStatus.PENDING
    citation_network: Optional[CitationNetwork] = None
    key_source_ids: List[str] = field(default_factory=list)

    # ── Stage 5: 撰写论文 ──────────────────────────────────────
    stage5_status: StageStatus = StageStatus.PENDING
    paper_draft: str = ""

    # ── Stage 6: 论文修改润色 ───────────────────────────────────
    stage6_status: StageStatus = StageStatus.PENDING
    polished_draft: str = ""
    style_transferred_draft: str = ""
    outline_review: Optional[OutlineReview] = None

    # ── Stage 7: 注释格式 ──────────────────────────────────────
    stage7_status: StageStatus = StageStatus.PENDING
    final_paper: str = ""

    # ── 内部状态 ───────────────────────────────────────────────
    _stage_history: List[StageResult] = field(default_factory=list)

    # ─────────────────────────────────────────────────────────
    #  工具方法
    # ─────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """保存为 JSON 文件（断点续做）"""
        data = {
            'id': self.id,
            'topic': self.topic,
            'language': self.language,
            'bilingual': self.bilingual,
            'citation_format': self.citation_format,
            'created_at': self.created_at,
            'updated_at': datetime.now().isoformat(timespec='seconds'),
            'literature': [p.to_dict() for p in self.literature],
            'book_metadata': [b.to_dict() for b in self.book_metadata],
            'entities': [e.to_dict() for e in self.entities],
            'citation_network': self.citation_network.to_dict() if self.citation_network else None,
            'paper_draft': self.paper_draft,
            'polished_draft': self.polished_draft,
            'final_paper': self.final_paper,
            'stage_status': {
                'stage1': self.stage1_status.value,
                'stage2': self.stage2_status.value,
                'stage3': self.stage3_status.value,
                'stage4': self.stage4_status.value,
                'stage5': self.stage5_status.value,
                'stage6': self.stage6_status.value,
                'stage7': self.stage7_status.value,
            },
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> 'ResearchProject':
        """从 JSON 文件恢复"""
        with open(path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        project = cls(
            id=d.get('id', str(uuid.uuid4())[:8]),
            topic=d.get('topic', ''),
            language=d.get('language', 'en'),
            bilingual=d.get('bilingual', True),
            citation_format=d.get('citation_format', 'chicago'),
            created_at=d.get('created_at', ''),
        )
        project.literature = [PaperRecord.from_dict(p) for p in d.get('literature', [])]
        project.entities = [HistoricalEntity(**e) for e in d.get('entities', [])]
        project.paper_draft = d.get('paper_draft', '')
        project.final_paper = d.get('final_paper', '')
        status_map = {
            'pending': StageStatus.PENDING,
            'running': StageStatus.RUNNING,
            'done': StageStatus.DONE,
            'failed': StageStatus.FAILED,
            'skipped': StageStatus.SKIPPED,
        }
        for k, v in d.get('stage_status', {}).items():
            stage_num = int(k.replace('stage', ''))
            status = status_map.get(v, StageStatus.PENDING)
            setattr(project, f'stage{stage_num}_status', status)
        return project

    def mark_stage_start(self, stage: int) -> None:
        """标记阶段开始"""
        attr = f'stage{stage}_status'
        setattr(self, attr, StageStatus.RUNNING)
        self.updated_at = datetime.now().isoformat(timespec='seconds')

    def mark_stage_done(self, stage: int) -> None:
        """标记阶段完成"""
        attr = f'stage{stage}_status'
        setattr(self, attr, StageStatus.DONE)
        self.updated_at = datetime.now().isoformat(timespec='seconds')

    def mark_stage_failed(self, stage: int, error: str) -> None:
        """标记阶段失败"""
        attr = f'stage{stage}_status'
        setattr(self, attr, StageStatus.FAILED)
        self.updated_at = datetime.now().isoformat(timespec='seconds')

    def mark_stage_skipped(self, stage: int = 6) -> None:
        """标记阶段跳过"""
        attr = f'stage{stage}_status'
        setattr(self, attr, StageStatus.SKIPPED)
        self.updated_at = datetime.now().isoformat(timespec='seconds')

    def summary(self) -> str:
        """返回项目状态摘要"""
        lines = [
            f"ResearchProject({self.id}) — {self.topic}",
            f"  Language: {self.language} | Bilingual: {self.bilingual}",
            f"  Stage 1 (Collect): {self.stage1_status.value} — {len(self.literature)} papers",
            f"  Stage 2 (Organize): {self.stage2_status.value}",
            f"  Stage 3 (Extract): {self.stage3_status.value} — {len(self.entities)} entities",
            f"  Stage 4 (Examine): {self.stage4_status.value}",
            f"  Stage 5 (Write): {self.stage5_status.value} — {len(self.paper_draft)} chars",
            f"  Stage 6 (Polish): {self.stage6_status.value}",
            f"  Stage 7 (Format): {self.stage7_status.value}",
        ]
        return "\n".join(lines)
