"""Convert a Markdown report in this workspace into a printable PDF."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import markdown
except ModuleNotFoundError:  # Keep the converter usable in a bare Python env.
    markdown = None


ROOT = Path(__file__).resolve().parents[1]

CSS = """
@page {
  size: A4;
  margin: 18mm 15mm 18mm;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  color: #20252b;
  background: #f5f1e8;
  font-family: "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
  font-size: 10.8pt;
  line-height: 1.68;
}

.page {
  max-width: 900px;
  margin: 0 auto;
  padding: 30px 38px 38px;
  background: #fffdf8;
  border: 1px solid #ded6c7;
}

.cover {
  margin-bottom: 22px;
  padding-left: 18px;
  border-left: 7px solid #195c5a;
}

.kicker {
  color: #b66b2c;
  font-size: 9.6pt;
  font-weight: 700;
  letter-spacing: .08em;
}

h1 {
  margin: 6px 0 10px;
  color: #1d2730;
  font-size: 23pt;
  line-height: 1.25;
}

h2 {
  margin: 24px 0 10px;
  padding-top: 5px;
  color: #173f5f;
  font-size: 15.5pt;
  border-top: 1px solid #e2d9ca;
  break-after: avoid;
}

h3 {
  margin: 17px 0 8px;
  color: #195c5a;
  font-size: 12.5pt;
  break-after: avoid;
}

p {
  margin: 7px 0;
}

ul,
ol {
  margin: 7px 0 10px 1.1em;
  padding-left: 1em;
}

li {
  margin: 3px 0;
}

code {
  color: #173f5f;
  background: #f0ede4;
  border-radius: 4px;
  padding: 1px 4px;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 9.2pt;
}

pre {
  margin: 10px 0;
  padding: 10px 12px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  background: #232a31;
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
  font-size: 8.9pt;
}

th,
td {
  padding: 6px 7px;
  border: 1px solid #d9d1c3;
  vertical-align: top;
}

th {
  color: #fff;
  background: #2c5282;
}

tr:nth-child(even) td {
  background: #f4f0e7;
}

a {
  color: #195c5a;
  text-decoration: none;
}

.meta {
  color: #65707a;
  font-size: 9pt;
}

@media print {
  body {
    background: #fff;
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
    for executable in ("msedge", "chrome", "chromium"):
        found = shutil.which(executable)
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No Edge/Chrome executable found for PDF export.")


def render_html(markdown_text: str, title: str) -> str:
    if markdown is not None:
        body = markdown.markdown(
            markdown_text,
            extensions=[
                "markdown.extensions.extra",
                "markdown.extensions.sane_lists",
                "markdown.extensions.tables",
            ],
            output_format="html5",
        )
    else:
        body = render_markdown_fallback(markdown_text)
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
      <div class="kicker">AI 辅助历史研究 · 本地模型测试报告</div>
      <h1>{html.escape(title)}</h1>
      <div class="meta">由 Markdown 自动排版导出 PDF</div>
    </section>
    {body}
  </main>
</body>
</html>
"""


def render_inline(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def render_markdown_fallback(markdown_text: str) -> str:
    """Render the report subset we need without third-party dependencies."""
    lines = markdown_text.splitlines()
    output: list[str] = []
    in_ul = False
    in_code = False
    code_lines: list[str] = []
    in_table = False

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            output.append("</ul>")
            in_ul = False

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            output.append("</tbody></table>")
            in_table = False

    def is_separator(row: str) -> bool:
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        return bool(cells) and all(set(cell) <= {"-", ":"} and "-" in cell for cell in cells)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            close_ul()
            close_table()
            if in_code:
                output.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            close_ul()
            close_table()
            continue
        if stripped.startswith("#"):
            close_ul()
            close_table()
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            level = min(max(level, 1), 6)
            output.append(f"<h{level}>{render_inline(text)}</h{level}>")
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            close_ul()
            if is_separator(stripped):
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not in_table:
                output.append("<table><thead><tr>")
                output.extend(f"<th>{render_inline(cell)}</th>" for cell in cells)
                output.append("</tr></thead><tbody>")
                in_table = True
            else:
                output.append("<tr>")
                output.extend(f"<td>{render_inline(cell)}</td>" for cell in cells)
                output.append("</tr>")
            continue
        close_table()
        if stripped.startswith("- "):
            if not in_ul:
                output.append("<ul>")
                in_ul = True
            output.append(f"<li>{render_inline(stripped[2:])}</li>")
            continue
        close_ul()
        output.append(f"<p>{render_inline(stripped)}</p>")

    close_ul()
    close_table()
    if in_code:
        output.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    return "\n".join(output)


def export_pdf(browser: Path, html_path: Path, pdf_path: Path) -> None:
    if pdf_path.exists():
        pdf_path.unlink()
    user_data_dir = Path(tempfile.mkdtemp(prefix="md_report_pdf_chrome_"))
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Markdown to PDF with local Chromium/Edge.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output_pdf", type=Path)
    parser.add_argument("--title", default=None)
    parser.add_argument("--html", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output_pdf = args.output_pdf.resolve()
    output_html = (args.html.resolve() if args.html else output_pdf.with_suffix(".print.html"))
    if not source.exists():
        raise FileNotFoundError(f"Source markdown not found: {source}")
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    title = args.title or source.stem
    output_html.write_text(render_html(source.read_text(encoding="utf-8"), title), encoding="utf-8")
    browser = find_browser()
    export_pdf(browser, output_html, output_pdf)
    print(f"Generated: {output_pdf}")
    print(f"HTML: {output_html}")
    print(f"Browser: {browser}")
    print(f"Size: {output_pdf.stat().st_size}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
