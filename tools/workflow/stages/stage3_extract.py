"""
Stage 3: 提取信息

增强：NERDisambiguation 实体消歧

输入：
    project.literature: List[PaperRecord]
    project.obsidian_notes: List[Dict]
    project.language: str

输出：
    project.entities: List[HistoricalEntity]
    project.entity_relations: List[EntityRelation]

依赖模块：
    modules.ner_processor.NERProcessor (日语/中文)
    modules.ner_disambiguation.NERDisambiguation
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
    """

    NAME = "extract"
    STAGE_NUM = 3

    def __init__(self, project: ResearchProject):
        self.project = project
        self.ner_processor = None
        self.ner_disambiguator = None
        self.ocr_processor = None
        self.llm_client = None

    def _get_ner_processor(self):
        """延迟创建 NER 处理器（日语/中文）"""
        if self.ner_processor is None:
            from modules.ner_processor import NERProcessor
            self.ner_processor = NERProcessor(
                api_provider="qwen",
                test_mode=False
            )
        return self.ner_processor

    def _get_ner_disambiguator(self):
        """延迟创建 NER 消歧器"""
        if self.ner_disambiguator is None:
            try:
                from modules.ner_disambiguation import NERDisambiguation
                self.ner_disambiguator = NERDisambiguation()
                print("[Stage 3] NERDisambiguation loaded")
            except Exception as e:
                print(f"[Stage 3] NERDisambiguation 加载失败: {e}")
                self.ner_disambiguator = None
        return self.ner_disambiguator

    def _get_llm_client(self):
        """延迟创建 LLM 客户端（用于英语实体提取）"""
        if self.llm_client is None:
            from modules.llm_client import LLMClient
            # 优先从 secrets/api_keys.txt 读取，兼容环境变量 fallback
            try:
                from config.api_key_manager import APIKeyManager
                mgr = APIKeyManager()
                api_key = mgr.get_key('qwen')  # dashscope key
            except Exception:
                api_key = None
            
            if api_key:
                self.llm_client = LLMClient({
                    'provider': 'dashscope',
                    'model': 'qwen-turbo',
                    'api_key': api_key
                })
                print("[Stage 3] LLM: dashscope qwen-turbo (from secrets)")
            else:
                # fallback 到环境变量
                from modules.llm_client import create_llm_client
                self.llm_client = create_llm_client({'provider': 'dashscope'})
                print("[Stage 3] LLM: dashscope (from env var)")
        return self.llm_client

    def _fetch_crossref_metadata(self, doi: str) -> Optional[Dict]:
        """
        通过 CrossRef API 获取论文元数据（摘要、作者、期刊）
        DOI 格式：10.xxxx/xxxxx
        """
        import requests
        
        # 清理 DOI
        clean_doi = doi.strip()
        if clean_doi.startswith('https://doi.org/'):
            clean_doi = clean_doi[16:]
        if clean_doi.startswith('http://doi.org/'):
            clean_doi = clean_doi[15:]
        
        if not clean_doi:
            return None
        
        try:
            url = f"https://api.crossref.org/works/{clean_doi}"
            r = requests.get(url, headers={'Accept': 'application/json'}, timeout=15)
            if r.status_code != 200:
                return None
            
            data = r.json().get('message', {})
            
            # 提取作者
            authors = []
            for a in data.get('author', []):
                name = ' '.join(filter(None, [a.get('given', ''), a.get('family', '')]))
                if name:
                    authors.append(name)
            
            # 提取摘要（可能为 HTML，需清理）
            abstract = data.get('abstract', '') or ''
            # 去除 HTML 标签
            import re
            abstract = re.sub(r'<[^>]+>', '', abstract)
            
            # 提取期刊
            container = data.get('container-title', [])
            journal = container[0] if container else ''
            
            # 提取年份
            published = data.get('published-print', data.get('published-online', {}))
            year = ''
            date_parts = published.get('date-parts', [[]])
            if date_parts and date_parts[0]:
                year = str(date_parts[0][0])
            
            return {
                'abstract': abstract,
                'authors': authors,
                'journal': journal,
                'year': year,
            }
        except Exception as e:
            print(f"[Stage 3] CrossRef 获取失败 [{doi[:40]}]: {e}")
            return None

    def run(self, **kwargs) -> Dict[str, Any]:
        """
        执行 Stage 3：提取信息
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

        # ── 3c. 实体消歧（NERDisambiguation）──────────────────
        if all_entities and self.project.language != 'en':
            all_entities = self._disambiguate_entities(all_entities)

        # ── 3d. 去重 + 归类 ────────────────────────────────────
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
            # ── 1. 先尝试 CrossRef API 补充元数据（DOI 有摘要时跳过）──
            original_abstract = paper.abstract or ''
            original_authors = list(paper.authors) if paper.authors else []
            
            # 尝试从 doi 字段或 url 字段提取 DOI
            doi_to_use = paper.doi or ''
            if not doi_to_use and paper.url:
                # 从 URL 中提取 DOI（如 https://doi.org/10.xxxx/xxxxx）
                import re
                m = re.search(r'(10\.\d{4,}/[^\s\?#]+)', paper.url)
                if m:
                    doi_to_use = m.group(1).rstrip('.')
            
            if not original_abstract and doi_to_use:
                meta = self._fetch_crossref_metadata(doi_to_use)
                if meta:
                    paper.abstract = meta.get('abstract', '')
                    if not paper.authors and meta.get('authors'):
                        paper.authors = meta['authors']
                    if not paper.journal and meta.get('journal'):
                        paper.journal = meta['journal']
                    print(f"[Stage 3] CrossRef 补充 [{paper.title[:50]}]: "
                          f"abstract={len(paper.abstract)}chars, "
                          f"authors={len(paper.authors) if paper.authors else 0}")

            # ── 2. 组合文本用于实体提取 ────────────────────────────
            authors_str = ' '.join(paper.authors) if paper.authors else ''
            text = f"{paper.title} {authors_str} {paper.journal or ''} {paper.abstract or ''}".strip()
            
            if not text or len(text) < 10:
                # 仅有标题时，也尝试 LLM 实体提取（标题本身含实体）
                text = paper.title

            try:
                if self.project.language == 'ja':
                    paper_entities = self._ner_extract(text)
                else:
                    # 英语/其他 → LLM entity extraction
                    paper_entities = self._llm_extract_entities(text, paper.title)

                # 关联到 paper
                for ent in paper_entities:
                    ent.related_entities.append(f"paper:{paper.id}")

                entities.extend(paper_entities)
                
                # 恢复原始元数据（不修改 project.literature 全局状态）
                paper.abstract = original_abstract
                paper.authors = original_authors
                
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
        支持标题级提取（text 很短时也尝试提取）
        """
        import uuid
        import json

        input_text = text[:3000] if len(text) > 3000 else text
        topic = getattr(self.project, 'topic', '') or ''

        # 根据文本长度选择不同策略
        is_short = len(input_text) < 100

        prompt = f"""You are a historical research assistant specializing in the topic: {topic}

Extract key entities from the following text.

Text: {input_text}

Identify the following entity types:
- person: historical figures, scholars, monarchs, politicians
- location: countries, cities, regions, continents
- event: historical events, movements, wars, reforms, religious changes
- concept: academic terms, theories, ideologies, political systems
- literature: books, documents, archives, legal texts

Return ONLY valid JSON in this format (no explanation):
{{
  "entities": [
    {{"name": "entity name", "category": "person|location|event|concept|literature", "confidence": 0.0-1.0, "reason": "brief explanation"}},
    ...
  ]
}}

Important:
- Extract entities clearly present OR strongly implied by the text
- For short texts (titles), infer likely historical entities from the context
- Maximum 20 entities, prioritize the most significant
- confidence: higher for explicit mentions, lower for inferences"""

        try:
            llm = self._get_llm_client()
            result = llm._call_llm(prompt, max_tokens=max_tokens)

            # 解析返回值（_call_llm 返回 Dict 或 str）
            response = result.get('content', '') if isinstance(result, dict) else (result or '')

            # 解析 JSON（支持多行 JSON 对象）
            data = None
            
            # 方法1：尝试直接解析整个 response
            try:
                data = json.loads(response)
            except Exception:
                pass

            # 方法2：尝试从代码块中提取
            if data is None:
                for chunk in response.split('```'):
                    chunk = chunk.strip()
                    if chunk.startswith('json'):
                        chunk = chunk[4:].strip()
                    if chunk.startswith('{') or chunk.startswith('['):
                        try:
                            data = json.loads(chunk)
                            break
                        except Exception:
                            continue

            # 方法3：用正则找第一个 { ... } JSON 对象
            if data is None:
                first_brace = response.find('{')
                if first_brace >= 0:
                    possible = response[first_brace:]
                    try:
                        data = json.loads(possible)
                    except json.JSONDecodeError:
                        pass

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

    def _disambiguate_entities(
        self,
        entities: List[HistoricalEntity]
    ) -> List[HistoricalEntity]:
        """
        使用 NERDisambiguation 对实体进行消歧

        Args:
            entities: 原始实体列表

        Returns:
            List[HistoricalEntity]: 消歧后的实体列表
        """
        try:
            disamb = self._get_ner_disambiguator()
            if disamb is None:
                return entities

            print(f"[Stage 3] 实体消歧: {len(entities)} 个实体")

            # 构建 NERDisambiguation 所需格式
            # 格式: [(text, entity_type, start_pos, end_pos), ...]
            ner_results = []
            for ent in entities:
                if ent.name:
                    ner_results.append((
                        ent.name,
                        ent.category,
                        0,  # start_pos (unknown)
                        len(ent.name)  # end_pos
                    ))

            if not ner_results:
                return entities

            # 执行消歧
            disamb_results = disamb.disambiguate(ner_results, self.project.topic)

            # 更新 entities with disambiguated info
            disamb_map = {}
            for item in disamb_results:
                original = item.get('original_entity', '')
                if original:
                    disamb_map[original] = item

            disambiguated = []
            for ent in entities:
                key = ent.name
                if key in disamb_map:
                    disamb_info = disamb_map[key]
                    # 更新 category 和 confidence
                    new_category = disamb_info.get('disambiguated_type', ent.category)
                    new_confidence = disamb_info.get('confidence', ent.confidence)
                    ent.category = new_category
                    ent.confidence = float(new_confidence)

                    # 更新中文名
                    if disamb_info.get('standard_name'):
                        ent.name_zh = disamb_info.get('standard_name', '')

                disambiguated.append(ent)

            print(f"[Stage 3] 消歧完成")
            return disambiguated

        except Exception as e:
            print(f"[Stage 3] 实体消歧失败: {e}，保持原样")
            return entities

    def _merge_entities(self, entities: List[HistoricalEntity]) -> List[HistoricalEntity]:
        """合并重复实体（同名/近似名合并，保留最高 confidence）"""
        if not entities:
            return []

        seen = {}
        for ent in entities:
            key = ent.name.lower().strip()
            if key not in seen or ent.confidence > seen[key].confidence:
                seen[key] = ent

        merged = list(seen.values())
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
