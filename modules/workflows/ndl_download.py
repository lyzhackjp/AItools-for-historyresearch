from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

import requests

from ._legacy import PROJECT_ROOT, load_legacy_module


@dataclass
class NDLSearchRecord:
    title: str
    url: str
    ndl_id: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    publisher: Optional[str] = None
    pdf_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NDLDownloadRequest:
    keyword: str
    output_dir: str | Path = PROJECT_ROOT / "output" / "ndl_downloads"
    filename: Optional[str] = None
    ndl_id: Optional[str] = None
    title: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    max_results: int = 5
    max_attempts: int = 5
    use_api: bool = True
    headless: bool = True
    restricted: bool = False
    result_index: int = 0


@dataclass
class NDLDownloadOutcome:
    success: bool
    mode: str
    status: str
    keyword: str
    output_dir: str
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None
    selected_result: Optional[NDLSearchRecord] = None
    search_results: List[NDLSearchRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class NDLDownloadModule:
    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root) if project_root else PROJECT_ROOT

    def _public_searcher_class(self):
        return load_legacy_module("ndl-search/core/dl_searcher.py").NDLSearcher

    def _browser_client_class(self):
        return load_legacy_module("ndl-search/browser_client.py").NDLBrowserClient

    def _normalize_output_dir(self, output_dir: str | Path) -> Path:
        path = Path(output_dir)
        if not path.is_absolute():
            path = self.project_root / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _to_search_record(self, record: Any) -> NDLSearchRecord:
        return NDLSearchRecord(
            title=getattr(record, "title", "") or "",
            url=getattr(record, "url", "") or "",
            ndl_id=getattr(record, "ndl_id", None),
            author=getattr(record, "author", None),
            date=getattr(record, "date", None),
            publisher=getattr(record, "publisher", None),
            pdf_url=getattr(record, "pdf_url", None),
            metadata=dict(getattr(record, "metadata", {}) or {}),
        )

    def search(
        self,
        keyword: str,
        *,
        max_results: int = 10,
        use_api: bool = True,
        headless: bool = True,
        output_dir: str | Path | None = None,
    ) -> List[NDLSearchRecord]:
        searcher_cls = self._public_searcher_class()
        resolved_output = self._normalize_output_dir(output_dir or (self.project_root / "output" / "ndl_downloads"))
        searcher = searcher_cls(output_dir=str(resolved_output), headless=headless)
        try:
            records = searcher.search(keyword, max_results=max_results, use_api=use_api)
            return [self._to_search_record(record) for record in records]
        finally:
            searcher.close()

    def download(self, request: NDLDownloadRequest) -> NDLDownloadOutcome:
        if request.restricted or request.result_index != 0 or not request.use_api:
            return self._download_with_browser_client(request)
        return self._download_with_public_searcher(request)

    def download_first_match(self, keyword: str, **kwargs: Any) -> NDLDownloadOutcome:
        return self.download(NDLDownloadRequest(keyword=keyword, **kwargs))

    def _is_browser_recoverable_error(self, error_message: str) -> bool:
        normalized = (error_message or "").lower()
        recoverable_markers = (
            "download_link_not_found",
            "print_dialog_setup_failed",
            "print_button_not_found",
            "download_http_403",
            "download_fetch_failed",
            "lambda_http_401",
            "lambda_http_403",
            "browser_not_initialized",
            "login",
            "presigned_http_403",
        )
        return any(marker in normalized for marker in recoverable_markers)

    def _probe_ndl_toc(self, ndl_id: Optional[str]) -> Dict[str, Any]:
        if not ndl_id:
            return {"status": "skipped"}
        try:
            response = requests.get(
                f"https://dl.ndl.go.jp/api/meta/search/toc/facet/{ndl_id}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": f"{type(exc).__name__}:{exc}"}
        result: Dict[str, Any] = {
            "status": "ok" if response.status_code == 200 else "http_error",
            "status_code": response.status_code,
        }
        if response.status_code == 200:
            try:
                payload = response.json()
                bundles = payload.get("contentsBundles") or []
                contents = (bundles[0] if bundles else {}).get("contents") or []
                result["contents_count"] = len(contents)
                if not contents:
                    result["status"] = "empty_toc"
            except Exception as exc:  # noqa: BLE001
                result["status"] = "invalid_toc_json"
                result["error"] = f"{type(exc).__name__}:{exc}"
        return result

    def _validate_pdf_file(self, file_path: Optional[str]) -> Dict[str, Any]:
        if not file_path:
            return {"valid": False, "reason": "pdf_path_missing"}
        pdf_path = Path(file_path)
        if not pdf_path.exists():
            return {"valid": False, "reason": "pdf_file_missing", "path": str(pdf_path)}
        try:
            file_size = pdf_path.stat().st_size
        except OSError as exc:
            return {"valid": False, "reason": f"pdf_stat_failed:{exc}", "path": str(pdf_path)}
        validation: Dict[str, Any] = {
            "valid": False,
            "path": str(pdf_path),
            "file_size": file_size,
        }
        if file_size <= 0:
            validation["reason"] = "pdf_file_empty"
            return validation
        try:
            with pdf_path.open("rb") as handle:
                header = handle.read(8)
        except OSError as exc:
            validation["reason"] = f"pdf_read_failed:{exc}"
            return validation
        if not header.startswith(b"%PDF"):
            validation["reason"] = f"pdf_magic_mismatch:{header[:8]!r}"
            return validation
        try:
            import fitz

            document = fitz.open(str(pdf_path))
            try:
                page_count = len(document)
                if page_count >= 1:
                    first_page = document[0]
                    first_page_text = (first_page.get_text("text") or "").strip()
                    first_page_long_side = max(float(first_page.rect.width), float(first_page.rect.height))
                    validation["first_page_long_side"] = first_page_long_side
                    validation["first_page_text_length"] = len(first_page_text)
                    validation["first_page_image_count"] = len(first_page.get_images(full=True))
            finally:
                document.close()
            if page_count < 1:
                validation["reason"] = "pdf_has_no_pages"
                return validation
            validation["page_count"] = page_count
            if (
                validation.get("first_page_image_count", 0)
                and validation.get("first_page_text_length", 0) < 20
                and validation.get("first_page_long_side", 0) < 1000
            ):
                validation["reason"] = "pdf_low_resolution_for_ocr"
                return validation
        except Exception as exc:  # noqa: BLE001
            validation["reason"] = f"pdf_open_failed:{type(exc).__name__}:{exc}"
            return validation
        validation["valid"] = True
        validation["reason"] = "ok"
        return validation

    def _validated_outcome(self, outcome: NDLDownloadOutcome) -> NDLDownloadOutcome:
        if not outcome.success:
            return outcome
        validation = self._validate_pdf_file(outcome.file_path)
        outcome.metadata = {**(outcome.metadata or {}), "pdf_validation": validation}
        outcome.file_size = validation.get("file_size", outcome.file_size)
        if validation.get("valid"):
            return outcome
        invalid_path = outcome.file_path
        if invalid_path:
            try:
                Path(invalid_path).unlink(missing_ok=True)
            except OSError:
                pass
        outcome.success = False
        outcome.status = "invalid_pdf"
        outcome.error_message = validation.get("reason", "invalid_pdf")
        outcome.file_path = None
        return outcome

    def _download_with_public_searcher(self, request: NDLDownloadRequest) -> NDLDownloadOutcome:
        searcher_cls = self._public_searcher_class()
        resolved_output = self._normalize_output_dir(request.output_dir)
        searcher = searcher_cls(output_dir=str(resolved_output), headless=request.headless)
        try:
            result = searcher.search_and_download(
                keyword=request.keyword,
                filename=request.filename,
                max_attempts=request.max_attempts,
                use_api=request.use_api,
            )
            status = getattr(getattr(result, "status", None), "value", str(getattr(result, "status", "unknown")))
            return self._validated_outcome(NDLDownloadOutcome(
                success=status == "success",
                mode="public",
                status=status,
                keyword=request.keyword,
                output_dir=str(resolved_output),
                file_path=getattr(result, "file_path", None),
                file_size=getattr(result, "file_size", None),
                error_message=getattr(result, "error_message", None),
                metadata={
                    "attempts": getattr(result, "attempts", None),
                    "download_time": getattr(result, "download_time", None),
                    "checksum": getattr(result, "checksum", None),
                },
            ))
        finally:
            searcher.close()

    def _download_with_browser_client(self, request: NDLDownloadRequest) -> NDLDownloadOutcome:
        resolved_output = self._normalize_output_dir(request.output_dir)
        toc_probe = self._probe_ndl_toc(request.ndl_id)
        if toc_probe.get("status_code") == 404:
            return NDLDownloadOutcome(
                success=False,
                mode="restricted" if request.restricted else "browser",
                status="not_found",
                keyword=request.keyword,
                output_dir=str(resolved_output),
                error_message=f"ndl_toc_not_found:{request.ndl_id}",
                metadata={"toc_probe": toc_probe},
            )
        if toc_probe.get("status") == "empty_toc":
            return NDLDownloadOutcome(
                success=False,
                mode="restricted" if request.restricted else "browser",
                status="not_found",
                keyword=request.keyword,
                output_dir=str(resolved_output),
                error_message=f"ndl_toc_empty:{request.ndl_id}",
                metadata={"toc_probe": toc_probe},
            )

        browser_cls = self._browser_client_class()
        client = browser_cls(headless=request.headless, output_dir=str(resolved_output))
        try:
            if request.restricted:
                client.login()

            if request.ndl_id:
                selected = load_legacy_module("ndl-search/browser_client.py").NDLBook(
                    title=request.title or request.keyword or request.ndl_id,
                    ndl_id=request.ndl_id,
                    pid=request.ndl_id,
                    total_pages=0,
                    url=f"https://dl.ndl.go.jp/pid/{request.ndl_id}",
                    author=None,
                    publisher=None,
                    date=None,
                )
                search_results = [self._to_search_record(selected)]
            else:
                books = client.search_and_get_book(request.keyword)
                search_results = [self._to_search_record(book) for book in books]
                if not books:
                    return NDLDownloadOutcome(
                        success=False,
                        mode="browser",
                        status="not_found",
                        keyword=request.keyword,
                        output_dir=str(resolved_output),
                        error_message="No NDL search results were returned.",
                        search_results=search_results,
                    )

                if request.result_index < 0 or request.result_index >= len(books):
                    return NDLDownloadOutcome(
                        success=False,
                        mode="browser",
                        status="invalid_result_index",
                        keyword=request.keyword,
                        output_dir=str(resolved_output),
                        error_message=f"Result index {request.result_index} is out of range.",
                        search_results=search_results,
                    )

                selected = books[request.result_index]

            result = None
            attempt_errors: List[str] = []
            max_attempts = max(1, int(request.max_attempts or 1))
            for attempt in range(1, max_attempts + 1):
                if request.start_page is not None or request.end_page is not None:
                    selected_filename = request.filename
                    if not selected_filename:
                        safe_title = "".join(ch if ch not in '\\/*?:"<>|' else "_" for ch in selected.title)[:50]
                    start_page = max(1, int(request.start_page or 1))
                    end_page = max(start_page, int(request.end_page or start_page))
                    if not selected_filename:
                        selected_filename = f"{safe_title}_{selected.ndl_id}_p{start_page}-p{end_page}.pdf"
                    result = client._download_single_range(
                        selected,
                        start_page=start_page,
                        end_page=end_page,
                        filename=selected_filename,
                        dir_path=resolved_output,
                    )
                else:
                    result = client.download_book(
                        selected,
                        filename=request.filename,
                        download_dir=str(resolved_output),
                    )

                if getattr(result, "success", False):
                    break

                error_message = getattr(result, "error_message", None) or f"attempt_{attempt}_failed"
                attempt_errors.append(f"{attempt}:{error_message}")
                if attempt < max_attempts:
                    if self._is_browser_recoverable_error(error_message):
                        try:
                            target_url = f"https://dl.ndl.go.jp/pid/{selected.ndl_id}" if getattr(selected, "ndl_id", None) else None
                            if hasattr(client, "_refresh_and_relogin"):
                                client._refresh_and_relogin(target_url=target_url)
                            else:
                                client._ensure_logged_in()
                        except Exception:
                            pass
                    else:
                        try:
                            client._ensure_logged_in()
                        except Exception:
                            pass
                    time.sleep(min(5, attempt))

            return self._validated_outcome(NDLDownloadOutcome(
                success=bool(getattr(result, "success", False)),
                mode="restricted" if request.restricted else "browser",
                status="success" if getattr(result, "success", False) else "failed",
                keyword=request.keyword,
                output_dir=str(resolved_output),
                file_path=getattr(result, "output_path", None),
                error_message=getattr(result, "error_message", None) if getattr(result, "success", False) else " | ".join(attempt_errors) or getattr(result, "error_message", None),
                selected_result=self._to_search_record(selected),
                search_results=search_results,
                metadata={
                    "total_pages": getattr(result, "total_pages", None),
                    "is_encrypted": getattr(result, "is_encrypted", None),
                    "chunk_count": len(getattr(result, "chunks", []) or []),
                    "attempts": max_attempts if getattr(result, "success", False) else len(attempt_errors),
                    "requested_start_page": getattr(result, "requested_start_page", None),
                    "requested_end_page": getattr(result, "requested_end_page", None),
                    "actual_start_page": getattr(result, "actual_start_page", None),
                    "actual_end_page": getattr(result, "actual_end_page", None),
                    "range_adjusted": bool(getattr(result, "range_adjusted", False)),
                },
            ))
        finally:
            client.close()
