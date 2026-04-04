"""
Stage 3: 提取信息

从史料（文本/PDF/扫描件）中提取历史实体和关系

输入：
    project.literature: List[PaperRecord] — 论文列表（从中提取实体）
    project.obsidian_notes: List[Dict] — 笔记内容（可额外提取）
    project.language: str — 主要语言 (en/ja/zh)

输出：
    project.entities: List[HistoricalEntity]
    project.entity_relations: List[EntityRelation]

依赖模块：
    modules.ner_processor.NERProcessor (日语/中文)
    modules.unified_ocr_processor.UnifiedOCRProcessor (扫描件)
    LLM entity extraction (英语/通用)
"""

import sys
import os
from typing import List, Dict, Any, Optional

_AI_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..')
if _AI_TOOLS not in sys.path:
    sys.path.insert(0, _AI_TOOLS)

from tools.workflow.research_project import (
    ResearchProject, PaperRecord, HistoricalEntity, EntityRelation
)


class Stage3Extract:
    """
    Stage 3: 提取信息

    使用方法：
        stage = Stage3Extract(project)
        result = stage.run()

        # 或直接提取
        entities = stage.extract_entities(texts, language='en')
    """

    NAME = "extract"
    STAGE_NUM = 3

    def __init__(self, project: ResearchProject):
        self.project = project
        self.ner_processor = None
        self.ocr_processor = None
        self.llm_client = None

    def _get_ner_processor(self):
        """延迟创建 NER 处理器（日语/中文）"""
        if self.ner_processor is None:
            from modules.ner_processor import NERProcessor
            # NERProcessor 主要支持日语，英语用 LLM 旁路
            self.ner_processor = NERProcessor(
                api_provider="qwen",
                test_mode=False
            )
        return self.ner_processor

    def _get_llm_client(self):
        """延迟创建 LLM 客户端（用于英语实体提取）"""
        if self.llm_client is None:
            from modules.llm_client import create_llm_client
            self.llm_client = create_llm_client(provider="dashscope")
        return self.llm_client

    def run(self, **kwargs) -> Dict[str, Any]:
        """
        执行 Stage 3：提取信息

        Returns:
            Dict 含 'entities' 和 'relations'
        """
        print(f"[Stage 3] 开始提取信息 | 语言: {self.project.language}")
        print(f"[Stage 3] 文献: {len(self.project.literature)} 篇 | 笔记: {len(self.project.obsidian_notes)} 条")

        self.project.mark_stage_start(self.STAGE_NUM)

        all_entities = []
        all_relations = []

        # ── 3a. 从论文摘要提取实体 ──────────────────────────────
        lit_entities, lit_relations = self._extract_from_literature()
        all_entities.extend(lit_entities)
        all_relations.extend(lit_relations)
        print(f"[Stage 3] 论文实体: {len(lit_entities)} 个")

        # ── 3b. 从笔记内容提取实体（可选）──────────────────────
        if self.project.obsidian_notes:
            note_entities, note_relations = self._extract_from_notes()
            all_entities.extend(note_entities)
            all_relations.extend(note_relations)
            print(f"[Stage 3] 笔记实体: {len(note_entities)} 个")

        # ── 3c. 去重 + 归类 ────────────────────────────────────
        merged_entities = self._merge_entities(all_entities)
        merged_relations = self._deduplicate_relations(all_relations)

        self.project.entities = merged_entities
        self.project.entity_relations = merged_relations
        self.project.mark_stage_done(self.STAGE_NUM)

        result = {
            'entities': merged_entities,
            'relations': merged_relations,
            'total_entities': len(merged_entities),
            'total_relations': len(merged_relations),
        }

        print(f"[Stage 3] 完成！实体: {len(merged_entities)} 个 | 关系: {len(merged_relations)} 条")
        self._print_entity_summary(merged_entities)

        return result

    def _extract_from_literature(self) -> tuple:
        """从论文列表提取实体"""
        entities = []
        relations = []

        for paper in self.project.literature:
            text = f"{paper.title} {paper.abstract or ''}".strip()
            if not text or len(text) < 10:
                continue

            try:
                if self.project.language == 'ja':
                    # 日语 → 使用 NERProcessor
                    paper_entities = self._ner_extract(text)
                else:
                    # 英语/其他 → LLM entity extraction
                    paper_entities = self._llm_extract_entities(text, paper.title)

                # 关联到 paper
                for ent in paper_entities:
                    ent.related_entities.append(f"paper:{paper.id}")

                entities.extend(paper_entities)
            except Exception as e:
                print(f"[Stage 3] 论文实体提取失败 [{paper.title[:40]}]: {e}")

        return entities, relations

    def _extract_from_notes(self) -> tuple:
        """从笔记内容提取实体"""
        entities = []
        relations = []

        for note in self.project.obsidian_notes:
            content = note.get('content', '') or ''
            if not content or len(content) < 20:
                continue

            try:
                if self.project.language == 'ja':
                    note_entities = self._ner_extract(content)
                else:
                    note_entities = self._llm_extract_entities(content, note.get('title', ''))

                # 关联到 note
                for ent in note_entities:
                    ent.related_entities.append(f"note:{note['id']}")

                entities.extend(note_entities)
            except Exception as e:
                print(f"[Stage 3] 笔记实体提取失败 [{note.get('title','')[:40]}]: {e}")

        return entities, relations

    def _ner_extract(self, text: str) -> List[HistoricalEntity]:
        """使用 NERProcessor 提取实体（日语/中文）"""
        import uuid
        try:
            processor = self._get_ner_processor()
            result = processor.recognize_historical_entities(text)

            entities = []
            for item in result:
                entities.append(HistoricalEntity(
                    id=str(uuid.uuid4())[:8],
                    name=item.get('entity', '') or item.get('name', ''),
                    name_zh=item.get('name_zh', ''),
                    category=item.get('category', 'unknown'),
                    confidence=float(item.get('confidence', 0.5)),
                    notes='',
                    related_entities=[],
                ))
            return entities
        except Exception as e:
            print(f"[Stage 3] NER 提取失败: {e}")
            return []

    def _llm_extract_entities(
        self,
        text: str,
        title: str = "",
        max_tokens: int = 2000
    ) -> List[HistoricalEntity]:
        """
        使用 LLM 提取实体（英语等非日语语言）

        基于 HistoryFieldExplorer 中验证过的 _extract_entities_from_llm 方法
        """
        import uuid
        import json

        # 控制输入长度
        input_text = text[:3000] if len(text) > 3000 else text

        prompt = f"""You are a historical research assistant. Extract key entities from the following text.

Text: {input_text}

Identify the following entity types:
- person: historical figures, scholars
- location: countries, cities, regions
- event: historical events, movements
- concept: academic terms, theories, ideologies
- literature: books, documents, archives

Return ONLY valid JSON in this format (no explanation):
{{
  "entities": [
    {{"name": "entity name", "category": "person|location|event|concept|literature", "confidence": 0.0-1.0}},
    ...
  ]
}}

Only return entities that are clearly present in the text. Maximum 15 entities."""

        try:
            llm = self._get_llm_client()
            response = llm._call_llm(prompt, max_tokens=max_tokens)

            # 解析 JSON
            data = None
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith('{') or line.startswith('['):
                    try:
                        data = json.loads(line)
                        break
                    except:
                        continue

            # 尝试从代码块中提取
            if data is None:
                for chunk in response.split('```'):
                    chunk = chunk.strip()
                    if chunk.startswith('{') or chunk.startswith('['):
                        try:
                            data = json.loads(chunk)
                            break
                        except:
                            continue

            entities = []
            if data and 'entities' in data:
                for item in data['entities']:
                    name = item.get('name', '') or item.get('entity', '')
                    if name and len(name) > 1:
                        entities.append(HistoricalEntity(
                            id=str(uuid.uuid4())[:8],
                            name=name,
                            name_zh='',
                            category=item.get('category', 'concept'),
                            confidence=float(item.get('confidence', 0.5)),
                            notes='',
                            related_entities=[],
                        ))

            return entities

        except Exception as e:
            print(f"[Stage 3] LLM 实体提取失败: {e}")
            return []

    def _merge_entities(self, entities: List[HistoricalEntity]) -> List[HistoricalEntity]:
        """
        合并重复实体（同名/近似名合并，保留最高 confidence）
        按 category 分组输出
        """
        if not entities:
            return []

        # 按名称小写去重
        seen = {}
        for ent in entities:
            key = ent.name.lower().strip()
            if key not in seen or ent.confidence > seen[key].confidence:
                seen[key] = ent

        merged = list(seen.values())
        # 按 category + confidence 排序
        merged.sort(key=lambda e: (e.category, -e.confidence))

        print(f"[Stage 3] 实体去重: {len(entities)} → {len(merged)}")
        return merged

    def _deduplicate_relations(
        self,
        relations: List[EntityRelation]
    ) -> List[EntityRelation]:
        """去重关系"""
        seen = set()
        unique = []
        for rel in relations:
            key = (rel.from_entity.lower(), rel.to_entity.lower(), rel.relation_type)
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        return unique

    def _print_entity_summary(self, entities: List[HistoricalEntity]) -> None:
        """打印实体摘要"""
        from collections import Counter
        counts = Counter(e.category for e in entities)
        for cat, cnt in counts.most_common():
            sample = [e.name for e in entities if e.category == cat][:3]
            print(f"  [{cat}] {cnt}: {', '.join(sample[:3])}")
