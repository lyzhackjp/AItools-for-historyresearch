"""Convert the Manshu workflow markdown case study into a printable PDF."""

from __future__ import annotations

import html
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import markdown


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SOURCE_MD = DOCS / "MANSHU_OCR_NER_RESEARCH_WORKFLOW_CASE_STUDY.md"
OUTPUT_PDF = DOCS / "MANSHU_OCR_NER_RESEARCH_WORKFLOW_CASE_STUDY.pdf"
OUTPUT_HTML = DOCS / "MANSHU_OCR_NER_RESEARCH_WORKFLOW_CASE_STUDY.print.html"


CSS = """
@page {
  size: A4;
  margin: 22mm 18mm 20mm;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  color: #252a2f;
  background: #f7f4ec;
  font-family: "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
  font-size: 11.2pt;
  line-height: 1.72;
}

.page {
  max-width: 860px;
  margin: 0 auto;
  padding: 34px 44px 42px;
  background: #fffdf8;
  border: 1px solid #ded6c7;
}

.cover {
  border-left: 8px solid #14776f;
  padding-left: 20px;
  margin-bottom: 26px;
}

.kicker {
  color: #c97434;
  font-size: 10pt;
  font-weight: 700;
  letter-spacing: .08em;
  margin-bottom: 8px;
}

h1 {
  margin: 0 0 8px;
  color: #20252b;
  font-size: 25pt;
  line-height: 1.22;
}

h2 {
  margin: 26px 0 10px;
  padding-top: 4px;
  color: #173f5f;
  font-size: 17pt;
  line-height: 1.35;
  border-top: 1px solid #e2d9ca;
  break-after: avoid;
}

h3 {
  margin: 18px 0 8px;
  color: #14776f;
  font-size: 13.2pt;
  break-after: avoid;
}

h4 {
  margin: 14px 0 6px;
  color: #4e5964;
  font-size: 11.5pt;
}

p {
  margin: 7px 0;
}

ul,
ol {
  margin: 7px 0 10px 1.25em;
  padding-left: 1em;
}

li {
  margin: 3px 0;
}

blockquote {
  margin: 12px 0;
  padding: 9px 13px;
  color: #4f5a63;
  background: #f2eee3;
  border-left: 4px solid #c97434;
}

code {
  color: #173f5f;
  background: #f0ede4;
  border-radius: 4px;
  padding: 1px 4px;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 9.5pt;
}

pre {
  margin: 10px 0;
  padding: 10px 12px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  background: #222831;
  color: #f8f1e7;
  border-radius: 8px;
  break-inside: avoid;
}

pre code {
  color: inherit;
  background: transparent;
  padding: 0;
}

table {
  width: 100%;
  margin: 12px 0 16px;
  border-collapse: collapse;
  break-inside: avoid;
  font-size: 9.8pt;
}

th,
td {
  padding: 7px 8px;
  border: 1px solid #d9d1c3;
  vertical-align: top;
}

th {
  color: #ffffff;
  background: #2c5282;
  font-weight: 700;
}

tr:nth-child(even) td {
  background: #f4f0e7;
}

a {
  color: #14776f;
  text-decoration: none;
}

hr {
  border: 0;
  height: 1px;
  background: #ded6c7;
  margin: 20px 0;
}

.meta {
  color: #5e666e;
  font-size: 9.5pt;
  margin-top: 12px;
}

.toc {
  margin: 18px 0 22px;
  padding: 12px 16px;
  background: #f2eee3;
  border-radius: 10px;
}

.toc strong {
  color: #173f5f;
}

@media print {
  body {
    background: #ffffff;
  }

  .page {
    max-width: none;
    padding: 0;
    border: 0;
  }
}
"""


def find_browser() -> Path:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    path_candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chromium"),
    ]
    candidates.extend(Path(item) for item in path_candidates if item)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No Edge/Chrome executable found for PDF export.")


def render_html(markdown_text: str) -> str:
    body = markdown.markdown(
        markdown_text,
        extensions=[
            "markdown.extensions.extra",
            "markdown.extensions.sane_lists",
            "markdown.extensions.toc",
        ],
        output_format="html5",
    )
    title = "《満洲紳士録》OCR-NER 流程复盘"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <main class="page">
    <section class="cover">
      <div class="kicker">AI 辅助历史研究流程复盘</div>
      <h1>{html.escape(title)}</h1>
      <div class="meta">由 Markdown 文档自动排版导出 PDF</div>
    </section>
    {body}
  </main>
</body>
</html>
"""


def export_pdf(browser: Path, html_path: Path, pdf_path: Path) -> None:
    if pdf_path.exists():
        pdf_path.unlink()
    user_data_dir = Path(tempfile.mkdtemp(prefix="manshu_pdf_chrome_"))
    command = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={user_data_dir}",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path}",
        html_path.resolve().as_uri(),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            command[1] = "--headless"
            result = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=120,
            )
        if result.returncode != 0:
            raise RuntimeError(
                "Browser PDF export failed.\n"
                f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
            )
        for _ in range(40):
            if pdf_path.exists() and pdf_path.stat().st_size > 1024:
                return
            time.sleep(0.25)
        raise RuntimeError(f"PDF was not created or is too small: {pdf_path}")
    finally:
        shutil.rmtree(user_data_dir, ignore_errors=True)


def main() -> None:
    if not SOURCE_MD.exists():
        raise FileNotFoundError(f"Source markdown not found: {SOURCE_MD}")
    html_text = render_html(SOURCE_MD.read_text(encoding="utf-8"))
    OUTPUT_HTML.write_text(html_text, encoding="utf-8")
    browser = find_browser()
    export_pdf(browser, OUTPUT_HTML, OUTPUT_PDF)
    print(f"Generated: {OUTPUT_PDF}")
    print(f"HTML: {OUTPUT_HTML}")
    print(f"Browser: {browser}")
    print(f"Size: {OUTPUT_PDF.stat().st_size}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
