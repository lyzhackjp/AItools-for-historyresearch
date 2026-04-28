"""Compare NDLOCR-Lite and full NDLOCR outputs for Manshu page 211.

The script is deliberately conservative: it reports the full NDLOCR model as
"not_available" unless actual OCR text is present, so we do not accidentally
turn an environment failure into a fake accuracy number.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "ocr_output" / "ndlocr_full_vs_lite_page211"
ENTRIES_JSON = (
    ROOT
    / "ocr_output"
    / "manshu_full_pipeline_211_215_resplit"
    / "pages"
    / "page_0211_entries.json"
)
LITE_SUMMARY_JSON = ROOT / "ocr_output" / "japanese_ocr_model_eval_0211" / "ndlocr_lite_halves_page_0211_summary.json"
LITE_TEXT = ROOT / "ocr_output" / "japanese_ocr_model_eval_0211" / "ndlocr_lite_halves_page_0211.txt"
FULL_REPO = ROOT / "external" / "ndlocr_cli"
FULL_OUTPUT_DIR = ROOT / "ocr_output" / "ndlocr_full_page211"


FIELD_MARKERS = ["【出生】", "【本籍】", "【續柄】", "【學歴】", "【經歴】", "【家族】", "【住所】"]


def run_command(command: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as exc:
        return {
            "command": command,
            "returncode": None,
            "error": repr(exc),
        }


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def load_expected_entries() -> list[dict[str, Any]]:
    data = json.loads(ENTRIES_JSON.read_text(encoding="utf-8"))
    return data.get("entries", [])


def evaluate_text(label: str, text: str, expected_names: list[str]) -> dict[str, Any]:
    compact = normalize_text(text)
    found_names = [name for name in expected_names if name and name in compact]
    return {
        "engine": label,
        "status": "ok",
        "char_count": len(compact),
        "expected_name_count": len(expected_names),
        "found_name_count": len(found_names),
        "name_recall": round(len(found_names) / len(expected_names), 4) if expected_names else None,
        "found_names": found_names,
        "missing_names": [name for name in expected_names if name and name not in found_names],
        "field_marker_hits": {marker: compact.count(marker) for marker in FIELD_MARKERS},
    }


def collect_full_text() -> str | None:
    if not FULL_OUTPUT_DIR.exists():
        return None
    candidates = sorted(FULL_OUTPUT_DIR.rglob("*.txt"))
    if not candidates:
        return None
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in candidates)


def repo_status() -> dict[str, Any]:
    submodules = {}
    submodule_root = FULL_REPO / "submodules"
    if submodule_root.exists():
        for child in sorted(path for path in submodule_root.iterdir() if path.is_dir()):
            submodules[child.name] = len(list(child.iterdir()))
    return {
        "repo_dir": str(FULL_REPO),
        "repo_exists": FULL_REPO.exists(),
        "has_git_metadata": (FULL_REPO / ".git").exists(),
        "has_main_py": (FULL_REPO / "main.py").exists(),
        "has_cpu_test_config": (FULL_REPO / "config_cpu_page211.yml").exists(),
        "submodules": submodules,
        "model_files": {
            "layout_model": {
                "path": str(FULL_REPO / "submodules" / "ndl_layout" / "models" / "ndl_retrainmodel.pth"),
                "exists": (FULL_REPO / "submodules" / "ndl_layout" / "models" / "ndl_retrainmodel.pth").exists(),
                "size": (FULL_REPO / "submodules" / "ndl_layout" / "models" / "ndl_retrainmodel.pth").stat().st_size
                if (FULL_REPO / "submodules" / "ndl_layout" / "models" / "ndl_retrainmodel.pth").exists()
                else None,
            },
            "ocr_model": {
                "path": str(FULL_REPO / "submodules" / "text_recognition_lightning" / "models" / "resnet-orient2.ckpt"),
                "exists": (FULL_REPO / "submodules" / "text_recognition_lightning" / "models" / "resnet-orient2.ckpt").exists(),
                "size": (FULL_REPO / "submodules" / "text_recognition_lightning" / "models" / "resnet-orient2.ckpt").stat().st_size
                if (FULL_REPO / "submodules" / "text_recognition_lightning" / "models" / "resnet-orient2.ckpt").exists()
                else None,
            },
        },
    }


def write_markdown(report: dict[str, Any]) -> str:
    lite = report["models"]["ndlocr_lite"]
    full = report["models"]["ndlocr_full"]
    lines = [
        "# NDLOCR full vs lite 第211页测试记录",
        "",
        f"- 生成时间：{report['generated_at']}",
        "- 测试对象：`ocr_output/manshu_full_pipeline_211_215_resplit/split_halves/page_0211_right.png` 与 `page_0211_left.png`",
        "- 评价口径：以既有优化流程第211页分条结果中的 19 个姓名作为自动化代理指标，统计 OCR 文本中姓名召回率；同时统计常用字段标记命中。",
        "- 注意：这不是人工标注字符级准确率，而是在不新增人工标注前提下可复现的 OCR 实用召回指标。",
        "",
        "## 结果摘要",
        "",
        "| 模型 | 状态 | 姓名召回 | 召回人数 | 文本字符数 | 说明 |",
        "| --- | --- | ---: | ---: | ---: | --- |",
        f"| ndlocr-lite | {lite['status']} | {lite['name_recall']:.2%} | {lite['found_name_count']}/{lite['expected_name_count']} | {lite['char_count']} | 当前主流程基线 |",
        f"| ndlocr full | {full['status']} | N/A | N/A | N/A | 当前环境未跑出 OCR 文本，不能计算准确率 |",
        "",
        "## ndlocr-lite 指标",
        "",
        f"- 姓名召回：{lite['found_name_count']}/{lite['expected_name_count']} = {lite['name_recall']:.2%}",
        f"- 字段标记命中：{json.dumps(lite['field_marker_hits'], ensure_ascii=False)}",
        f"- 未召回姓名：{', '.join(lite['missing_names']) if lite['missing_names'] else '无'}",
        "",
        "## ndlocr full 当前阻塞点",
        "",
        "- GitHub `git clone --recursive` 被网络阻断；已改用 `codeload.github.com` zip 下载主仓库与子模块源码，因此本地目录可用但没有 `.git` 元数据。",
        "- 官方运行路径依赖 Docker + NVIDIA GPU；本机 Docker 已启动，但 `docker run --gpus all ... nvidia-smi` 返回 `WSL environment detected but no adapters were found`。",
        "- 尝试构建官方 Docker 镜像时，Docker Hub token 请求超时，无法拉取 `nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04`。",
        "- 因此本轮没有产生 ndlocr full 的实际 OCR 文本；在没有输出文本的情况下，不给出伪准确率。",
        "",
        "## 已落地准备",
        "",
        "- 非 lite 主仓库与子模块源码：`external/ndlocr_cli`",
        "- CPU 降级测试配置：`external/ndlocr_cli/config_cpu_page211.yml`",
        "- 已下载必要测试权重：`resnet-orient2.ckpt` 与 `ndl_retrainmodel.pth`",
        "- 若 Docker Hub 与 GPU/CPU 运行条件恢复，可继续运行 full 模型并重新执行本脚本生成对比。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    expected_entries = load_expected_entries()
    expected_names = [entry.get("name", "") for entry in expected_entries]

    if LITE_SUMMARY_JSON.exists():
        lite_summary = json.loads(LITE_SUMMARY_JSON.read_text(encoding="utf-8"))
        lite_text = LITE_TEXT.read_text(encoding="utf-8", errors="replace") if LITE_TEXT.exists() else ""
        lite_eval = evaluate_text("ndlocr_lite", lite_text, expected_names)
        # Preserve the earlier benchmark's count when it is more complete than
        # a plain text re-read through a locale-sensitive console.
        lite_eval["entry_count"] = lite_summary.get("entry_count")
        lite_eval["review_count"] = lite_summary.get("review_count")
    else:
        raise FileNotFoundError(LITE_SUMMARY_JSON)

    full_text = collect_full_text()
    if full_text:
        full_eval = evaluate_text("ndlocr_full", full_text, expected_names)
    else:
        full_eval = {
            "engine": "ndlocr_full",
            "status": "not_available",
            "reason": "No full NDLOCR OCR text was produced in ocr_output/ndlocr_full_page211.",
        }

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "page": 211,
        "input_images": [
            str(ROOT / "ocr_output" / "manshu_full_pipeline_211_215_resplit" / "split_halves" / "page_0211_right.png"),
            str(ROOT / "ocr_output" / "manshu_full_pipeline_211_215_resplit" / "split_halves" / "page_0211_left.png"),
        ],
        "evaluation_note": "Proxy OCR utility metric without new manual annotation: name recall against the existing optimized page-211 entry list plus field marker hits.",
        "models": {
            "ndlocr_lite": lite_eval,
            "ndlocr_full": full_eval,
        },
        "full_repo_status": repo_status(),
        "environment_checks": {
            "docker_info": run_command(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=30),
            "nvidia_runtime_probe": run_command(["docker", "run", "--rm", "--gpus", "all", "nvidia/cuda:12.1.1-base-ubuntu22.04", "nvidia-smi"], timeout=120),
            "full_image_exists": run_command(["docker", "images", "-q", "ndlocr-cli-cpu-test"], timeout=30),
        },
    }

    (OUTPUT_DIR / "comparison_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "comparison_report.md").write_text(write_markdown(report), encoding="utf-8")
    print(json.dumps(report["models"], ensure_ascii=False, indent=2))
    print(f"Wrote: {OUTPUT_DIR / 'comparison_summary.json'}")
    print(f"Wrote: {OUTPUT_DIR / 'comparison_report.md'}")


if __name__ == "__main__":
    main()
