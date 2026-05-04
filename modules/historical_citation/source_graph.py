from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .footnote_parser import extract_volume_terms
from .models import CitationCandidate, ParsedFootnote
from .source_resolvers import resolve_source


def _clean_text(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"\s+", " ", text).strip()


_DATE_CONTEXT_PATTERN = re.compile(
    r"(?:1[89]\d{2}|20\d{2})\s*年(?:\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)?"
    r"|(?:明治|大正|昭和|平成|令和)\s*[0-9一二三四五六七八九十百廿卅元]+\s*年(?:\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)?"
)


def _diary_local_paragraph_context(candidate: CitationCandidate) -> str:
    paragraph = unicodedata.normalize("NFKC", _clean_text(candidate.paragraph_text))
    claim = unicodedata.normalize("NFKC", _clean_text(candidate.translation_text))
    if not paragraph or not claim:
        return paragraph
    index = paragraph.find(claim)
    if index < 0:
        return paragraph[:320]
    prefix = paragraph[:index]
    matches = list(_DATE_CONTEXT_PATTERN.finditer(prefix))
    if matches:
        start = max(0, matches[-1].start())
    else:
        start = max(0, index - 180)
    end = min(len(paragraph), index + len(claim))
    return paragraph[start:end]


def normalize_source_key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    replacements = {
        "國": "国",
        "會": "会",
        "學": "学",
        "條": "条",
        "關": "関",
        "說": "説",
        "書": "書",
        "卷": "巻",
        "册": "冊",
        "·": "・",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"[\s　「」『』《》〈〉（）()\[\]［］・･·,，.。:：;；、\-‐‑–—_/]+", "", text)


def _append_unique(items: List[str], value: Any) -> None:
    cleaned = _clean_text(value)
    if cleaned and cleaned not in items:
        items.append(cleaned)


def _unique(values: Iterable[Any]) -> List[str]:
    items: List[str] = []
    for value in values:
        _append_unique(items, value)
    return items


def _is_broad_standalone_query(value: str) -> bool:
    cleaned = _clean_text(value)
    return bool(
        re.fullmatch(r"(?:1[89]\d{2}|20\d{2})年?", cleaned)
        or re.fullmatch(r"(?:1[89]\d{2}|20\d{2})年\d{1,2}月\d{1,2}日", cleaned)
        or re.fullmatch(r"(?:1[89]\d{2}|20\d{2})[\-/\.]\d{1,2}[\-/\.]\d{1,2}", cleaned)
        or re.fullmatch(r"(?:明治|大正|昭和|平成|令和)[0-9一二三四五六七八九十百元]+年?", cleaned)
        or re.fullmatch(r"(?:明治|大正|昭和|平成|令和)[0-9一二三四五六七八九十百元]+年\d{1,2}月\d{1,2}日", cleaned)
    )


def _standalone_specific_allowed(term: str, blocked_terms: Sequence[str]) -> bool:
    if normalize_source_key(term) in {normalize_source_key(blocked) for blocked in blocked_terms}:
        return False
    if _is_broad_standalone_query(term):
        return False
    return bool(_clean_text(term) and len(_clean_text(term)) >= 4)


def _volume_series_query_bucket(term: str) -> str:
    if "支那ニ於ケル" in term or "商業上" in term and ("門戸開放" in term or "門戶開放" in term):
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
        "document_title": 1,
        "open_door": 2,
        "equal_opportunity": 1,
        "reply_position": 2,
        "person": 1,
        "other": 1,
    }
    bucket_order = ["document_title", "open_door", "equal_opportunity", "reply_position", "person", "other"]
    selected: List[str] = []
    for bucket in bucket_order:
        taken = 0
        bucket_terms = [term for term in specifics if _volume_series_query_bucket(term) == bucket]
        if bucket == "document_title":
            bucket_terms = sorted(bucket_terms, key=lambda term: (0 if "支那ニ於ケル" in term else 1, len(term), term))
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


def _text_blob(footnote: ParsedFootnote, claim_text: str = "") -> str:
    return " ".join(
        _clean_text(value)
        for value in [
            footnote.text,
            footnote.title,
            footnote.host_title,
            footnote.contained_title,
            footnote.ndl_keyword,
            claim_text,
        ]
        if _clean_text(value)
    )


def extract_source_dates(text: str) -> List[str]:
    normalized = unicodedata.normalize("NFKC", text or "")
    dates: List[str] = []
    for pattern in (
        r"(1[89]\d{2}|20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"(明治|大正|昭和|平成|令和)\s*([0-9一二三四五六七八九十百元]+)\s*年\s*(\d{1,2})?\s*月?\s*(\d{1,2})?\s*日?",
        r"(1[89]\d{2}|20\d{2})\s*年",
    ):
        for match in re.finditer(pattern, normalized):
            _append_unique(dates, match.group(0))
    return dates[:8]


def _has_any(text_key: str, markers: Sequence[str]) -> bool:
    return any(normalize_source_key(marker) in text_key for marker in markers)


SOURCE_PID_HINTS: Dict[str, List[str]] = {
    "nihon_kindai_shiso_taikei_religion_state": ["13260166"],
    "imperial_constitution_gikai": ["1272168"],
}


SOURCE_AVAILABILITY_HINTS: Dict[str, str] = {
    "nihon_kindai_shiso_taikei_religion_state": "fulltext-only",
    "nihon_gaiko_bunsho": "mixed",
    "hara_takashi_diary": "mixed",
    "imperial_constitution_gikai": "downloadable",
    "contained_document": "unknown",
    "secondary_scholarship": "metadata-or-downloadable",
}


@dataclass
class SourceGraphNode:
    source_family: str
    source_type: str
    resolver: str
    title: str = ""
    host_title: str = ""
    contained_title: str = ""
    volume_terms: List[str] = field(default_factory=list)
    year: str = ""
    dates: List[str] = field(default_factory=list)
    known_pid_candidates: List[str] = field(default_factory=list)
    availability: str = "unknown"
    evidence_route: str = "metadata_bridge"
    special_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceQueryPlan:
    source_family: str
    resolver: str
    title_bucket: List[str] = field(default_factory=list)
    host_bucket: List[str] = field(default_factory=list)
    contained_bucket: List[str] = field(default_factory=list)
    volume_bucket: List[str] = field(default_factory=list)
    date_bucket: List[str] = field(default_factory=list)
    person_bucket: List[str] = field(default_factory=list)
    policy_bucket: List[str] = field(default_factory=list)
    special_term_bucket: List[str] = field(default_factory=list)
    blocked_standalone_terms: List[str] = field(default_factory=list)
    known_pid_candidates: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def ordered_terms(self) -> List[str]:
        return _unique(
            [
                *self.contained_bucket,
                *self.policy_bucket,
                *self.person_bucket,
                *self.special_term_bucket,
                *self.date_bucket,
                *self.volume_bucket,
                *self.host_bucket,
                *self.title_bucket,
            ]
        )

    def global_fulltext_queries(self, *, max_queries: int = 8) -> List[str]:
        queries: List[str] = []
        anchors = _unique([*self.host_bucket, *self.title_bucket])
        specifics = _unique(
            [
                *self.contained_bucket,
                *self.policy_bucket,
                *self.person_bucket,
                *self.special_term_bucket,
                *self.date_bucket,
            ]
        )
        volume_terms = list(self.volume_bucket)
        if self.resolver == "NihonGaikoBunshoResolver":
            balanced = _balanced_volume_series_specifics(specifics, max_terms=max(4, min(8, max_queries)))
            for anchor in anchors[:1]:
                for volume in volume_terms[:1] or [""]:
                    for specific in balanced[:2]:
                        _append_unique(queries, " ".join(item for item in [anchor, volume, specific] if item))
                        if len(queries) >= max_queries:
                            return queries
            for specific in balanced:
                if not _standalone_specific_allowed(specific, self.blocked_standalone_terms):
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
            for volume in volume_terms:
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
            if not _standalone_specific_allowed(specific, self.blocked_standalone_terms):
                continue
            _append_unique(queries, specific)
            if len(queries) >= max_queries:
                return queries
        return queries[:max_queries]


def build_source_graph_node(footnote: ParsedFootnote, *, claim_text: str = "") -> SourceGraphNode:
    resolved = resolve_source(footnote, claim_text=claim_text)
    blob = _text_blob(footnote, claim_text)
    blob_key = normalize_source_key(blob)
    title = _clean_text(footnote.title)
    host = _clean_text(footnote.host_title)
    contained = _clean_text(footnote.contained_title)
    volume_terms = extract_volume_terms(blob)
    dates = extract_source_dates(blob)

    source_family = "generic"
    source_type = "monograph"
    resolver = "GenericSourceResolver"
    evidence_route = "metadata_bridge"
    known_pids: List[str] = []

    if _has_any(blob_key, ("日本近代思想大系", "宗教と国家")):
        source_family = "日本近代思想大系"
        source_type = "source_collection"
        resolver = "NihonKindaiShisoTaikeiResolver"
        evidence_route = "pid_snippet"
        known_pids = list(SOURCE_PID_HINTS["nihon_kindai_shiso_taikei_religion_state"])
    elif _has_any(blob_key, ("日本外交文書", "日本外交文书")):
        source_family = "日本外交文書"
        source_type = "volume_series"
        resolver = "NihonGaikoBunshoResolver"
        evidence_route = "pid_snippet_or_download_ocr"
    elif _has_any(blob_key, ("原敬日記", "原敬日记")):
        source_family = "原敬日記"
        source_type = "diary"
        resolver = "DiaryDateResolver"
        evidence_route = "date_snippet_or_download_ocr"
    elif _has_any(blob_key, ("帝国憲法義解", "帝國憲法義解", "皇室典範義解")):
        source_family = "帝国憲法義解・皇室典範義解"
        source_type = "downloadable_monograph"
        resolver = "DownloadableMonographResolver"
        evidence_route = "download_ocr"
        known_pids = list(SOURCE_PID_HINTS["imperial_constitution_gikai"])
    elif _clean_text(getattr(footnote, "source_relation", "")) == "contained_in_host" or host:
        source_family = host or "contained_document"
        source_type = "contained_document"
        resolver = "ContainedDocumentResolver"
        evidence_route = "host_then_pid_snippet"

    if source_type == "monograph" and _has_any(blob_key, ("儀礼と権力", "天皇の祭祀", "極東新秩序の模索")):
        source_type = "secondary_scholarship"
        resolver = "SecondaryScholarshipResolver"
        evidence_route = "bibliographic_page_review"

    if resolved.resolver != "GenericSourceResolver" or resolver == "GenericSourceResolver":
        source_family = resolved.source_family
        source_type = resolved.source_type
        resolver = resolved.resolver
        evidence_route = resolved.evidence_mode
        volume_terms = resolved.volume_terms or volume_terms
        dates = resolved.dates or dates
        if resolved.known_pid_candidates:
            known_pids = list(resolved.known_pid_candidates)

    special_terms: List[str] = []
    if "大麻" in blob and (
        "神宮" in blob
        or "皇大神宮" in blob
        or "神社" in blob
        or "御札" in blob
        or "流言" in blob
        or "配布" in blob
    ):
        special_terms.append("神宮大麻")

    availability_key = {
        "NihonKindaiShisoTaikeiResolver": "nihon_kindai_shiso_taikei_religion_state",
        "NihonGaikoBunshoResolver": "nihon_gaiko_bunsho",
        "DiaryDateResolver": "hara_takashi_diary",
        "DownloadableMonographResolver": "imperial_constitution_gikai",
        "ContainedDocumentResolver": "contained_document",
        "SecondaryScholarshipResolver": "secondary_scholarship",
    }.get(resolver, "generic")

    return SourceGraphNode(
        source_family=source_family,
        source_type=source_type,
        resolver=resolver,
        title=title,
        host_title=host,
        contained_title=contained,
        volume_terms=volume_terms,
        year=_clean_text(footnote.year),
        dates=dates,
        known_pid_candidates=known_pids,
        availability=SOURCE_AVAILABILITY_HINTS.get(availability_key, "unknown"),
        evidence_route=evidence_route,
        special_terms=special_terms,
    )


def _imperial_title_variants(title: str) -> List[str]:
    base = _clean_text(title)
    variants: List[str] = []
    for value in [
        base,
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


def _hay_policy_terms(blob: str) -> Dict[str, List[str]]:
    person: List[str] = []
    policy: List[str] = []
    if any(term in blob for term in ("约翰", "海伊", "John Hay", "Hay", "ヘイ")):
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
    if any(term in blob for term in ("门户开放", "門戸開放", "門戶開放", "机会均等", "機會均等", "照会", "回答")):
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
    return {"person": person, "policy": policy}


def _sort_volume_terms(terms: Sequence[str]) -> List[str]:
    return sorted(
        _unique(terms),
        key=lambda term: (
            0 if "巻" in term else 1 if "卷" in term else 2 if "年" in term else 3,
            len(term),
            term,
        ),
    )


def _special_term_queries(blob: str) -> tuple[List[str], List[str]]:
    if "大麻" not in blob:
        return [], []
    qualifiers = [
        "神宮大麻",
        "皇大神宮",
        "神田神社",
        "窪田次郎",
        "配布",
        "流言",
        "御札",
    ]
    if not any(term in blob for term in qualifiers):
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


def build_source_query_plan(footnote: ParsedFootnote, *, claim_text: str = "") -> SourceQueryPlan:
    node = build_source_graph_node(footnote, claim_text=claim_text)
    resolved = resolve_source(footnote, claim_text=claim_text)
    blob = _text_blob(footnote, claim_text)
    plan = SourceQueryPlan(
        source_family=node.source_family,
        resolver=node.resolver,
        known_pid_candidates=list(node.known_pid_candidates),
    )
    for value in [node.title, footnote.ndl_keyword]:
        _append_unique(plan.title_bucket, value)
    for value in [node.host_title]:
        _append_unique(plan.host_bucket, value)
    for value in [node.contained_title]:
        _append_unique(plan.contained_bucket, value)
    for value in node.volume_terms:
        _append_unique(plan.volume_bucket, value)
    for value in resolved.volume_terms:
        _append_unique(plan.volume_bucket, value)
    plan.volume_bucket = _sort_volume_terms(plan.volume_bucket)
    for value in [*node.dates, *resolved.dates]:
        _append_unique(plan.date_bucket, value)

    if node.resolver == "DownloadableMonographResolver":
        plan.title_bucket = _unique([*plan.title_bucket, *_imperial_title_variants(node.title)])

    if node.resolver == "NihonGaikoBunshoResolver":
        hay_terms = _hay_policy_terms(blob)
        for value in hay_terms["person"]:
            _append_unique(plan.person_bucket, value)
        for value in hay_terms["policy"]:
            _append_unique(plan.policy_bucket, value)

    if node.resolver == "DiaryDateResolver":
        for value in extract_source_dates(blob):
            _append_unique(plan.date_bucket, value)

    special_terms, blocked_terms = _special_term_queries(blob)
    for value in special_terms:
        _append_unique(plan.special_term_bucket, value)
    for value in blocked_terms:
        _append_unique(plan.blocked_standalone_terms, value)
    for bucket_name, values in (resolved.query_buckets or {}).items():
        target = {
            "title": plan.title_bucket,
            "host": plan.host_bucket,
            "contained": plan.contained_bucket,
            "volume": plan.volume_bucket,
            "date": plan.date_bucket,
            "person": plan.person_bucket,
            "policy": plan.policy_bucket,
            "special_term": plan.special_term_bucket,
            "blocked_standalone": plan.blocked_standalone_terms,
        }.get(bucket_name)
        if target is None:
            continue
        for value in values:
            _append_unique(target, value)
    plan.volume_bucket = _sort_volume_terms(plan.volume_bucket)

    return plan


def _manual_query_buckets(plan: SourceQueryPlan, resolved: Any) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {}
    for bucket_name, values in (
        ("title", plan.title_bucket),
        ("host", plan.host_bucket),
        ("contained", plan.contained_bucket),
        ("volume", plan.volume_bucket),
        ("date", plan.date_bucket),
        ("person", plan.person_bucket),
        ("policy", plan.policy_bucket),
        ("special_term", plan.special_term_bucket),
        ("blocked_standalone", plan.blocked_standalone_terms),
    ):
        cleaned = _unique(values)
        if cleaned:
            buckets[bucket_name] = cleaned[:8]

    resolver_buckets = getattr(resolved, "query_buckets", {}) or {}
    if isinstance(resolver_buckets, dict):
        for bucket_name, values in resolver_buckets.items():
            if not isinstance(values, list):
                continue
            target = buckets.setdefault(str(bucket_name), [])
            for value in values:
                _append_unique(target, value)
            if len(target) > 8:
                del target[8:]
    return buckets


def build_manual_search_recipe(
    footnote: ParsedFootnote,
    *,
    claim_text: str = "",
    current_status: str = "",
) -> Dict[str, Any]:
    node = build_source_graph_node(footnote, claim_text=claim_text)
    plan = build_source_query_plan(footnote, claim_text=claim_text)
    resolved = resolve_source(footnote, claim_text=claim_text)
    steps: List[str] = []
    reason = ""
    if node.source_type == "source_collection":
        steps = [
            "先确认宿主书/卷册 PID，而不是把析出题名当独立书全站泛搜。",
            "进入宿主 PID 后，用析出题名、制度词、人名或事件词做 PID 内全文 snippet。",
            "若只能命中目录或书名，保留为 lead，不作为最终证据。",
        ]
        reason = "source_collection_requires_host_pid_context"
    elif node.source_type == "volume_series":
        steps = [
            "先解析卷号、年份、册次，再进入对应卷册 PID。",
            "在目标卷册 PID 内搜索文书题名、日期、人名和外交政策词。",
            "只命中系列名或目录时，应标为 fulltext_lead_only。",
        ]
        reason = "volume_series_requires_volume_pid"
    elif node.source_type == "diary":
        steps = [
            "先抽取脚注或正文事件链中的年月日。",
            "按日期定位日记卷册，再用人名和事件词补检。",
            "页码只作二次校验，不作为唯一入口。",
        ]
        reason = "diary_requires_date_first_lookup"
    elif node.source_type == "downloadable_monograph":
        steps = [
            "先用合刻题名、分题名、新旧字体变体寻找 NDL Digital 可下载 PID。",
            "确认 PID 后复用页映射、OCR 和小页窗缓存。",
            "页映射失败时先尝试 PID 内 snippet 定位扫描页。",
        ]
        reason = "downloadable_monograph_requires_pid_and_cache_reuse"
    elif node.source_type == "contained_document":
        steps = [
            "不要把析出文献直接视为独立书。",
            "先找 host collection，再在 host PID 内搜索析出题名和事件词。",
            "host 未明确时保留候选 host 列表并输出人工路径。",
        ]
        reason = "contained_document_requires_host_discovery"
    elif node.source_type == "secondary_scholarship":
        steps = [
            "按现代研究处理，优先核对书目信息、页码和论点承接。",
            "若不可全文检索，不应强行套用原始史料 OCR 标准。",
        ]
        reason = "secondary_scholarship_uses_bibliographic_review"
    else:
        steps = [
            "先确认题名、作者、出版年和页码。",
            "若候选不可下载，尝试 PID 内全文 snippet 或其他平台元数据桥接。",
        ]
        reason = "generic_manual_review"

    return {
        "reason": reason,
        "current_status": current_status,
        "source_family": node.source_family,
        "resolver": node.resolver,
        "source_level_cache_key": resolved.source_level_cache_key,
        "verification_mode": resolved.verification_mode,
        "pid_scope_strategy": resolved.pid_scope_strategy,
        "known_pid_candidates": node.known_pid_candidates,
        "suggested_pid_scope": node.known_pid_candidates[0] if node.known_pid_candidates else "",
        "suggested_queries": plan.global_fulltext_queries(max_queries=8),
        "target_pid_queries": _unique(resolved.target_pid_queries)[:12],
        "global_queries": _unique(resolved.global_queries)[:12],
        "query_buckets": _manual_query_buckets(plan, resolved),
        "blocked_standalone_terms": plan.blocked_standalone_terms,
        "steps": steps,
        "resolver_steps": resolved.manual_steps,
        "warnings": resolved.warnings,
    }


def candidate_source_claim_context(candidate: CitationCandidate) -> str:
    claim_text = _clean_text(candidate.translation_text)
    preliminary = resolve_source(candidate.footnote, claim_text=claim_text)
    if preliminary.resolver != "DiaryDateResolver":
        return claim_text
    combined = _clean_text(" ".join([claim_text, _diary_local_paragraph_context(candidate)]))
    if combined and combined != claim_text:
        candidate.artifacts["source_query_context_scope"] = "translation_plus_paragraph_for_diary"
        return combined
    return claim_text


def attach_source_graph_artifacts(candidate: CitationCandidate) -> CitationCandidate:
    claim_text = candidate_source_claim_context(candidate)
    node = build_source_graph_node(candidate.footnote, claim_text=claim_text)
    plan = build_source_query_plan(candidate.footnote, claim_text=claim_text)
    resolved = resolve_source(candidate.footnote, claim_text=claim_text)
    candidate.artifacts["source_graph"] = node.to_dict()
    candidate.artifacts["source_query_plan"] = plan.to_dict()
    candidate.artifacts["source_resolver_plan"] = resolved.to_dict()
    candidate.artifacts["manual_search_recipe"] = build_manual_search_recipe(
        candidate.footnote,
        claim_text=claim_text,
        current_status=candidate.verification_status,
    )
    for note in [
        f"source_graph_resolver:{node.resolver}",
        *(f"source_graph_known_pid:{pid}" for pid in node.known_pid_candidates),
    ]:
        if note not in candidate.notes:
            candidate.notes.append(note)
    return candidate


def candidate_deduplication_key(item: CitationCandidate | Dict[str, Any], *, paper_id: str = "") -> str:
    if isinstance(item, CitationCandidate):
        footnote = item.footnote
        footnote_id = item.footnote_id
        paragraph_index = item.paragraph_index
        candidate_id = item.candidate_id
        quote = item.translation_text
        title = footnote.host_title or footnote.title or footnote.ndl_keyword
        footnote_text = footnote.text
    else:
        footnote_payload = item.get("footnote") or {}
        footnote_id = item.get("footnote_id") or footnote_payload.get("id") or ""
        paragraph_index = item.get("paragraph_index") or ""
        candidate_id = item.get("candidate_id") or ""
        quote = item.get("translation_text") or item.get("paragraph_text") or ""
        title = footnote_payload.get("host_title") or footnote_payload.get("title") or footnote_payload.get("ndl_keyword") or ""
        footnote_text = footnote_payload.get("text") or ""
    parts = [
        paper_id,
        str(candidate_id),
        str(footnote_id),
        str(paragraph_index),
        normalize_source_key(title),
        normalize_source_key(quote)[:160],
        normalize_source_key(footnote_text)[:160],
    ]
    return "\x1f".join(parts)


def dedupe_candidates(candidates: Sequence[CitationCandidate], *, paper_id: str = "") -> List[CitationCandidate]:
    seen: set[str] = set()
    deduped: List[CitationCandidate] = []
    for candidate in candidates:
        key = candidate_deduplication_key(candidate, paper_id=paper_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def dedupe_result_dicts(items: Sequence[Dict[str, Any]], *, paper_id: str = "") -> List[Dict[str, Any]]:
    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for item in items:
        key = candidate_deduplication_key(item, paper_id=paper_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
