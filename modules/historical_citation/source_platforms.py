from __future__ import annotations

from dataclasses import dataclass
import html
import os
from pathlib import Path
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Sequence
from urllib.parse import quote_plus, urljoin

import requests

from .models import CitationCandidate, NDLSearchMatch, ParsedFootnote
from .ndl_search import (
    iter_ndl_search_keywords,
    normalize_match_text,
    resolve_ndlsearch_detail_url,
    score_ndl_record,
    search_ndl_digital_fulltext,
    search_ndl_public_api,
    search_ndlsearch_fulltext,
    title_query_terms,
)
from .source_acquisition import (
    build_restricted_download_requests,
    download_public_pdf,
    is_likely_digital_ndl_pid,
    select_preferred_source_match,
)


JAPAN_SEARCH_SPARQL_URL = "https://jpsearch.go.jp/rdf/sparql/"
INTERNET_ARCHIVE_ADVANCED_SEARCH_URL = "https://archive.org/advancedsearch.php"
INTERNET_ARCHIVE_METADATA_URL = "https://archive.org/metadata/{identifier}"
JSTAGE_GLOBAL_SEARCH_URL = "https://www.jstage.jst.go.jp/result/global/-char/ja"
CINII_RESEARCH_SEARCH_URL = "https://cir.nii.ac.jp/all"
JACAR_SEARCH_URL = "https://www.jacar.archives.go.jp/aj/meta/result"
DIET_PROCEEDINGS_API_URL = "https://kokkai.ndl.go.jp/api/speech"
EGOV_LAW_SEARCH_URL = "https://elaws.e-gov.go.jp/search/elawsSearch/elaws_search/lsg0100/"


class SourcePlatformAdapter(Protocol):
    """Minimal contract for online source repositories.

    New platforms should implement search first. If the platform can provide
    PDFs or page-window downloads, it can also implement the acquisition hooks.
    The verifier keeps OCR, alignment, and reporting platform-neutral.
    """

    name: str

    def search(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        ...

    def select_preferred_match(self, matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
        ...

    def download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        ...

    def build_restricted_download_requests(
        self,
        *,
        footnote: ParsedFootnote,
        top_match: Optional[NDLSearchMatch],
        fallback_title: str,
        output_dir: Path,
        start_page: int,
        end_page: int,
    ) -> List[Dict[str, Any]]:
        ...


def normalize_source_record(record: Any, *, platform: str) -> NDLSearchMatch:
    if isinstance(record, dict):
        title = record.get("title", "") or ""
        author = record.get("author")
        year = record.get("date")
        publisher = record.get("publisher")
        url = record.get("url", "") or ""
        ndl_id = record.get("ndl_id")
        pdf_url = record.get("pdf_url")
        metadata = dict(record.get("metadata", {}) or {})
    else:
        title = getattr(record, "title", "") or ""
        author = getattr(record, "author", None)
        year = getattr(record, "date", None)
        publisher = getattr(record, "publisher", None)
        url = getattr(record, "url", "") or ""
        ndl_id = getattr(record, "ndl_id", None)
        pdf_url = getattr(record, "pdf_url", None)
        metadata = dict(getattr(record, "metadata", {}) or {})
    platform_item_id = ndl_id or metadata.get("identifier") or url or None
    return NDLSearchMatch(
        title=title,
        url=url,
        ndl_id=ndl_id,
        platform=platform,
        platform_item_id=platform_item_id,
        author=author,
        date=year,
        publisher=publisher,
        pdf_url=pdf_url,
        metadata=metadata,
    )


def is_plausible_source_match(
    footnote: ParsedFootnote,
    match: NDLSearchMatch,
    *,
    min_score: float = 0.35,
) -> bool:
    """Reject obvious title/metadata mismatches before download.

    This is intentionally conservative: a strong title match is enough, and a
    weaker title can pass if author/year/publisher anchors support it.
    """

    score = score_ndl_record(
        footnote,
        title=match.title,
        author=match.author,
        year=match.date,
        publisher=match.publisher,
    )
    match.score = score
    if score >= min_score:
        return True
    if not footnote.title:
        return True
    match.metadata["mismatch_reason"] = f"score_below_threshold:{score:.3f}"
    return False


@dataclass
class NDLSourcePlatformAdapter:
    download_module_getter: Callable[[], Any]
    prefer_external_module: bool = False
    allow_external_fallback: bool = True
    name: str = "ndl"

    def search(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        records: List[Any] = []
        if self.prefer_external_module:
            records = self._search_via_download_module(footnote, max_results=max_results, use_api=True)
        if not records:
            try:
                records = search_ndl_public_api(footnote, max_results=max_results)
            except Exception:
                records = []
        if not records and self.allow_external_fallback:
            records = self._search_via_download_module(footnote, max_results=max_results, use_api=True)
        if not records and self.allow_external_fallback:
            records = self._search_via_download_module(footnote, max_results=max_results, use_api=False)
        fulltext_records: List[Any] = []
        has_host_title = bool(getattr(footnote, "host_title", ""))
        should_try_fulltext = (
            has_host_title
            or not any(self._record_has_download_hint(record) for record in records)
            or os.environ.get("HISTORICAL_CITATION_ENABLE_NDLSEARCH_HTML") == "1"
        )
        if should_try_fulltext:
            fulltext_records = self._search_via_ndlsearch_fulltext(footnote, max_results=max_results)
        if fulltext_records:
            records = self._merge_records(records, fulltext_records)

        matches = [normalize_source_record(record, platform=self.name) for record in records]
        for rank, match in enumerate(matches, start=1):
            match.metadata.setdefault("source_rank", rank)
        for match in matches:
            self._resolve_match_detail_pid(match)
        matches = [match for match in matches if match.title or match.url]
        plausible_matches: List[NDLSearchMatch] = []
        rejected_matches: List[NDLSearchMatch] = []
        for match in matches:
            if is_plausible_source_match(footnote, match):
                plausible_matches.append(match)
            else:
                match.metadata["source_mismatch"] = True
                rejected_matches.append(match)
        if plausible_matches:
            matches = plausible_matches
        else:
            fallback_match = next((match for match in matches if float(match.score or 0) >= 0.20), None)
            if fallback_match is not None:
                fallback_match.metadata.pop("source_mismatch", None)
                fallback_match.metadata["source_match_warning"] = "ndl_relevance_low_metadata_score_fallback"
                matches = [fallback_match] + [match for match in rejected_matches if match is not fallback_match]
            else:
                matches = rejected_matches
        matches.sort(
            key=lambda item: (
                bool(item.metadata.get("source_mismatch")),
                -self._effective_source_score(item),
                0 if self._match_has_download_hint(item) else 1,
                int(item.metadata.get("source_rank") or 9999),
            )
        )
        return matches[:max_results]

    def _match_has_download_hint(self, match: NDLSearchMatch) -> bool:
        return bool(
            is_likely_digital_ndl_pid(getattr(match, "ndl_id", None))
            or getattr(match, "pdf_url", None)
            or "dl.ndl.go.jp" in str(getattr(match, "url", "") or "")
        )

    def _effective_source_score(self, match: NDLSearchMatch) -> float:
        score = float(getattr(match, "score", 0) or 0)
        if self._match_has_download_hint(match):
            score += 0.12
        metadata = getattr(match, "metadata", {}) or {}
        if isinstance(metadata, dict) and metadata.get("fulltext_hints"):
            score += 0.10
        return score

    def _merge_records(self, *record_groups: Sequence[Any]) -> List[Any]:
        merged: List[Any] = []
        seen_by_key: Dict[str, Any] = {}
        for records in record_groups:
            for record in records or []:
                if isinstance(record, dict):
                    key = str(record.get("ndl_id") or record.get("url") or record.get("title") or "")
                else:
                    key = str(
                        getattr(record, "ndl_id", None)
                        or getattr(record, "url", None)
                        or getattr(record, "title", None)
                        or ""
                    )
                if key and key in seen_by_key:
                    self._merge_record_metadata(seen_by_key[key], record)
                    continue
                if key:
                    seen_by_key[key] = record
                merged.append(record)
        return merged

    def _merge_record_metadata(self, existing: Any, incoming: Any) -> None:
        if not isinstance(existing, dict) or not isinstance(incoming, dict):
            return
        for field in ("ndl_id", "url", "author", "date", "publisher", "pdf_url"):
            if not existing.get(field) and incoming.get(field):
                existing[field] = incoming.get(field)
        existing_metadata = existing.setdefault("metadata", {})
        incoming_metadata = incoming.get("metadata") or {}
        if not isinstance(existing_metadata, dict) or not isinstance(incoming_metadata, dict):
            return
        routes = existing_metadata.setdefault("search_routes", [])
        if not isinstance(routes, list):
            existing_metadata["search_routes"] = routes = []
        for route in [existing_metadata.get("search_route"), incoming_metadata.get("search_route")]:
            if route and route not in routes:
                routes.append(route)
        if incoming_metadata.get("search_route") and not existing_metadata.get("search_route"):
            existing_metadata["search_route"] = incoming_metadata.get("search_route")
        for key, value in incoming_metadata.items():
            if key == "fulltext_hints":
                hints = existing_metadata.setdefault("fulltext_hints", [])
                if not isinstance(hints, list):
                    existing_metadata["fulltext_hints"] = hints = []
                for hint in value or []:
                    if isinstance(hint, dict) and not any(
                        isinstance(item, dict)
                        and item.get("snippet") == hint.get("snippet")
                        and item.get("pdf_page") == hint.get("pdf_page")
                        for item in hints
                    ):
                        hints.append(hint)
            elif key not in existing_metadata or existing_metadata.get(key) in (None, "", []):
                existing_metadata[key] = value

    def _record_has_download_hint(self, record: Any) -> bool:
        if isinstance(record, dict):
            ndl_id = record.get("ndl_id")
            url = record.get("url") or ""
            pdf_url = record.get("pdf_url")
        else:
            ndl_id = getattr(record, "ndl_id", None)
            url = getattr(record, "url", "") or ""
            pdf_url = getattr(record, "pdf_url", None)
        return bool(ndl_id or pdf_url or "dl.ndl.go.jp" in str(url))

    def _resolve_match_detail_pid(self, match: NDLSearchMatch) -> None:
        if match.ndl_id or not match.url:
            return
        resolution = resolve_ndlsearch_detail_url(match.url)
        match.metadata["ndlsearch_detail_resolution"] = {
            key: value for key, value in resolution.items() if key != "url"
        }
        ndl_ids = resolution.get("ndl_ids") or []
        if ndl_ids:
            match.ndl_id = str(ndl_ids[0])
            match.url = f"https://dl.ndl.go.jp/pid/{match.ndl_id}"
            match.platform_item_id = match.ndl_id
            match.metadata["resolved_from_ndlsearch_url"] = True

    def _search_via_download_module(
        self,
        footnote: ParsedFootnote,
        *,
        max_results: int,
        use_api: bool,
    ) -> List[Any]:
        module = self.download_module_getter()
        collected: List[Any] = []
        seen_keys: set[str] = set()
        for keyword in iter_ndl_search_keywords(footnote):
            try:
                records = module.search(
                    keyword,
                    max_results=max_results,
                    use_api=use_api,
                    headless=True,
                )
            except BaseException:
                continue
            for record in records:
                key = getattr(record, "ndl_id", None) or getattr(record, "url", None) or getattr(record, "title", None)
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    collected.append(record)
            if collected:
                break
        return collected[:max_results]

    def _search_via_ndlsearch_fulltext(
        self,
        footnote: ParsedFootnote,
        *,
        max_results: int,
    ) -> List[Any]:
        collected: List[Any] = []
        seen_keys: set[str] = set()
        fulltext_keywords: List[str] = []
        contained_title = str(getattr(footnote, "contained_title", "") or "")
        if contained_title:
            fulltext_keywords.append(contained_title)
        for keyword in iter_ndl_search_keywords(footnote):
            if keyword not in fulltext_keywords:
                fulltext_keywords.append(keyword)
        for keyword in fulltext_keywords:
            try:
                records = search_ndl_digital_fulltext(keyword, max_results=max_results)
            except Exception:
                records = []
            if not records:
                try:
                    records = search_ndlsearch_fulltext(
                        keyword,
                        max_results=max_results,
                        use_browser=os.environ.get("HISTORICAL_CITATION_ENABLE_NDLSEARCH_BROWSER_HTML") == "1",
                    )
                except Exception:
                    continue
            for record in records:
                key = str(record.get("ndl_id") or record.get("url") or record.get("title") or "")
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    collected.append(record)
            if collected:
                break
        return collected[:max_results]

    def select_preferred_match(self, matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
        return select_preferred_source_match(matches)

    def download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        return download_public_pdf(match, output_dir=output_dir)

    def build_restricted_download_requests(
        self,
        *,
        footnote: ParsedFootnote,
        top_match: Optional[NDLSearchMatch],
        fallback_title: str,
        output_dir: Path,
        start_page: int,
        end_page: int,
    ) -> List[Dict[str, Any]]:
        return build_restricted_download_requests(
            keywords=iter_ndl_search_keywords(footnote),
            top_match=top_match,
            fallback_title=fallback_title,
            output_dir=output_dir,
            start_page=start_page,
            end_page=end_page,
        )


@dataclass
class JapanSearchPlatformAdapter:
    """Search Japan Search metadata through its public SPARQL endpoint."""

    name: str = "japan_search"
    request_get: Callable[..., Any] = requests.get

    def search(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        records: List[NDLSearchMatch] = []
        seen_urls: set[str] = set()
        for keyword in self._iter_keywords(footnote):
            query = self._build_query(keyword, limit=max_results)
            try:
                response = self.request_get(
                    JAPAN_SEARCH_SPARQL_URL,
                    params={"query": query, "format": "json"},
                    headers={
                        "Accept": "application/sparql-results+json",
                        "User-Agent": "Mozilla/5.0",
                    },
                    timeout=30,
                )
                if getattr(response, "status_code", 500) != 200:
                    continue
                payload = response.json()
            except Exception:
                continue
            for binding in payload.get("results", {}).get("bindings", []):
                match = self._binding_to_match(binding, footnote)
                key = match.url or match.platform_item_id or match.title
                if key and key not in seen_urls:
                    seen_urls.add(key)
                    records.append(match)
            if records:
                break
        records.sort(key=lambda item: item.score, reverse=True)
        return records[:max_results]

    def _iter_keywords(self, footnote: ParsedFootnote) -> List[str]:
        keywords: List[str] = []
        for value in [footnote.title, *title_query_terms(footnote.title), footnote.author]:
            value = (value or "").strip()
            if value and value not in keywords:
                keywords.append(value)
        return keywords[:5]

    def _build_query(self, keyword: str, *, limit: int) -> str:
        escaped_keyword = keyword.replace("\\", "\\\\").replace('"', '\\"')
        return f"""
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?item ?label ?creator ?publisher ?date ?url WHERE {{
  ?item schema:name|rdfs:label ?label .
  FILTER(CONTAINS(STR(?label), "{escaped_keyword}"))
  OPTIONAL {{ ?item schema:creator ?creator . }}
  OPTIONAL {{ ?item schema:publisher ?publisher . }}
  OPTIONAL {{ ?item schema:datePublished|schema:dateCreated ?date . }}
  OPTIONAL {{ ?item schema:url|schema:relatedLink ?url . }}
}}
LIMIT {max(1, min(int(limit), 20))}
"""

    def _binding_to_match(self, binding: Dict[str, Any], footnote: ParsedFootnote) -> NDLSearchMatch:
        def value(name: str) -> str:
            return str(binding.get(name, {}).get("value", "") or "")

        item_url = value("item")
        landing_url = value("url") or item_url
        match = NDLSearchMatch(
            title=value("label"),
            url=landing_url,
            platform=self.name,
            platform_item_id=item_url or landing_url or None,
            author=value("creator") or None,
            date=value("date") or None,
            publisher=value("publisher") or None,
            metadata={"item": item_url},
        )
        match.score = self._score(footnote, match)
        return match

    def _score(self, footnote: ParsedFootnote, match: NDLSearchMatch) -> float:
        title_score = score_ndl_record(
            footnote,
            title=match.title,
            author=match.author,
            year=match.date,
            publisher=match.publisher,
        )
        footnote_title = normalize_match_text(footnote.title)
        match_title = normalize_match_text(match.title)
        if footnote_title and match_title and footnote_title in match_title:
            title_score += 0.15
        return min(title_score, 1.0)

    def select_preferred_match(self, matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
        return matches[0] if matches else None

    def download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        del match, output_dir
        return None

    def build_restricted_download_requests(
        self,
        *,
        footnote: ParsedFootnote,
        top_match: Optional[NDLSearchMatch],
        fallback_title: str,
        output_dir: Path,
        start_page: int,
        end_page: int,
    ) -> List[Dict[str, Any]]:
        del footnote, top_match, fallback_title, output_dir, start_page, end_page
        return []


@dataclass
class InternetArchivePlatformAdapter:
    """Search and acquire public files from Internet Archive texts."""

    name: str = "internet_archive"
    request_get: Callable[..., Any] = requests.get

    def search(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        records: List[NDLSearchMatch] = []
        seen_ids: set[str] = set()
        for query in self._iter_queries(footnote):
            try:
                response = self.request_get(
                    INTERNET_ARCHIVE_ADVANCED_SEARCH_URL,
                    params={
                        "q": query,
                        "fl[]": ["identifier", "title", "creator", "date", "publisher"],
                        "rows": max(1, min(int(max_results), 20)),
                        "page": 1,
                        "output": "json",
                    },
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=30,
                )
                if getattr(response, "status_code", 500) != 200:
                    continue
                payload = response.json()
            except Exception:
                continue
            for item in payload.get("response", {}).get("docs", []):
                identifier = str(item.get("identifier") or "")
                if not identifier or identifier in seen_ids:
                    continue
                seen_ids.add(identifier)
                match = self._item_to_match(item, footnote)
                if match.score >= 0.35:
                    records.append(match)
            if records:
                break
        records.sort(key=lambda item: item.score, reverse=True)
        return records[:max_results]

    def _iter_queries(self, footnote: ParsedFootnote) -> List[str]:
        queries: List[str] = []
        for value in [footnote.title, *title_query_terms(footnote.title), footnote.author]:
            value = (value or "").strip()
            if not value:
                continue
            escaped = value.replace('"', '\\"')
            for query in [f'title:"{escaped}" AND mediatype:texts', f'"{escaped}" AND mediatype:texts']:
                if query not in queries:
                    queries.append(query)
        return queries[:8]

    def _item_to_match(self, item: Dict[str, Any], footnote: ParsedFootnote) -> NDLSearchMatch:
        identifier = str(item.get("identifier") or "")
        title = self._first_value(item.get("title"))
        creator = self._first_value(item.get("creator"))
        publisher = self._first_value(item.get("publisher"))
        date = self._first_value(item.get("date"))
        match = NDLSearchMatch(
            title=title,
            url=f"https://archive.org/details/{identifier}",
            platform=self.name,
            platform_item_id=identifier,
            author=creator or None,
            date=date or None,
            publisher=publisher or None,
            metadata={"identifier": identifier},
        )
        match.score = score_ndl_record(
            footnote,
            title=match.title,
            author=match.author,
            year=match.date,
            publisher=match.publisher,
        )
        return match

    def _first_value(self, value: Any) -> str:
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value or "")

    def select_preferred_match(self, matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
        return matches[0] if matches else None

    def download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        identifier = match.platform_item_id or match.metadata.get("identifier")
        if not identifier:
            return None
        try:
            response = self.request_get(
                INTERNET_ARCHIVE_METADATA_URL.format(identifier=identifier),
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            if getattr(response, "status_code", 500) != 200:
                return None
            payload = response.json()
        except Exception:
            return None
        files = payload.get("files") or []
        pdf_file = self._select_pdf_file(files)
        if not pdf_file:
            return None
        file_name = pdf_file.get("name")
        if not file_name:
            return None
        target = output_dir / f"{identifier}.pdf"
        download_url = f"https://archive.org/download/{identifier}/{file_name}"
        try:
            file_response = self.request_get(download_url, stream=True, timeout=120)
            if getattr(file_response, "status_code", 500) != 200:
                return None
            with open(target, "wb") as handle:
                for chunk in file_response.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        handle.write(chunk)
        except Exception:
            return None
        return str(target.resolve())

    def _select_pdf_file(self, files: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        pdfs = [
            file
            for file in files
            if str(file.get("name", "")).lower().endswith(".pdf")
        ]
        if not pdfs:
            return None
        text_pdfs = [file for file in pdfs if "_text" in str(file.get("name", "")).lower()]
        return (text_pdfs or pdfs)[0]

    def build_restricted_download_requests(
        self,
        *,
        footnote: ParsedFootnote,
        top_match: Optional[NDLSearchMatch],
        fallback_title: str,
        output_dir: Path,
        start_page: int,
        end_page: int,
    ) -> List[Dict[str, Any]]:
        del footnote, top_match, fallback_title, output_dir, start_page, end_page
        return []


def _html_title_candidates(html_text: str, *, base_url: str, href_pattern: str) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(rf"<a\b[^>]*href=[\"']({href_pattern})[\"'][^>]*>(.*?)</a>", re.I | re.S)
    for href, raw_label in pattern.findall(html_text or ""):
        url = urljoin(base_url, html.unescape(href))
        if url in seen:
            continue
        label = re.sub(r"<[^>]+>", " ", raw_label)
        label = html.unescape(re.sub(r"\s+", " ", label)).strip()
        if not label:
            continue
        seen.add(url)
        candidates.append({"title": label, "url": url})
    return candidates


@dataclass
class JStagePlatformAdapter:
    """Search J-STAGE public article pages through the official site search."""

    name: str = "jstage"
    request_get: Callable[..., Any] = requests.get

    def search(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        records: List[NDLSearchMatch] = []
        for keyword in self._iter_keywords(footnote):
            try:
                response = self.request_get(
                    JSTAGE_GLOBAL_SEARCH_URL,
                    params={"globalSearchKey": keyword},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=30,
                )
                if getattr(response, "status_code", 500) != 200:
                    continue
            except Exception:
                continue
            for item in _html_title_candidates(
                getattr(response, "text", "") or "",
                base_url="https://www.jstage.jst.go.jp",
                href_pattern=r"[^\"']*/article/[^\"']+",
            ):
                match = NDLSearchMatch(
                    title=item["title"],
                    url=item["url"],
                    platform=self.name,
                    platform_item_id=item["url"],
                    metadata={"query": keyword, "route": "jstage_global_search"},
                )
                match.score = score_ndl_record(
                    footnote,
                    title=match.title,
                    author=match.author,
                    year=match.date,
                    publisher=match.publisher,
                )
                if match.score >= 0.20:
                    records.append(match)
            if records:
                break
        records.sort(key=lambda item: item.score, reverse=True)
        return records[:max_results]

    def _iter_keywords(self, footnote: ParsedFootnote) -> List[str]:
        keywords = [footnote.title, *title_query_terms(footnote.title), footnote.author]
        return [item for item in dict.fromkeys(str(value or "").strip() for value in keywords) if item][:5]

    def select_preferred_match(self, matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
        return matches[0] if matches else None

    def download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        del match, output_dir
        return None

    def build_restricted_download_requests(self, **kwargs: Any) -> List[Dict[str, Any]]:
        del kwargs
        return []


@dataclass
class CiNiiResearchPlatformAdapter:
    """Search CiNii Research public records with an HTML fallback route."""

    name: str = "cinii_research"
    request_get: Callable[..., Any] = requests.get

    def search(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        records: List[NDLSearchMatch] = []
        for keyword in self._iter_keywords(footnote):
            try:
                response = self.request_get(
                    CINII_RESEARCH_SEARCH_URL,
                    params={"q": keyword, "lang": "ja"},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=30,
                )
                if getattr(response, "status_code", 500) != 200:
                    continue
            except Exception:
                continue
            for item in _html_title_candidates(
                getattr(response, "text", "") or "",
                base_url="https://cir.nii.ac.jp",
                href_pattern=r"[^\"']*/crid/[^\"']+",
            ):
                match = NDLSearchMatch(
                    title=item["title"],
                    url=item["url"],
                    platform=self.name,
                    platform_item_id=item["url"],
                    metadata={"query": keyword, "route": "cinii_research_html"},
                )
                match.score = score_ndl_record(
                    footnote,
                    title=match.title,
                    author=match.author,
                    year=match.date,
                    publisher=match.publisher,
                )
                if match.score >= 0.20:
                    records.append(match)
            if records:
                break
        records.sort(key=lambda item: item.score, reverse=True)
        return records[:max_results]

    def _iter_keywords(self, footnote: ParsedFootnote) -> List[str]:
        keywords = [footnote.title, *title_query_terms(footnote.title), footnote.author]
        return [item for item in dict.fromkeys(str(value or "").strip() for value in keywords) if item][:5]

    def select_preferred_match(self, matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
        return matches[0] if matches else None

    def download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        del match, output_dir
        return None

    def build_restricted_download_requests(self, **kwargs: Any) -> List[Dict[str, Any]]:
        del kwargs
        return []


@dataclass
class JACARPlatformAdapter:
    """Resolve JACAR reference codes and search public JACAR metadata pages."""

    name: str = "jacar"
    request_get: Callable[..., Any] = requests.get

    def search(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        records: List[NDLSearchMatch] = []
        for ref_code in re.findall(r"\b[A-Z]\d{10,12}\b", footnote.text or ""):
            records.append(
                NDLSearchMatch(
                    title=footnote.title or ref_code,
                    url=f"https://www.jacar.archives.go.jp/aj/meta/result?IS_KEY_S1={quote_plus(ref_code)}",
                    platform=self.name,
                    platform_item_id=ref_code,
                    score=1.0,
                    metadata={"ref_code": ref_code, "route": "jacar_ref_code"},
                )
            )
        if records:
            return records[:max_results]
        for keyword in [footnote.title, footnote.ndl_keyword]:
            keyword = str(keyword or "").strip()
            if not keyword:
                continue
            try:
                response = self.request_get(
                    JACAR_SEARCH_URL,
                    params={"IS_KEY_S1": keyword},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=30,
                )
                if getattr(response, "status_code", 500) != 200:
                    continue
            except Exception:
                continue
            refs = re.findall(r"\b[A-Z]\d{10,12}\b", getattr(response, "text", "") or "")
            for ref_code in dict.fromkeys(refs):
                records.append(
                    NDLSearchMatch(
                        title=footnote.title or ref_code,
                        url=f"https://www.jacar.archives.go.jp/aj/meta/result?IS_KEY_S1={quote_plus(ref_code)}",
                        platform=self.name,
                        platform_item_id=ref_code,
                        score=0.6,
                        metadata={"query": keyword, "ref_code": ref_code, "route": "jacar_html_search"},
                    )
                )
            if records:
                break
        return records[:max_results]

    def select_preferred_match(self, matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
        return matches[0] if matches else None

    def download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        del match, output_dir
        return None

    def build_restricted_download_requests(self, **kwargs: Any) -> List[Dict[str, Any]]:
        del kwargs
        return []


@dataclass
class DietProceedingsPlatformAdapter:
    """Search the National Diet Proceedings API for meeting/speech records."""

    name: str = "diet_proceedings"
    request_get: Callable[..., Any] = requests.get

    def search(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        keyword = footnote.title or footnote.ndl_keyword or footnote.text[:80]
        if not keyword:
            return []
        try:
            response = self.request_get(
                DIET_PROCEEDINGS_API_URL,
                params={
                    "any": keyword,
                    "maximumRecords": max(1, min(int(max_results), 20)),
                    "recordPacking": "json",
                },
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            if getattr(response, "status_code", 500) != 200:
                return []
            payload = response.json()
        except Exception:
            return []
        records: List[NDLSearchMatch] = []
        for item in payload.get("speechRecord", []) or payload.get("meetingRecord", []):
            title = item.get("nameOfHouse") or item.get("nameOfMeeting") or keyword
            url = item.get("speechURL") or item.get("meetingURL") or ""
            speech_id = item.get("speechID") or item.get("issueID") or url
            records.append(
                NDLSearchMatch(
                    title=str(title),
                    url=str(url),
                    platform=self.name,
                    platform_item_id=str(speech_id),
                    date=item.get("date"),
                    score=0.55,
                    metadata={"route": "kokkai_api", "raw_keys": sorted(item.keys())[:12]},
                )
            )
        return records[:max_results]

    def select_preferred_match(self, matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
        return matches[0] if matches else None

    def download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        del match, output_dir
        return None

    def build_restricted_download_requests(self, **kwargs: Any) -> List[Dict[str, Any]]:
        del kwargs
        return []


@dataclass
class EGovLawPlatformAdapter:
    """Route law citations to e-Gov law search pages for later exact adapters."""

    name: str = "egov_law"

    def search(self, footnote: ParsedFootnote, *, max_results: int = 5) -> List[NDLSearchMatch]:
        title = footnote.title or footnote.ndl_keyword
        if not title or not any(marker in footnote.text for marker in ("法", "令", "勅", "条例")):
            return []
        return [
            NDLSearchMatch(
                title=title,
                url=f"{EGOV_LAW_SEARCH_URL}?keyword={quote_plus(title)}",
                platform=self.name,
                platform_item_id=title,
                score=0.4,
                metadata={"route": "egov_law_search", "note": "metadata_only_search_url"},
            )
        ][:max_results]

    def select_preferred_match(self, matches: Sequence[NDLSearchMatch]) -> Optional[NDLSearchMatch]:
        return matches[0] if matches else None

    def download_public_pdf(self, match: NDLSearchMatch, *, output_dir: Path) -> Optional[str]:
        del match, output_dir
        return None

    def build_restricted_download_requests(self, **kwargs: Any) -> List[Dict[str, Any]]:
        del kwargs
        return []


@dataclass
class SourcePlatformRegistry:
    platforms: Sequence[SourcePlatformAdapter]

    def search(
        self,
        footnote: ParsedFootnote,
        *,
        max_results: int = 5,
        platform_names: Optional[Iterable[str]] = None,
    ) -> List[NDLSearchMatch]:
        allowed = set(platform_names or [])
        matches: List[NDLSearchMatch] = []
        seen_keys: set[str] = set()
        for platform in self.platforms:
            if allowed and platform.name not in allowed:
                continue
            for match in platform.search(footnote, max_results=max_results):
                key = f"{match.platform}:{match.platform_item_id or match.ndl_id or match.url or match.title}"
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    matches.append(match)
        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[:max_results]

    def get(self, name: str) -> Optional[SourcePlatformAdapter]:
        for platform in self.platforms:
            if platform.name == name:
                return platform
        return None


def default_source_platform_registry(
    *,
    ndl_download_module_getter: Callable[[], Any],
    prefer_external_ndl_module: bool = False,
    allow_external_ndl_fallback: bool = True,
) -> SourcePlatformRegistry:
    return SourcePlatformRegistry(
        platforms=[
            NDLSourcePlatformAdapter(
                download_module_getter=ndl_download_module_getter,
                prefer_external_module=prefer_external_ndl_module,
                allow_external_fallback=allow_external_ndl_fallback,
            ),
            JapanSearchPlatformAdapter(),
            InternetArchivePlatformAdapter(),
            JStagePlatformAdapter(),
            CiNiiResearchPlatformAdapter(),
            JACARPlatformAdapter(),
            DietProceedingsPlatformAdapter(),
            EGovLawPlatformAdapter(),
        ]
    )
