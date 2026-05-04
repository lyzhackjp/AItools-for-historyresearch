from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .footnote_parser import extract_volume_terms
from .models import ParsedFootnote


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def resolver_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    replacements = {
        "國": "国",
        "會": "会",
        "學": "学",
        "條": "条",
        "關": "関",
        "說": "説",
        "卷": "巻",
        "册": "冊",
        "·": "・",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"[\s　「」『』《》〈〉（）()\[\]［］・･·,，.。:：;；、\-‐‑–—_/]+", "", text)


def _append_unique(items: List[str], value: Any) -> None:
    cleaned = _clean(value)
    if cleaned and cleaned not in items:
        items.append(cleaned)


def _unique(values: Iterable[Any]) -> List[str]:
    items: List[str] = []
    for value in values:
        _append_unique(items, value)
    return items


def _blob(footnote: ParsedFootnote, claim_text: str = "") -> str:
    return " ".join(
        _clean(value)
        for value in [
            footnote.text,
            footnote.title,
            footnote.host_title,
            footnote.contained_title,
            footnote.ndl_keyword,
            claim_text,
        ]
        if _clean(value)
    )


def _blob_key(footnote: ParsedFootnote, claim_text: str = "") -> str:
    return resolver_key(_blob(footnote, claim_text))


def _has_any(blob_key: str, markers: Sequence[str]) -> bool:
    return any(resolver_key(marker) in blob_key for marker in markers)


def _sort_volume_terms(terms: Sequence[str]) -> List[str]:
    return sorted(
        _unique(terms),
        key=lambda term: (
            0 if "巻" in term else 1 if "卷" in term else 2 if "年" in term else 3,
            len(term),
            term,
        ),
    )


def extract_dates(text: str) -> List[str]:
    normalized = unicodedata.normalize("NFKC", text or "")
    dates: List[str] = []
    for pattern in (
        r"(1[89]\d{2}|20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"(1[89]\d{2}|20\d{2})[\-/\.](\d{1,2})[\-/\.](\d{1,2})",
        r"(明治|大正|昭和|平成|令和)\s*([0-9一二三四五六七八九十百元]+)\s*年\s*(\d{1,2})?\s*月?\s*(\d{1,2})?\s*日?",
        r"(1[89]\d{2}|20\d{2})\s*年",
    ):
        for match in re.finditer(pattern, normalized):
            _append_unique(dates, match.group(0))
    return dates[:8]


def _is_same_year_only_date(date_value: Any, publication_year: Any) -> bool:
    date_key = resolver_key(date_value)
    year_key = resolver_key(publication_year)
    if not date_key or not year_key:
        return False
    year_forms = {year_key}
    if not year_key.endswith("年"):
        year_forms.add(f"{year_key}年")
    return date_key in year_forms


def _is_broad_standalone_query(value: str) -> bool:
    cleaned = _clean(value)
    return bool(
        re.fullmatch(r"(?:1[89]\d{2}|20\d{2})年?", cleaned)
        or re.fullmatch(r"(?:1[89]\d{2}|20\d{2})年\d{1,2}月\d{1,2}日", cleaned)
        or re.fullmatch(r"(?:1[89]\d{2}|20\d{2})[\-/\.]\d{1,2}[\-/\.]\d{1,2}", cleaned)
        or re.fullmatch(r"(?:明治|大正|昭和|平成|令和)[0-9一二三四五六七八九十百元]+年?", cleaned)
        or re.fullmatch(r"(?:明治|大正|昭和|平成|令和)[0-9一二三四五六七八九十百元]+年\d{1,2}月\d{1,2}日", cleaned)
    )


def _imperial_title_variants(title: str) -> List[str]:
    variants: List[str] = []
    for value in [
        title,
        "帝国憲法義解 皇室典範義解",
        "帝国憲法義解・皇室典範義解",
        "帝國憲法義解 皇室典範義解",
        "帝國憲法義解・皇室典範義解",
        "帝国憲法義解",
        "帝國憲法義解",
        "皇室典範義解",
    ]:
        _append_unique(variants, value)
    return variants


def _hay_policy_terms(text: str) -> tuple[List[str], List[str]]:
    person: List[str] = []
    policy: List[str] = []
    if any(term in text for term in ("约翰", "海伊", "John Hay", "Hay", "ヘイ")):
        for value in [
            "ジョン・ヘイ",
            "ヘイ",
            "ヘイ國務卿",
            "ヘイ国務卿",
            "米國務卿",
            "米国務卿",
            "米國國務長官",
            "米国国務長官",
            "合衆國國務長官",
        ]:
            _append_unique(person, value)
    if any(term in text for term in ("门户开放", "門戸開放", "門戶開放", "机会均等", "機會均等", "照会", "回答")):
        for value in [
            "支那ニ於ケル商業上機會均等及門戸開放",
            "支那ニ於ケル商業上機会均等及門戸開放",
            "商業上機會均等及門戸開放",
            "商業上機会均等及門戸開放",
            "支那門戶開放",
            "支那門戸開放",
            "門戶開放",
            "門戸開放",
            "商業上機會均等",
            "商業上機会均等",
            "合衆國ノ提議",
            "合衆国ノ提議",
            "合衆國政府ノ提議",
            "合衆国政府ノ提議",
            "合衆國政府カ宣言",
            "合衆国政府カ宣言",
            "日本國政府ハ",
            "日本国政府ハ",
            "承諾シタル",
            "米國照會",
            "米国照会",
            "米國政府照會",
            "米国政府照会",
            "米國國務長官照會",
            "米国国務長官照会",
            "帝國政府回答",
            "帝国政府回答",
            "帝國政府ノ回答",
            "帝国政府ノ回答",
            "各國回答",
            "各国回答",
        ]:
            _append_unique(policy, value)
    return person, policy


def _gaiko_document_terms(text: str) -> List[str]:
    terms: List[str] = []
    if any(term in text for term in ("巴黎", "巴里", "パリ", "講和", "讲和", "牧野")):
        for value in [
            "大正期 追補",
            "大正期追補",
            "追補 [1]",
            "巴里講和會議經過概要",
            "巴里講和会議経過概要",
            "巴里講和会議經過概要",
            "巴黎讲和会议经过概要",
            "巴黎講和会議経過概要",
            "パリ講和会議経過概要",
            "牧野",
            "講和會議",
            "講和会議",
        ]:
            _append_unique(terms, value)
    if any(term in text for term in ("ワシントン", "華盛頓", "华盛顿", "軍備", "军备", "主力艦", "海軍")):
        for value in [
            "ワシントン會議",
            "ワシントン会議",
            "華盛頓會議",
            "华盛顿会议",
            "ワシントン会議 上",
            "ワシントン会議 下",
            "軍備制限問題",
            "海軍軍備制限問題",
            "主力艦",
            "比率",
            "内田康哉",
            "加藤友三郎",
            "ヒューズ",
        ]:
            _append_unique(terms, value)
    return terms


def _gaiko_document_heading_terms(text: str) -> List[str]:
    terms: List[str] = []
    if any(term in text for term in ("巴里", "巴黎", "パリ", "講和", "讲和", "牧野")):
        for value in [
            "帝國主張説明",
            "帝国主張説明",
            "牧野男",
            "牧野委員",
            "聯盟委員管理",
        ]:
            _append_unique(terms, value)
        if any(term in text for term in ("赤道", "南洋", "太平洋", "委任", "托管", "既定目標", "既定目标")):
            for value in [
                "委任統治",
                "委任統治ノ形式",
                "C式委任統治",
                "C類委任統治",
                "赤道以北",
                "獨領南洋",
                "独領南洋",
                "南洋群島",
                "太平洋群島",
                "會議ノ決定",
                "会議ノ決定",
                "決定ヲ受諾",
            ]:
                _append_unique(terms, value)
        if any(term in text for term in ("山東", "山东", "膠州", "胶州", "還附", "归还", "歸還")):
            for value in [
                "青島南洋",
                "山東",
                "膠州灣",
                "膠州湾",
                "還附ノ決定",
            ]:
                _append_unique(terms, value)
    if any(term in text for term in ("ワシントン", "華盛頓", "华盛顿", "軍備", "军备", "主力艦", "海軍")):
        for value in [
            "軍備制限問題",
            "海軍軍備制限",
            "海軍軍備制限問題",
            "主力艦",
            "主力艦比率",
            "勢力比",
            "海軍勢力比",
            "比率",
            "ヒューズ",
            "ヒューズ国務長官",
            "ヒューズ國務長官",
            "十対六",
            "十對六",
            "米国案ノ十対六",
            "米國案ノ十對六",
            "六割",
            "日英米三国間",
            "日英米三國間",
            "製艦ヲ協定程度ニ制限",
            "内田",
            "加藤友三郎",
            "防備",
        ]:
            _append_unique(terms, value)
    if any(
        term in text
        for term in (
            "桂太郎",
            "塔夫脱",
            "塔夫脫",
            "タフト",
            "哈里曼",
            "ハリマン",
            "南满铁路",
            "南滿鐵路",
            "南满洲铁路",
            "南滿洲鐵路",
            "満鉄",
            "满铁",
        )
    ):
        for value in [
            "桂太郎",
            "タフト",
            "タフト陸軍長官",
            "桂・タフト",
            "桂・タフト協定",
            "桂・タフト覚書",
            "ハリマン",
            "満鉄",
            "南満洲鉄道",
            "南滿洲鐵道",
            "共同經營",
            "共同経営",
            "豫備協定",
            "予備協定",
        ]:
            _append_unique(terms, value)
    if any(term in text for term in ("門戸開放", "門戶開放", "门户开放", "機會均等", "机会均等", "John Hay", "海伊", "ヘイ")):
        for value in [
            "米國照會",
            "米国照会",
            "帝國政府回答",
            "帝国政府回答",
            "各國回答",
            "各国回答",
            "ヘイ國務卿",
            "ヘイ国務卿",
            "合衆國ノ提議",
            "合衆国ノ提議",
            "合衆國政府ノ提議",
            "合衆国政府ノ提議",
            "合衆國政府カ宣言",
            "合衆国政府カ宣言",
            "日本國政府ハ",
            "日本国政府ハ",
            "承諾シタル",
            "支那ニ於ケル商業上機會均等及門戸開放",
            "支那ニ於ケル商業上機会均等及門戸開放",
        ]:
            _append_unique(terms, value)
    return terms


def _gaiko_canonical_query_buckets(
    document_terms: Sequence[str],
    document_heading_terms: Sequence[str],
    person_terms: Sequence[str],
    policy_terms: Sequence[str],
) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {
        "anchor": [],
        "theme": [],
        "action": [],
        "page_near": [],
    }
    for value in [*document_terms, *person_terms]:
        _append_unique(buckets["anchor"], value)

    theme_markers = (
        "委任",
        "南洋",
        "太平洋",
        "軍備",
        "海軍",
        "主力艦",
        "比率",
        "十対六",
        "十對六",
        "米国案",
        "米國案",
        "門戸開放",
        "門戶開放",
        "機會均等",
        "機会均等",
        "南満",
        "南滿",
        "満鉄",
        "滿鐵",
    )
    action_markers = (
        "決定",
        "受諾",
        "承諾",
        "回答",
        "照會",
        "照会",
        "提議",
        "宣言",
        "共同經營",
        "共同経営",
        "協定",
        "覚書",
        "制限",
    )
    page_near_markers = (
        "帝國主張説明",
        "帝国主張説明",
        "牧野男",
        "赤道以北",
        "獨領南洋",
        "独領南洋",
        "米国案ノ十対六",
        "米國案ノ十對六",
        "十対六",
        "十對六",
        "合衆國ノ提議",
        "合衆国ノ提議",
        "日本國政府ハ",
        "日本国政府ハ",
        "桂・タフト",
        "タフト陸軍長官",
    )
    for value in [*document_heading_terms, *policy_terms]:
        if any(marker in value for marker in theme_markers):
            _append_unique(buckets["theme"], value)
        if any(marker in value for marker in action_markers):
            _append_unique(buckets["action"], value)
        if any(marker in value for marker in page_near_markers):
            _append_unique(buckets["page_near"], value)
    for value in document_heading_terms:
        _append_unique(buckets["page_near"], value)
    return {key: values for key, values in buckets.items() if values}


def _special_terms(text: str) -> tuple[List[str], List[str]]:
    if "大麻" not in text:
        return [], []
    qualifiers = ("神宮大麻", "皇大神宮", "神田神社", "窪田次郎", "配布", "流言", "御札", "神社")
    if not any(term in text for term in qualifiers):
        return [], ["大麻"]
    queries: List[str] = []
    for value in [
        "神宮大麻 皇大神宮",
        "神宮大麻 配布",
        "神宮大麻 御札",
        "神宮大麻 流言",
        "皇大神宮 大麻",
        "窪田次郎 神宮大麻",
        "神田神社 神宮大麻",
    ]:
        _append_unique(queries, value)
    return queries, ["大麻"]


def _load_resolver_config() -> Dict[str, Any]:
    paths: List[Path] = []
    paths.append(Path("config") / "historical_citation_source_resolvers.json")
    paths.append(Path(__file__).resolve().parents[2] / "config" / "historical_citation_source_resolvers.json")
    env_path = os.environ.get("HISTORICAL_CITATION_SOURCE_RESOLVER_CONFIG")
    if env_path:
        paths.append(Path(env_path))
    merged: Dict[str, Any] = {}
    for path in paths:
        try:
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            merged.update(payload)
    return merged


def _candidate_terms_from_config_item(item: Dict[str, Any]) -> List[str]:
    values: List[Any] = [
        item.get("volume"),
        item.get("year"),
        item.get("era_year"),
        item.get("date_range"),
        item.get("title"),
        item.get("author"),
    ]
    for key in ("terms", "aliases", "volume_aliases", "date_aliases"):
        extra = item.get(key)
        if isinstance(extra, list):
            values.extend(extra)
        elif extra:
            values.append(extra)
    return _unique(values)


def _terms_match_config(haystack_terms: Sequence[str], item_terms: Sequence[str]) -> bool:
    haystack_keys = [resolver_key(term) for term in haystack_terms if resolver_key(term)]
    item_keys = [resolver_key(term) for term in item_terms if resolver_key(term)]
    if not haystack_keys or not item_keys:
        return False
    for item_key in item_keys:
        for haystack_key in haystack_keys:
            if item_key == haystack_key or item_key in haystack_key or haystack_key in item_key:
                return True
    return False


def _configured_pid_candidates(
    section: str,
    volume_terms: Sequence[str],
    dates: Sequence[str],
    *,
    extra_terms: Sequence[str] = (),
) -> List[str]:
    config = _load_resolver_config().get(section) or {}
    volumes = config.get("volumes") if isinstance(config, dict) else None
    if not isinstance(volumes, list):
        return []
    haystack_terms = _unique([*volume_terms, *dates, *extra_terms])
    scored_pids: List[tuple[int, int, str]] = []
    for index, item in enumerate(volumes):
        if not isinstance(item, dict):
            continue
        item_terms = _candidate_terms_from_config_item(item)
        if item_terms:
            if not haystack_terms and not item.get("default"):
                continue
            if haystack_terms and not _terms_match_config(haystack_terms, item_terms):
                continue
        pid = str(item.get("pid") or item.get("ndl_id") or "")
        if pid:
            score = sum(1 for term in item_terms if _terms_match_config(haystack_terms, [term]))
            scored_pids.append((score, index, pid))
    pids: List[str] = []
    for _score, _index, pid in sorted(scored_pids, key=lambda item: (-item[0], item[1])):
        _append_unique(pids, pid)
    return pids


def _configured_document_items(section: str, terms: Sequence[str]) -> List[Dict[str, Any]]:
    config = _load_resolver_config().get(section) or {}
    documents = config.get("documents") if isinstance(config, dict) else None
    if not isinstance(documents, list):
        return []
    matches: List[Dict[str, Any]] = []
    haystack_terms = _unique(terms)
    for item in documents:
        if not isinstance(item, dict):
            continue
        item_terms = _candidate_terms_from_config_item(item)
        if item_terms and not _terms_match_config(haystack_terms, item_terms):
            continue
        matches.append(item)
    return matches


def _configured_document_pid_candidates(section: str, terms: Sequence[str]) -> List[str]:
    pids: List[str] = []
    for item in _configured_document_items(section, terms):
        pid = str(item.get("pid") or item.get("ndl_id") or "")
        if pid:
            _append_unique(pids, pid)
    return pids


def _configured_document_terms(items: Sequence[Dict[str, Any]], key: str) -> List[str]:
    values: List[Any] = []
    for item in items:
        terms = item.get(key)
        if isinstance(terms, list):
            values.extend(terms)
        elif terms:
            values.append(terms)
    return _unique(values)


def _configured_claim_facet_buckets(section: str, text: str) -> Dict[str, List[str]]:
    config = _load_resolver_config().get(section) or {}
    facets = config.get("claim_facets") if isinstance(config, dict) else None
    if not isinstance(facets, list):
        return {}
    text_key = resolver_key(text)
    buckets: Dict[str, List[str]] = {}
    term_keys = {
        "anchor_terms": "anchor",
        "theme_terms": "theme",
        "action_terms": "action",
        "page_near_terms": "page_near",
        "person_terms": "person",
        "policy_terms": "policy",
        "document_title_terms": "document_title",
        "document_heading_terms": "document_heading",
        "institution_terms": "institution",
        "special_terms": "special_term",
        "target_pid_required_terms": "_target_pid_required",
        "pid_match_terms": "_pid_match",
    }

    def add_terms(bucket_name: str, values: Any) -> None:
        if not bucket_name:
            return
        target = buckets.setdefault(bucket_name, [])
        if isinstance(values, list):
            source_values = values
        else:
            source_values = [values]
        for value in source_values:
            _append_unique(target, value)

    for facet in facets:
        if not isinstance(facet, dict):
            continue
        triggers = facet.get("trigger_terms") or facet.get("triggers") or []
        if triggers and not _has_any(text_key, [str(item) for item in triggers]):
            continue
        role = str(facet.get("role") or "")
        if role:
            add_terms(role, facet.get("terms") or [])
        facet_buckets = facet.get("buckets")
        if isinstance(facet_buckets, dict):
            for bucket_name, values in facet_buckets.items():
                add_terms(str(bucket_name), values)
        for key, bucket_name in term_keys.items():
            add_terms(bucket_name, facet.get(key) or [])
    return {key: values for key, values in buckets.items() if values}


def _merge_configured_query_buckets(
    target_buckets: Dict[str, List[str]],
    configured_buckets: Dict[str, List[str]],
) -> None:
    for bucket_name, bucket_values in configured_buckets.items():
        if bucket_name.startswith("_"):
            continue
        target = target_buckets.setdefault(bucket_name, [])
        for value in bucket_values:
            _append_unique(target, value)


@dataclass
class ResolvedSourcePlan:
    resolver: str
    source_family: str
    source_type: str
    source_level_cache_key: str
    evidence_mode: str
    verification_mode: str
    pid_scope_strategy: str
    known_pid_candidates: List[str] = field(default_factory=list)
    volume_terms: List[str] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    query_buckets: Dict[str, List[str]] = field(default_factory=dict)
    target_pid_queries: List[str] = field(default_factory=list)
    global_queries: List[str] = field(default_factory=list)
    metadata_queries: List[str] = field(default_factory=list)
    manual_steps: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceResolver:
    resolver_name = "GenericSourceResolver"
    source_family = "generic"
    source_type = "monograph"
    evidence_mode = "metadata_bridge"
    verification_mode = "primary_or_secondary_unknown"
    pid_scope_strategy = "metadata_then_pid"

    def matches(self, footnote: ParsedFootnote, claim_text: str = "") -> bool:
        return True

    def resolve(self, footnote: ParsedFootnote, claim_text: str = "") -> ResolvedSourcePlan:
        title = _clean(footnote.title)
        dates = extract_dates(_blob(footnote, claim_text))
        volume_terms = _sort_volume_terms(extract_volume_terms(_blob(footnote, claim_text)))
        query_buckets = {
            "title": _unique([title, footnote.ndl_keyword]),
            "host": _unique([footnote.host_title]),
            "contained": _unique([footnote.contained_title]),
            "volume": volume_terms,
            "date": dates,
            "person": [],
            "policy": [],
            "special_term": [],
            "blocked_standalone": [],
        }
        global_queries = _build_global_queries(query_buckets)
        return ResolvedSourcePlan(
            resolver=self.resolver_name,
            source_family=self.source_family,
            source_type=self.source_type,
            source_level_cache_key=_source_cache_key(self.source_family, title, volume_terms, dates),
            evidence_mode=self.evidence_mode,
            verification_mode=self.verification_mode,
            pid_scope_strategy=self.pid_scope_strategy,
            volume_terms=volume_terms,
            dates=dates,
            query_buckets=query_buckets,
            target_pid_queries=_unique([*query_buckets["contained"], *query_buckets["policy"], *query_buckets["person"], *query_buckets["date"], title]),
            global_queries=global_queries,
            metadata_queries=_unique([footnote.ndl_keyword, title, footnote.author]),
            manual_steps=[
                "先确认题名、作者、出版年和页码。",
                "若候选不可下载，尝试 PID 内全文 snippet 或其他平台元数据桥接。",
            ],
        )


class NihonKindaiShisoTaikeiResolver(SourceResolver):
    resolver_name = "NihonKindaiShisoTaikeiResolver"
    source_family = "日本近代思想大系"
    source_type = "source_collection"
    evidence_mode = "pid_snippet"
    verification_mode = "primary_source_collection"
    pid_scope_strategy = "fixed_host_pid_then_contained_snippet"

    def matches(self, footnote: ParsedFootnote, claim_text: str = "") -> bool:
        return _has_any(_blob_key(footnote, claim_text), ("日本近代思想大系", "宗教と国家"))

    def resolve(self, footnote: ParsedFootnote, claim_text: str = "") -> ResolvedSourcePlan:
        plan = super().resolve(footnote, claim_text)
        plan.resolver = self.resolver_name
        plan.source_family = self.source_family
        plan.source_type = self.source_type
        plan.evidence_mode = self.evidence_mode
        plan.verification_mode = self.verification_mode
        plan.pid_scope_strategy = self.pid_scope_strategy
        plan.known_pid_candidates = ["13260166"]
        plan.query_buckets["host"] = _unique([footnote.host_title, "日本近代思想大系 5：宗教と国家"])
        plan.query_buckets["contained"] = _unique([footnote.contained_title, footnote.title])
        special, blocked = _special_terms(_blob(footnote, claim_text))
        plan.query_buckets["special_term"] = special
        plan.query_buckets["blocked_standalone"] = blocked
        configured_buckets = _configured_claim_facet_buckets("nihon_kindai_shiso_taikei", _blob(footnote, claim_text))
        configured_required_target_terms = configured_buckets.pop("_target_pid_required", [])
        _merge_configured_query_buckets(plan.query_buckets, configured_buckets)
        plan.target_pid_queries = _ensure_limited_terms(
            _unique(
                [
                    *plan.query_buckets["contained"],
                    *plan.query_buckets.get("theme", []),
                    *plan.query_buckets.get("action", []),
                    *plan.query_buckets.get("page_near", []),
                    *plan.query_buckets.get("anchor", []),
                    *plan.query_buckets["special_term"],
                    *plan.query_buckets["date"],
                ]
            ),
            configured_required_target_terms,
            max_terms=12,
        )
        plan.global_queries = _build_global_queries(plan.query_buckets)
        plan.source_level_cache_key = _source_cache_key(self.source_family, "宗教と国家", plan.volume_terms, plan.dates)
        plan.manual_steps = [
            "固定宿主 PID 后，只在该 PID 内搜索析出题名和限定关键词。",
            "contained title 命中优先于 host title 命中。",
            "只命中目录或题名层时标为 lead，不作为最终支持证据。",
        ]
        return plan


class NihonGaikoBunshoResolver(SourceResolver):
    resolver_name = "NihonGaikoBunshoResolver"
    source_family = "日本外交文書"
    source_type = "volume_series"
    evidence_mode = "pid_snippet_or_download_ocr"
    verification_mode = "primary_source_collection"
    pid_scope_strategy = "volume_pid_mapping_then_pid_snippet"

    def matches(self, footnote: ParsedFootnote, claim_text: str = "") -> bool:
        return _has_any(_blob_key(footnote, claim_text), ("日本外交文書", "日本外交文书"))

    def resolve(self, footnote: ParsedFootnote, claim_text: str = "") -> ResolvedSourcePlan:
        plan = super().resolve(footnote, claim_text)
        text = _blob(footnote, claim_text)
        person_terms, policy_terms = _hay_policy_terms(text)
        document_terms = _gaiko_document_terms(text)
        document_heading_terms = _gaiko_document_heading_terms(text)
        canonical_buckets = _gaiko_canonical_query_buckets(
            document_terms,
            document_heading_terms,
            person_terms,
            policy_terms,
        )
        configured_buckets = _configured_claim_facet_buckets("nihon_gaiko_bunsho", text)
        configured_required_target_terms = configured_buckets.pop("_target_pid_required", [])
        configured_pid_match_terms = configured_buckets.pop("_pid_match", [])
        plan.resolver = self.resolver_name
        plan.source_family = self.source_family
        plan.source_type = self.source_type
        plan.evidence_mode = self.evidence_mode
        plan.verification_mode = self.verification_mode
        plan.pid_scope_strategy = self.pid_scope_strategy
        plan.query_buckets["title"] = _unique(["日本外交文書", footnote.ndl_keyword])
        plan.query_buckets["host"] = _unique(["日本外交文書"])
        plan.query_buckets["document_title"] = document_terms
        plan.query_buckets["document_heading"] = document_heading_terms
        plan.query_buckets["person"] = person_terms
        plan.query_buckets["policy"] = policy_terms
        for bucket_name, bucket_values in canonical_buckets.items():
            target = plan.query_buckets.setdefault(bucket_name, [])
            for value in bucket_values:
                _append_unique(target, value)
        for bucket_name, bucket_values in configured_buckets.items():
            target = plan.query_buckets.setdefault(bucket_name, [])
            for value in bucket_values:
                _append_unique(target, value)
        configured_terms = [
            value
            for bucket_values in configured_buckets.values()
            for value in bucket_values
        ]
        plan.known_pid_candidates = _configured_pid_candidates(
            "nihon_gaiko_bunsho",
            plan.volume_terms,
            plan.dates,
            extra_terms=[
                *person_terms,
                *policy_terms,
                *document_terms,
                *document_heading_terms,
                *configured_pid_match_terms,
                *plan.query_buckets["contained"],
            ],
        )
        if not plan.known_pid_candidates:
            plan.warnings.append("volume_pid_mapping_missing")
        plan.target_pid_queries = _ensure_limited_terms(
            _balanced_volume_series_specifics(
                _unique(
                    [
                        *plan.query_buckets["document_title"],
                        *plan.query_buckets["document_heading"],
                        *plan.query_buckets["policy"],
                        *plan.query_buckets["person"],
                        *plan.query_buckets.get("theme", []),
                        *plan.query_buckets.get("action", []),
                        *plan.query_buckets.get("page_near", []),
                        *plan.query_buckets.get("anchor", []),
                        *plan.query_buckets["date"],
                        *plan.query_buckets["contained"],
                    ]
                ),
                max_terms=12,
            ),
            configured_required_target_terms,
            max_terms=12,
        )
        plan.global_queries = _build_global_queries(plan.query_buckets, prefer_balanced_volume_series=True)
        plan.metadata_queries = _unique([" ".join(["日本外交文書", term]) for term in plan.volume_terms] + ["日本外交文書"])
        plan.source_level_cache_key = _source_cache_key(self.source_family, "日本外交文書", plan.volume_terms, plan.dates)
        plan.manual_steps = [
            "先解析卷号、年份、册次并查卷册 PID。",
            "进入目标卷册 PID 后搜索文书题名、人名、日期和外交政策词。",
            "只命中系列名、目录或错误卷册时标为 lead。",
        ]
        return plan


class DiaryDateResolver(SourceResolver):
    resolver_name = "DiaryDateResolver"
    source_family = "原敬日記"
    source_type = "diary"
    evidence_mode = "date_snippet_or_download_ocr"
    verification_mode = "primary_diary"
    pid_scope_strategy = "date_to_volume_then_pid_snippet"

    def matches(self, footnote: ParsedFootnote, claim_text: str = "") -> bool:
        return _has_any(_blob_key(footnote, claim_text), ("原敬日記", "原敬日记"))

    def resolve(self, footnote: ParsedFootnote, claim_text: str = "") -> ResolvedSourcePlan:
        plan = super().resolve(footnote, claim_text)
        plan.resolver = self.resolver_name
        plan.source_family = self.source_family
        plan.source_type = self.source_type
        plan.evidence_mode = self.evidence_mode
        plan.verification_mode = self.verification_mode
        plan.pid_scope_strategy = self.pid_scope_strategy
        original_dates = list(plan.dates)
        plan.dates = [
            date
            for date in plan.dates
            if not _is_same_year_only_date(date, getattr(footnote, "year", ""))
        ]
        if len(plan.dates) != len(original_dates):
            plan.warnings.append("publication_year_removed_from_diary_dates")
        plan.query_buckets["title"] = _unique(["原敬日記", footnote.ndl_keyword])
        plan.query_buckets["host"] = _unique(["原敬日記"])
        plan.query_buckets["date"] = plan.dates
        configured_buckets = _configured_claim_facet_buckets("hara_takashi_diary", _blob(footnote, claim_text))
        configured_required_target_terms = configured_buckets.pop("_target_pid_required", [])
        configured_pid_match_terms = configured_buckets.pop("_pid_match", [])
        _merge_configured_query_buckets(plan.query_buckets, configured_buckets)
        plan.known_pid_candidates = _configured_pid_candidates(
            "hara_takashi_diary",
            plan.volume_terms,
            plan.dates,
            extra_terms=configured_pid_match_terms,
        )
        if not plan.dates:
            plan.warnings.append("date_missing_for_diary_resolver")
        if not plan.known_pid_candidates:
            plan.warnings.append("diary_volume_pid_mapping_missing")
        plan.target_pid_queries = _ensure_limited_terms(
            _unique(
                [
                    *plan.query_buckets["date"],
                    *plan.query_buckets["person"],
                    *plan.query_buckets.get("anchor", []),
                    *plan.query_buckets.get("theme", []),
                    *plan.query_buckets.get("action", []),
                    *plan.query_buckets.get("page_near", []),
                    *plan.query_buckets.get("institution", []),
                    footnote.title,
                ]
            ),
            configured_required_target_terms,
            max_terms=12,
        )
        plan.global_queries = _build_global_queries(plan.query_buckets)
        plan.metadata_queries = _unique([" ".join(["原敬日記", term]) for term in [*plan.dates, *plan.volume_terms]] + ["原敬日記"])
        plan.source_level_cache_key = _source_cache_key(self.source_family, "原敬日記", plan.volume_terms, plan.dates)
        plan.manual_steps = [
            "日期优先，页码其次。",
            "若脚注没有日期，从正文事件链抽取最近日期。",
            "按日期定位卷册后，再用人名、事件词补检。",
        ]
        return plan


class DownloadableMonographResolver(SourceResolver):
    resolver_name = "DownloadableMonographResolver"
    source_family = "帝国憲法義解・皇室典範義解"
    source_type = "downloadable_monograph"
    evidence_mode = "download_ocr"
    verification_mode = "primary_monograph"
    pid_scope_strategy = "known_downloadable_pid_then_cache"

    def matches(self, footnote: ParsedFootnote, claim_text: str = "") -> bool:
        return _has_any(_blob_key(footnote, claim_text), ("帝国憲法義解", "帝國憲法義解", "皇室典範義解"))

    def resolve(self, footnote: ParsedFootnote, claim_text: str = "") -> ResolvedSourcePlan:
        plan = super().resolve(footnote, claim_text)
        plan.resolver = self.resolver_name
        plan.source_family = self.source_family
        plan.source_type = self.source_type
        plan.evidence_mode = self.evidence_mode
        plan.verification_mode = self.verification_mode
        plan.pid_scope_strategy = self.pid_scope_strategy
        plan.known_pid_candidates = ["1272168"]
        plan.query_buckets["title"] = _imperial_title_variants(footnote.title)
        if any(marker in _blob(footnote, claim_text) for marker in ("信教", "宗教", "信仰", "自由")):
            plan.query_buckets["special_term"] = _unique(
                [
                    "信仰",
                    "信仰歸依",
                    "信仰帰依",
                    "内部ニ於ケル信",
                    "外部ニ於ケル禮拜",
                    "外部ニ於ケル礼拝",
                    "臣民ノ義務",
                    "法憲",
                    "法律規則",
                    "布教",
                ]
            )
        plan.global_queries = _build_global_queries(plan.query_buckets)
        plan.target_pid_queries = _unique([*plan.query_buckets["special_term"], *plan.query_buckets["title"]])
        plan.source_level_cache_key = _source_cache_key(self.source_family, "1272168", [], [])
        plan.manual_steps = [
            "先用合刻题名、分题名和新旧字体变体确认可下载 PID。",
            "同一 PID 下复用页映射、OCR 和小页窗缓存。",
            "页映射失败时先尝试 PID 内 snippet 定位扫描页。",
        ]
        return plan


class ContainedDocumentResolver(SourceResolver):
    resolver_name = "ContainedDocumentResolver"
    source_family = "contained_document"
    source_type = "contained_document"
    evidence_mode = "host_then_pid_snippet"
    verification_mode = "primary_contained_document"
    pid_scope_strategy = "host_discovery_then_contained_snippet"

    def matches(self, footnote: ParsedFootnote, claim_text: str = "") -> bool:
        key = _blob_key(footnote, claim_text)
        return bool(
            _clean(getattr(footnote, "host_title", ""))
            or _clean(getattr(footnote, "source_relation", "")) == "contained_in_host"
            or _has_any(key, ("意見書", "意见书", "建白", "談話", "谈话"))
        )

    def resolve(self, footnote: ParsedFootnote, claim_text: str = "") -> ResolvedSourcePlan:
        plan = super().resolve(footnote, claim_text)
        host = _clean(footnote.host_title)
        contained = _clean(footnote.contained_title or footnote.title)
        matched_config_items = _configured_document_items(
            "contained_documents",
            [contained, footnote.title, footnote.author, footnote.ndl_keyword, claim_text],
        )
        configured_pids = _configured_document_pid_candidates(
            "contained_documents",
            [contained, footnote.title, footnote.author, footnote.ndl_keyword, claim_text],
        )
        plan.resolver = self.resolver_name
        plan.source_family = host or "contained_document"
        plan.source_type = self.source_type
        plan.evidence_mode = self.evidence_mode
        plan.verification_mode = self.verification_mode
        plan.pid_scope_strategy = self.pid_scope_strategy
        if configured_pids:
            plan.source_family = contained or plan.source_family
            plan.evidence_mode = "known_document_pid_then_host_fallback"
            plan.pid_scope_strategy = "known_document_pid_then_host_fallback"
            plan.known_pid_candidates = configured_pids
        plan.query_buckets["host"] = _unique([host])
        plan.query_buckets["contained"] = _unique([contained])
        plan.query_buckets["person"] = _configured_document_terms(matched_config_items, "person_terms")
        plan.query_buckets["theme"] = _configured_document_terms(matched_config_items, "theme_terms")
        plan.query_buckets["action"] = _configured_document_terms(matched_config_items, "action_terms")
        plan.query_buckets["page_near"] = _configured_document_terms(matched_config_items, "page_near_terms")
        configured_buckets = _configured_claim_facet_buckets("contained_documents", _blob(footnote, claim_text))
        configured_required_target_terms = configured_buckets.pop("_target_pid_required", [])
        _merge_configured_query_buckets(plan.query_buckets, configured_buckets)
        if not host and not configured_pids:
            plan.warnings.append("host_title_missing_for_contained_document")
        plan.target_pid_queries = _ensure_limited_terms(
            _unique(
                [
                    contained,
                    *plan.query_buckets["date"],
                    *plan.query_buckets["person"],
                    *plan.query_buckets["theme"],
                    *plan.query_buckets["action"],
                    *plan.query_buckets["page_near"],
                    *plan.query_buckets.get("anchor", []),
                ]
            ),
            configured_required_target_terms,
            max_terms=12,
        )
        plan.global_queries = _build_global_queries(plan.query_buckets)
        plan.metadata_queries = _unique([contained, " ".join([contained, footnote.author]), host])
        plan.source_level_cache_key = _source_cache_key(plan.source_family, contained, plan.volume_terms, plan.dates)
        plan.manual_steps = [
            "若配置中已有单独 NDL Digital PID，先核验该 PID。",
            "没有单独 PID 时，不要先按独立书处理析出文献。",
            "再找 host collection，并进入 host PID 搜索析出题名。",
            "host 未明确时保留 host 候选列表并输出人工路径。",
        ]
        return plan


class SecondaryScholarshipResolver(SourceResolver):
    resolver_name = "SecondaryScholarshipResolver"
    source_family = "secondary_scholarship"
    source_type = "secondary_scholarship"
    evidence_mode = "bibliographic_page_review"
    verification_mode = "secondary_scholarship"
    pid_scope_strategy = "bibliographic_metadata_then_page_review"

    def matches(self, footnote: ParsedFootnote, claim_text: str = "") -> bool:
        return _has_any(
            _blob_key(footnote, claim_text),
            ("儀礼と権力", "天皇の祭祀", "極東新秩序の模索"),
        ) and not _has_any(_blob_key(footnote, claim_text), ("日本外交文書", "日本近代思想大系", "原敬日記"))

    def resolve(self, footnote: ParsedFootnote, claim_text: str = "") -> ResolvedSourcePlan:
        plan = super().resolve(footnote, claim_text)
        plan.resolver = self.resolver_name
        plan.source_family = _clean(footnote.title) or self.source_family
        plan.source_type = self.source_type
        plan.evidence_mode = self.evidence_mode
        plan.verification_mode = self.verification_mode
        plan.pid_scope_strategy = self.pid_scope_strategy
        plan.warnings.append("secondary_scholarship_not_primary_source")
        plan.target_pid_queries = _unique([footnote.title, footnote.author, footnote.year])
        plan.global_queries = _build_global_queries(plan.query_buckets)
        plan.source_level_cache_key = _source_cache_key(plan.source_family, footnote.title, [], [footnote.year])
        plan.manual_steps = [
            "按现代研究核验书目信息、页码和论点承接。",
            "不强行要求原始史料式全文命中。",
            "报告应区分 secondary-source verification 与 primary-source verification。",
        ]
        return plan


def _volume_series_query_bucket(term: str) -> str:
    if any(
        marker in term
        for marker in (
            "帝國主張説明",
            "帝国主張説明",
            "牧野男",
            "牧野委員",
            "委任統治",
            "C式委任統治",
            "C類委任統治",
            "赤道以北",
            "獨領南洋",
            "独領南洋",
            "南洋群島",
            "太平洋群島",
            "會議ノ決定",
            "会議ノ決定",
            "決定ヲ受諾",
            "還附ノ決定",
            "軍備制限問題",
            "海軍軍備制限",
            "主力艦",
            "勢力比",
            "比率",
            "十対",
            "十對",
            "六割",
            "ヒューズ",
            "米國照會",
            "米国照会",
            "帝國政府回答",
            "帝国政府回答",
            "各國回答",
            "各国回答",
            "合衆國ノ提議",
            "合衆国ノ提議",
            "合衆國政府ノ提議",
            "合衆国政府ノ提議",
            "合衆國政府カ宣言",
            "合衆国政府カ宣言",
            "日本國政府ハ",
            "日本国政府ハ",
            "承諾シタル",
            "桂太郎",
            "タフト",
            "タフト陸軍長官",
            "桂・タフト",
            "ハリマン",
            "満鉄",
            "南満洲鉄道",
            "南滿洲鐵道",
            "共同經營",
            "共同経営",
            "豫備協定",
            "予備協定",
        )
    ):
        return "document_heading"
    if (
        "支那ニ於ケル" in term
        or "商業上" in term and ("門戸開放" in term or "門戶開放" in term)
        or any(marker in term for marker in ("巴里講和", "巴黎讲和", "パリ講和", "ワシントン会議", "ワシントン會議", "軍備制限"))
    ):
        return "document_title"
    if any(marker in term for marker in ("門戸開放", "門戶開放", "门户开放")):
        return "open_door"
    if any(marker in term for marker in ("機會均等", "機会均等", "机会均等")):
        return "equal_opportunity"
    if any(marker in term for marker in ("照會", "照会", "回答", "各國", "各国", "帝國政府", "帝国政府")):
        return "reply_position"
    if any(marker in term for marker in ("ジョン・ヘイ", "ヘイ", "米國務", "米国務", "國務長官", "国務長官")):
        return "person"
    return "other"


def _balanced_volume_series_specifics(specifics: Sequence[str], *, max_terms: int = 8) -> List[str]:
    bucket_limits = {
        "document_heading": 7,
        "document_title": 1,
        "open_door": 2,
        "equal_opportunity": 1,
        "reply_position": 2,
        "person": 1,
        "other": 1,
    }
    has_open_door_document_title = any("支那ニ於ケル" in term for term in specifics)
    if has_open_door_document_title:
        bucket_order = [
            "document_title",
            "open_door",
            "equal_opportunity",
            "reply_position",
            "person",
            "document_heading",
            "other",
        ]
    else:
        bucket_order = [
            "document_heading",
            "document_title",
            "open_door",
            "equal_opportunity",
            "reply_position",
            "person",
            "other",
        ]
    selected: List[str] = []
    for bucket in bucket_order:
        taken = 0
        bucket_terms = [term for term in specifics if _volume_series_query_bucket(term) == bucket]
        if bucket == "document_heading":
            bucket_terms = sorted(
                bucket_terms,
                key=lambda term: (
                    0
                    if any(marker in term for marker in ("米国案ノ十対六", "米國案ノ十對六", "十対六", "十對六"))
                    else 1
                    if "ヒューズ" in term
                    else 2
                    if any(marker in term for marker in ("比率", "勢力比", "六割"))
                    else 3
                    if "帝國主張説明" in term or "帝国主張説明" in term
                    else 4
                    if any(marker in term for marker in ("委任統治", "赤道以北", "獨領南洋", "独領南洋", "南洋群島", "太平洋群島", "決定"))
                    else 5
                    if any(marker in term for marker in ("タフト", "ハリマン", "南満", "南滿", "満鉄", "共同"))
                    else 6
                    if "軍備制限" in term or "海軍軍備" in term
                    else 7,
                    len(term),
                    term,
                ),
            )
        elif bucket == "document_title":
            bucket_terms = sorted(
                bucket_terms,
                key=lambda term: (
                    0 if "支那ニ於ケル" in term and "機會" in term else 1 if "支那ニ於ケル" in term else 2,
                    len(term),
                    term,
                ),
            )
        elif bucket == "person":
            bucket_terms = sorted(
                bucket_terms,
                key=lambda term: (
                    0 if "ジョン・ヘイ" in term else 1 if "國務" in term or "国務" in term else 2,
                    len(term),
                    term,
                ),
            )
        elif bucket == "reply_position":
            bucket_terms = sorted(
                bucket_terms,
                key=lambda term: (
                    0 if term in {"米國照會", "米国照会"} else 1 if "米國" in term or "米国" in term else 2 if "帝國" in term or "帝国" in term else 3,
                    len(term),
                    term,
                ),
            )
        else:
            bucket_terms = sorted(bucket_terms, key=lambda term: (len(term), term))
        for term in bucket_terms:
            if term in selected or _volume_series_query_bucket(term) != bucket:
                continue
            _append_unique(selected, term)
            taken += 1
            if len(selected) >= max_terms or taken >= bucket_limits[bucket]:
                break
        if len(selected) >= max_terms:
            break
    for term in specifics:
        if len(selected) >= max_terms:
            break
        _append_unique(selected, term)
    return selected


def _ensure_limited_terms(
    selected: Sequence[str],
    required: Sequence[str],
    *,
    max_terms: int,
) -> List[str]:
    output = _unique(selected)[:max_terms]
    pinned: set[str] = set()
    for value in _unique(required):
        if not value or value in output:
            if value:
                pinned.add(value)
            continue
        if len(output) < max_terms:
            _append_unique(output, value)
            pinned.add(value)
            continue
        replace_index = next(
            (
                index
                for index in range(len(output) - 1, -1, -1)
                if _volume_series_query_bucket(output[index]) == "other"
                and output[index] not in pinned
            ),
            next(
                (
                    index
                    for index in range(len(output) - 1, -1, -1)
                    if output[index] not in pinned
                ),
                len(output) - 1,
            ),
        )
        output[replace_index] = value
        pinned.add(value)
        output = _unique(output)[:max_terms]
    return output[:max_terms]


def _standalone_specific_allowed(term: str, blocked: set[str]) -> bool:
    if resolver_key(term) in blocked or _is_broad_standalone_query(term):
        return False
    return bool(term and len(term) >= 4)


def _build_global_queries(
    query_buckets: Dict[str, List[str]],
    *,
    max_queries: int = 12,
    prefer_balanced_volume_series: bool = False,
) -> List[str]:
    queries: List[str] = []
    anchors = _unique([*(query_buckets.get("host") or []), *(query_buckets.get("title") or [])])
    specifics = _unique(
        [
            *(query_buckets.get("contained") or []),
            *(query_buckets.get("document_title") or []),
            *(query_buckets.get("document_heading") or []),
            *(query_buckets.get("policy") or []),
            *(query_buckets.get("person") or []),
            *(query_buckets.get("anchor") or []),
            *(query_buckets.get("theme") or []),
            *(query_buckets.get("action") or []),
            *(query_buckets.get("page_near") or []),
            *(query_buckets.get("institution") or []),
            *(query_buckets.get("special_term") or []),
            *(query_buckets.get("date") or []),
        ]
    )
    volumes = query_buckets.get("volume") or []
    blocked = {resolver_key(term) for term in query_buckets.get("blocked_standalone") or []}

    if prefer_balanced_volume_series:
        balanced = _balanced_volume_series_specifics(specifics, max_terms=max(4, min(8, max_queries)))
        for anchor in anchors[:1]:
            for volume in volumes[:1] or [""]:
                for specific in balanced[:2]:
                    _append_unique(queries, " ".join(item for item in [anchor, volume, specific] if item))
                    if len(queries) >= max_queries:
                        return queries
        for specific in balanced:
            if not _standalone_specific_allowed(specific, blocked):
                continue
            _append_unique(queries, specific)
            if len(queries) >= max_queries:
                return queries
        for anchor in anchors:
            for specific in balanced:
                _append_unique(queries, " ".join([anchor, specific]))
                if len(queries) >= max_queries:
                    return queries

    for anchor in anchors:
        for volume in volumes:
            for specific in specifics:
                _append_unique(queries, " ".join([anchor, volume, specific]))
                if len(queries) >= max_queries:
                    return queries
    for anchor in anchors:
        for specific in specifics:
            _append_unique(queries, " ".join([anchor, specific]))
            if len(queries) >= max_queries:
                return queries
    for specific in specifics:
        if not _standalone_specific_allowed(specific, blocked):
            continue
        _append_unique(queries, specific)
        if len(queries) >= max_queries:
            return queries
    return queries[:max_queries]


def _source_cache_key(source_family: str, title: str, volume_terms: Sequence[str], dates: Sequence[str]) -> str:
    parts = [source_family, title, *volume_terms[:3], *dates[:2]]
    return resolver_key("|".join(part for part in parts if part)) or "generic"


class SourceResolverRegistry:
    def __init__(self, resolvers: Optional[Sequence[SourceResolver]] = None):
        self.resolvers = list(
            resolvers
            or [
                NihonKindaiShisoTaikeiResolver(),
                NihonGaikoBunshoResolver(),
                DiaryDateResolver(),
                DownloadableMonographResolver(),
                ContainedDocumentResolver(),
                SecondaryScholarshipResolver(),
                SourceResolver(),
            ]
        )

    def resolve(self, footnote: ParsedFootnote, claim_text: str = "") -> ResolvedSourcePlan:
        for resolver in self.resolvers:
            if resolver.matches(footnote, claim_text):
                return resolver.resolve(footnote, claim_text)
        return SourceResolver().resolve(footnote, claim_text)


DEFAULT_SOURCE_RESOLVER_REGISTRY = SourceResolverRegistry()


def resolve_source(footnote: ParsedFootnote, *, claim_text: str = "") -> ResolvedSourcePlan:
    return DEFAULT_SOURCE_RESOLVER_REGISTRY.resolve(footnote, claim_text)
