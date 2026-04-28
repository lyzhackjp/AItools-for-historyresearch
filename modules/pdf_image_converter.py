"""PDF page-to-image conversion utilities for OCR workflows."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF


class PDFImageConverter:
    """Convert PDF pages into image files while preserving page metadata."""

    def __init__(self, dpi: int = 300):
        self.dpi = dpi

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a lightweight capability snapshot for workflow discovery."""
        return {
            "module": "pdf_image_converter",
            "backend": "script",
            "provider": "pymupdf",
            "model": None,
            "capabilities": [
                "pdf_page_to_image",
                "pdf_range_to_images",
                "page_artifact_mapping",
                "dpi_control",
            ],
            "fallback_order": ["script:pymupdf", "pdf_processor.convert_to_images_package"],
        }

    def convert_page(
        self,
        pdf_path: str,
        page_num: int,
        output_dir: str,
        output_prefix: str = "page",
    ) -> Optional[str]:
        """Convert one 1-based PDF page into a PNG image path."""
        try:
            os.makedirs(output_dir, exist_ok=True)
            with fitz.open(pdf_path) as doc:
                page_index = page_num - 1
                if page_index < 0 or page_index >= len(doc):
                    return None
                page = doc[page_index]
                pix = page.get_pixmap(matrix=fitz.Matrix(self.dpi / 72, self.dpi / 72))
                output_path = os.path.join(output_dir, f"{output_prefix}_{page_num:04d}.png")
                pix.save(output_path)
                return output_path
        except Exception as exc:
            print(f"Failed to convert page {page_num}: {exc}")
            return None

    def convert_range(
        self,
        pdf_path: str,
        start_page: int,
        end_page: int,
        output_dir: str,
        output_prefix: str = "page",
        progress_callback=None,
    ) -> List[str]:
        """Convert a 1-based inclusive page range and return image paths."""
        package = self.convert_range_package(
            pdf_path=pdf_path,
            start_page=start_page,
            end_page=end_page,
            output_dir=output_dir,
            output_prefix=output_prefix,
            progress_callback=progress_callback,
        )
        return [artifact["path"] for artifact in package["artifacts"]]

    def convert_range_package(
        self,
        pdf_path: str,
        start_page: int,
        end_page: int,
        output_dir: str,
        output_prefix: str = "page",
        image_format: str = "PNG",
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Convert a page range and return workflow-ready artifact metadata."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

        os.makedirs(output_dir, exist_ok=True)
        artifacts: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        started_at = time.time()
        image_format = image_format.upper()
        image_ext = image_format.lower()

        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
            normalized_start = max(1, start_page)
            normalized_end = min(total_pages, end_page)
            requested_pages = max(0, normalized_end - normalized_start + 1)

            for offset, page_num in enumerate(range(normalized_start, normalized_end + 1), start=1):
                try:
                    page = doc[page_num - 1]
                    pix = page.get_pixmap(matrix=fitz.Matrix(self.dpi / 72, self.dpi / 72))
                    output_path = os.path.join(output_dir, f"{output_prefix}_{page_num:04d}.{image_ext}")
                    pix.save(output_path)
                    artifacts.append(
                        {
                            "type": "image",
                            "path": output_path,
                            "source_path": pdf_path,
                            "page_number": page_num,
                            "page_index": page_num - 1,
                            "dpi": self.dpi,
                            "format": image_format,
                            "width": pix.width,
                            "height": pix.height,
                            "source_page_size": {
                                "width": page.rect.width,
                                "height": page.rect.height,
                            },
                        }
                    )
                except Exception as exc:
                    errors.append({"page_number": page_num, "error": str(exc)})

                if progress_callback:
                    progress_callback(offset, requested_pages, page_num)

        quality_flags = []
        if normalized_end < normalized_start:
            quality_flags.append("empty_page_range")
        if not artifacts:
            quality_flags.append("no_images_generated")
        if errors:
            quality_flags.append("partial_conversion_failure")

        completion_ratio = len(artifacts) / requested_pages if requested_pages else 0.0
        confidence = 0.35 + (0.6 * completion_ratio)
        return {
            "type": "pdf_image_conversion",
            "source_path": pdf_path,
            "output_dir": output_dir,
            "page_range": {"start": normalized_start, "end": normalized_end},
            "page_count": requested_pages,
            "image_count": len(artifacts),
            "artifacts": artifacts,
            "backend": "script",
            "provider": "pymupdf",
            "model": None,
            "confidence": round(min(confidence, 0.98), 2),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "errors": errors,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "elapsed_seconds": round(time.time() - started_at, 3),
        }

    def convert_all(
        self,
        pdf_path: str,
        output_dir: str,
        output_prefix: str = "page",
        progress_callback=None,
    ) -> List[str]:
        """Convert all PDF pages and return image paths."""
        try:
            return [artifact["path"] for artifact in self.convert_all_package(
                pdf_path=pdf_path,
                output_dir=output_dir,
                output_prefix=output_prefix,
                progress_callback=progress_callback,
            )["artifacts"]]
        except Exception as exc:
            print(f"Failed to open PDF: {exc}")
            return []

    def convert_all_package(
        self,
        pdf_path: str,
        output_dir: str,
        output_prefix: str = "page",
        image_format: str = "PNG",
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Convert all pages and return a structured artifact envelope."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")
        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
        return self.convert_range_package(
            pdf_path=pdf_path,
            start_page=1,
            end_page=total_pages,
            output_dir=output_dir,
            output_prefix=output_prefix,
            image_format=image_format,
            progress_callback=progress_callback,
        )


def convert_pdf_to_images(
    pdf_path: str,
    output_dir: str,
    dpi: int = 300,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    progress_callback=None,
) -> List[str]:
    """Convenience wrapper that preserves the legacy list-of-paths API."""
    converter = PDFImageConverter(dpi=dpi)
    if start_page is None:
        start_page = 1
    if end_page is None:
        with fitz.open(pdf_path) as doc:
            end_page = len(doc)
    return converter.convert_range(
        pdf_path=pdf_path,
        start_page=start_page,
        end_page=end_page,
        output_dir=output_dir,
        output_prefix="page",
        progress_callback=progress_callback,
    )


def convert_pdf_to_images_package(
    pdf_path: str,
    output_dir: str,
    dpi: int = 300,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    progress_callback=None,
) -> Dict[str, Any]:
    """Convenience wrapper that returns a workflow-ready conversion package."""
    converter = PDFImageConverter(dpi=dpi)
    if start_page is None:
        start_page = 1
    if end_page is None:
        with fitz.open(pdf_path) as doc:
            end_page = len(doc)
    return converter.convert_range_package(
        pdf_path=pdf_path,
        start_page=start_page,
        end_page=end_page,
        output_dir=output_dir,
        output_prefix="page",
        progress_callback=progress_callback,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python pdf_image_converter.py <pdf_path> <output_dir> [dpi]")
        sys.exit(1)

    source_pdf = sys.argv[1]
    destination_dir = sys.argv[2]
    target_dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 300

    def progress(current, total, page):
        print(f"Progress: {current}/{total} (page: {page})")

    files = convert_pdf_to_images(source_pdf, destination_dir, target_dpi, progress_callback=progress)
    print(f"Conversion completed, generated {len(files)} images.")
