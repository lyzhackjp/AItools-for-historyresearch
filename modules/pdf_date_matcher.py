# -*- coding: utf-8 -*-
from __future__ import annotations
"""
PDF日期匹配与训练数据生成模块
用于识别两个PDF中时间上相对应的页面，生成训练数据

遵循 WORKFLOW_DIAGRAM.md 和 COMPREHENSIVE_TECHNICAL_GUIDE.md 的流程
"""

import os
import re
import json
import base64
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
import logging

try:
    import fitz
except Exception:
    fitz = None

try:
    from PIL import Image
except Exception:
    Image = None

import io

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DateEntry:
    date_str: str
    year: int
    month: int
    day: int
    era: str
    era_year: int
    text_content: str
    source_page: int
    annotation_page: Optional[int] = None


@dataclass
class MatchedPair:
    source_image_path: str
    source_page: int
    annotation_text: str
    annotation_page: int
    date_info: Dict[str, Any]
    confidence: float = 1.0


@dataclass
class TrainingSample:
    image_path: str
    annotation_text: str
    date_info: Dict[str, Any]
    source_pdf_page: int
    annotation_pdf_page: int


class PDFDateMatcher:
    """
    PDF日期匹配器
    用于识别两个PDF中时间上相对应的页面
    """

    ERA_MAP = {
        '明治': (1868, 1912),
        '大正': (1912, 1926),
        '昭和': (1926, 1989),
        '平成': (1989, 2019),
        '令和': (2019, 2025)
    }

    KANJI_NUM = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '十一': 11, '十二': 12, '二十': 20, '三十': 30
    }

    DATE_PATTERNS = [
        r'明治(\d{1,2})年(\d{1,2})月(\d{1,2})日',
        r'明治(\d{1,2})年(\d{1,2})月',
        r'大正(\d{1,2})年(\d{1,2})月(\d{1,2})日',
        r'大正(\d{1,2})年(\d{1,2})月',
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',
        r'(\d{4})年(\d{1,2})月',
        r'明治([一二三四五六七八九十]+)年([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日',
        r'明治([一二三四五六七八九十]+)年([一二三四五六七八九十]+)月',
    ]

    def __init__(
        self,
        source_pdf_path: str,
        annotation_pdf_path: str,
        output_dir: str,
        api_key: str = None,
        auto_load_api_key: bool = False,
    ):
        self.source_pdf_path = source_pdf_path
        self.annotation_pdf_path = annotation_pdf_path
        self.output_dir = Path(output_dir)
        self.auto_load_api_key = auto_load_api_key

        self.images_dir = self.output_dir / 'source_images'
        self.annotations_dir = self.output_dir / 'annotations'
        self.matched_dir = self.output_dir / 'matched_pairs'
        self.training_dir = self.output_dir / 'training_data'

        for d in [self.images_dir, self.annotations_dir, self.matched_dir, self.training_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.api_key = api_key or (self._load_api_key() if auto_load_api_key else os.getenv('DASHSCOPE_API_KEY', ''))
        self.annotation_dates: Dict[str, DateEntry] = {}
        self.source_dates: Dict[str, DateEntry] = {}
        self.matched_pairs: List[MatchedPair] = []

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a workflow/agent-facing capability snapshot."""
        return {
            "module": "pdf_date_matcher",
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "layer": "training_prep",
            "input_formats": ["annotation_text_by_page", "source_date_results", "pdf"],
            "output_types": ["date_extraction", "date_match_pairs", "training_samples"],
            "capabilities": [
                "japanese_era_date_extraction",
                "annotation_date_indexing",
                "source_annotation_date_matching",
                "training_sample_generation",
                "package_output",
            ],
            "fallback_order": ["script:local_rules", "llm_api:qwen_vl", "local_llm", "skill", "mcp"],
            "optional_dependencies": {
                "fitz": fitz is not None,
                "PIL": Image is not None,
            },
            "privacy": {
                "offline_by_default": True,
                "auto_load_api_key": self.auto_load_api_key,
                "external_api_requires_use_llm": True,
                "config_file_key_loading_disabled_by_default": True,
            },
        }

    def parse_annotation_dates_package(self, text_by_page: Dict[int, str]) -> Dict[str, Any]:
        """Parse annotation text pages into a stable date extraction package."""
        dates = self.parse_annotation_dates(text_by_page)
        quality_flags = self._date_extraction_quality_flags(text_by_page, dates)
        return {
            "type": "date_extraction",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": self._estimate_confidence(
                item_count=len(dates),
                quality_flags=quality_flags,
                base=0.45,
            ),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "dates": {key: asdict(value) for key, value in dates.items()},
            "summary": {
                "page_count": len(text_by_page),
                "date_count": len(dates),
                "source": "annotation_text_by_page",
            },
            "capabilities": self.get_capabilities(),
        }

    def match_dates_package(
        self,
        annotation_dates: Dict[str, DateEntry],
        source_results: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Match source page dates to annotation pages and wrap the result."""
        matched_pairs = self.match_dates(annotation_dates, source_results)
        quality_flags = self._match_quality_flags(annotation_dates, source_results, matched_pairs)
        return {
            "type": "date_match_pairs",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": self._estimate_confidence(
                item_count=len(matched_pairs),
                quality_flags=quality_flags,
                base=0.40,
            ),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "matched_pairs": [asdict(pair) for pair in matched_pairs],
            "summary": {
                "annotation_date_count": len(annotation_dates),
                "source_result_count": len(source_results),
                "matched_pair_count": len(matched_pairs),
            },
            "capabilities": self.get_capabilities(),
        }

    def generate_training_data_package(
        self,
        matched_pairs: List[MatchedPair],
        *,
        save_artifacts: bool = False,
    ) -> Dict[str, Any]:
        """Generate training sample records without writing files by default."""
        training_samples = self.generate_training_data(matched_pairs)
        artifacts: Dict[str, Any] = {}
        if save_artifacts:
            self.save_training_data(training_samples)
            artifacts["training_dir"] = str(self.training_dir)
            artifacts["samples_json"] = str(self.training_dir / 'training_samples.json')
        quality_flags = self._training_quality_flags(matched_pairs, training_samples, save_artifacts)
        return {
            "type": "training_samples",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": self._estimate_confidence(
                item_count=len(training_samples),
                quality_flags=quality_flags,
                base=0.45,
            ),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "samples": [asdict(sample) for sample in training_samples],
            "artifacts": artifacts,
            "summary": {
                "matched_pair_count": len(matched_pairs),
                "training_sample_count": len(training_samples),
                "save_artifacts": save_artifacts,
            },
            "capabilities": self.get_capabilities(),
        }

    def _load_api_key(self) -> str:
        project_root = Path(__file__).parent.parent
        api_key_file = project_root / 'config' / 'api_key.txt'

        if api_key_file.exists():
            try:
                with open(api_key_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for line in content.strip().split('\n'):
                        if 'qwen' in line.lower():
                            parts = line.split('=')
                            if len(parts) >= 2:
                                return parts[1].strip()
            except:
                pass

        config_path = project_root / 'config' / 'api_config.json'
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'dashscope' in config:
                        return config['dashscope'].get('api_key', '')
            except:
                pass

        return os.getenv('DASHSCOPE_API_KEY', '')

    def kanji_to_number(self, kanji: str) -> int:
        if kanji.isdigit():
            return int(kanji)

        if kanji in self.KANJI_NUM:
            return self.KANJI_NUM[kanji]

        if '十' in kanji:
            parts = kanji.replace('十', '')
            if not parts:
                return 10
            elif kanji.startswith('十'):
                return 10 + self.KANJI_NUM.get(parts, 0)
            elif kanji.endswith('十'):
                return self.KANJI_NUM.get(parts, 0) * 10
            else:
                idx = kanji.index('十')
                tens = self.KANJI_NUM.get(kanji[:idx], 1) * 10
                ones = self.KANJI_NUM.get(kanji[idx+1:], 0)
                return tens + ones

        return 0

    def normalize_text(self, text: str) -> str:
        normalized = text.replace('\n', '')
        normalized = re.sub(r'\s+', '', normalized)
        return normalized

    def extract_dates_from_text(self, text: str) -> List[Dict[str, Any]]:
        normalized = self.normalize_text(text)
        dates = []

        era_year_patterns = [
            (r'明治([一二三四五六七八九十]+)年', '明治'),
            (r'明治(\d+)年', '明治'),
            (r'大正([一二三四五六七八九十]+)年', '大正'),
            (r'大正(\d+)年', '大正'),
        ]

        month_day_patterns = [
            r'([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日',
            r'(\d+)月(\d+)日',
        ]

        era_info = None
        for pattern, era in era_year_patterns:
            match = re.search(pattern, normalized)
            if match:
                era_year_str = match.group(1)
                era_year = self.kanji_to_number(era_year_str) if not era_year_str.isdigit() else int(era_year_str)
                era_info = {
                    'era': era,
                    'era_year': era_year,
                    'year': (1868 if era == '明治' else 1912) + era_year - 1
                }
                break

        if not era_info:
            return dates

        for pattern in month_day_patterns:
            for match in re.finditer(pattern, normalized):
                month_str, day_str = match.groups()
                month = self.kanji_to_number(month_str) if not month_str.isdigit() else int(month_str)
                day = self.kanji_to_number(day_str) if not day_str.isdigit() else int(day_str)

                dates.append({
                    'era': era_info['era'],
                    'era_year': era_info['era_year'],
                    'year': era_info['year'],
                    'month': month,
                    'day': day,
                    'date_str': f"{era_info['era']}{era_info['era_year']}年{month}月{day}日",
                    'full_text': text
                })

        return dates

    def parse_date(self, text: str) -> Optional[Dict[str, Any]]:
        dates = self.extract_dates_from_text(text)
        return dates[0] if dates else None

    def extract_text_from_annotation_pdf(self) -> Dict[int, str]:
        logger.info("从翻刻版PDF提取文本...")
        if fitz is None:
            raise RuntimeError("fitz is required to extract annotation PDF text")
        doc = fitz.open(self.annotation_pdf_path)
        text_by_page = {}

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_by_page[page_num + 1] = text

        doc.close()
        logger.info(f"提取了 {len(text_by_page)} 页文本")
        return text_by_page

    def parse_annotation_dates(self, text_by_page: Dict[int, str]) -> Dict[str, DateEntry]:
        logger.info("解析翻刻版日期信息...")
        dates = {}

        for page_num, text in text_by_page.items():
            all_dates = self.extract_dates_from_text(text)
            for date_info in all_dates:
                date_key = f"{date_info['year']}-{date_info['month']:02d}-{date_info['day']:02d}"

                if date_key not in dates:
                    dates[date_key] = DateEntry(
                        date_str=date_info['date_str'],
                        year=date_info['year'],
                        month=date_info['month'],
                        day=date_info['day'],
                        era=date_info['era'],
                        era_year=date_info['era_year'],
                        text_content=text,
                        source_page=page_num
                    )

        logger.info(f"解析到 {len(dates)} 个日期条目")
        return dates

    def extract_images_from_source_pdf(
        self,
        start_page: int = 1,
        end_page: int = None,
        dpi: int = 300
    ) -> List[str]:
        logger.info(f"从原始史料PDF提取图片 (DPI={dpi})...")
        if fitz is None:
            raise RuntimeError("fitz is required to extract source PDF images")
        doc = fitz.open(self.source_pdf_path)
        total_pages = len(doc)

        if end_page is None:
            end_page = total_pages

        image_paths = []

        for page_num in range(start_page - 1, min(end_page, total_pages)):
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            image_path = self.images_dir / f'page_{page_num + 1:04d}.png'
            pix.save(str(image_path))
            image_paths.append(str(image_path))

            if (page_num + 1) % 10 == 0:
                logger.info(f"已处理 {page_num + 1} 页")

        doc.close()
        logger.info(f"提取了 {len(image_paths)} 张图片")
        return image_paths

    def image_to_base64(self, image_path: str, max_size_mb: float = 8.0) -> str:
        if Image is None:
            raise RuntimeError("Pillow is required to encode images")
        img = Image.open(image_path)

        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        quality = 85
        while quality >= 20:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            size_mb = len(buffer.getvalue()) / (1024 * 1024)

            if size_mb <= max_size_mb:
                return base64.b64encode(buffer.getvalue()).decode('utf-8')

            quality -= 10

        max_dimension = 2000
        while max_dimension >= 800:
            img_resized = img.copy()
            img_resized.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img_resized.save(buffer, format='JPEG', quality=70, optimize=True)
            size_mb = len(buffer.getvalue()) / (1024 * 1024)

            if size_mb <= max_size_mb:
                return base64.b64encode(buffer.getvalue()).decode('utf-8')

            max_dimension -= 200

        buffer = io.BytesIO()
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        img.save(buffer, format='JPEG', quality=50, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def call_llm_for_date_recognition(self, image_path: str) -> Dict[str, Any]:
        if not self.api_key:
            logger.warning("未配置API密钥，返回模拟数据")
            return {'dates': [], 'text': '', 'error': 'No API key'}

        try:
            from openai import OpenAI

            image_base64 = self.image_to_base64(image_path)
            image_url = f"data:image/jpeg;base64,{image_base64}"

            prompt = """この画像は明治時代の日記（中島徳蔵日誌）のページです。
以下の情報を抽出してください：

1. 日付情報（年月日）
   - 明治何年何月何日か
   - 西暦での年月日

2. ページの主要なテキスト内容の概要

JSON形式で回答してください：
{
    "dates": [
        {
            "era": "明治",
            "era_year": 36,
            "year": 1903,
            "month": 1,
            "day": 1,
            "date_str": "明治三十六年一月一日"
        }
    ],
    "text_summary": "テキストの概要",
    "has_content": true
}
"""

            client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )

            completion = client.chat.completions.create(
                model="qwen-vl-ocr-latest",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}},
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]
            )

            response_text = completion.choices[0].message.content

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                return json.loads(json_match.group())

            return {'dates': [], 'text': response_text, 'error': None}

        except Exception as e:
            logger.error(f"LLM调用错误: {e}")
            return {'dates': [], 'text': '', 'error': str(e)}

    def recognize_source_dates_with_llm(
        self,
        image_paths: List[str],
        batch_size: int = 5
    ) -> Dict[int, Dict[str, Any]]:
        logger.info("使用LLM识别原始史料日期...")
        results = {}

        for i, image_path in enumerate(image_paths):
            page_num = i + 1
            logger.info(f"处理第 {page_num} 页...")

            result = self.call_llm_for_date_recognition(image_path)
            results[page_num] = result

            if result.get('dates'):
                logger.info(f"  发现日期: {result['dates']}")

            time.sleep(1)

        return results

    def match_dates(
        self,
        annotation_dates: Dict[str, DateEntry],
        source_results: Dict[int, Dict[str, Any]]
    ) -> List[MatchedPair]:
        logger.info("匹配日期对应关系...")
        matched = []

        for page_num, result in source_results.items():
            if not result.get('dates'):
                continue

            for date_info in result['dates']:
                date_key = f"{date_info['year']}-{date_info['month']:02d}-{date_info['day']:02d}"

                if date_key in annotation_dates:
                    annotation = annotation_dates[date_key]
                    image_path = str(self.images_dir / f'page_{page_num:04d}.png')

                    matched.append(MatchedPair(
                        source_image_path=image_path,
                        source_page=page_num,
                        annotation_text=annotation.text_content,
                        annotation_page=annotation.source_page,
                        date_info=date_info,
                        confidence=1.0
                    ))

                    logger.info(f"匹配成功: 第{page_num}页 -> {date_key}")

        logger.info(f"共匹配 {len(matched)} 对")
        return matched

    def generate_training_data(self, matched_pairs: List[MatchedPair]) -> List[TrainingSample]:
        logger.info("生成训练数据...")
        training_samples = []

        for pair in matched_pairs:
            sample = TrainingSample(
                image_path=pair.source_image_path,
                annotation_text=pair.annotation_text,
                date_info=pair.date_info,
                source_pdf_page=pair.source_page,
                annotation_pdf_page=pair.annotation_page
            )
            training_samples.append(sample)

        logger.info(f"生成 {len(training_samples)} 个训练样本")
        return training_samples

    def save_training_data(self, training_samples: List[TrainingSample]):
        logger.info("保存训练数据...")

        samples_data = [asdict(s) for s in training_samples]

        json_path = self.training_dir / 'training_samples.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(samples_data, f, ensure_ascii=False, indent=2)

        for i, sample in enumerate(training_samples):
            src_path = Path(sample.image_path)
            if src_path.exists():
                dst_path = self.training_dir / f'sample_{i+1:04d}.png'
                shutil.copy(src_path, dst_path)

                annotation_path = self.training_dir / f'sample_{i+1:04d}.txt'
                with open(annotation_path, 'w', encoding='utf-8') as f:
                    f.write(sample.annotation_text)

        logger.info(f"训练数据已保存到 {self.training_dir}")

    def run_full_pipeline(
        self,
        start_page: int = 1,
        end_page: int = 10,
        use_llm: bool = True
    ) -> Dict[str, Any]:
        logger.info("="*60)
        logger.info("开始PDF日期匹配流程")
        logger.info("="*60)

        text_by_page = self.extract_text_from_annotation_pdf()
        annotation_dates = self.parse_annotation_dates(text_by_page)

        image_paths = self.extract_images_from_source_pdf(start_page, end_page)

        if use_llm:
            source_results = self.recognize_source_dates_with_llm(image_paths)
        else:
            source_results = {}

        matched_pairs = self.match_dates(annotation_dates, source_results)

        training_samples = self.generate_training_data(matched_pairs)

        self.save_training_data(training_samples)

        report = {
            'annotation_pdf': self.annotation_pdf_path,
            'source_pdf': self.source_pdf_path,
            'total_annotation_pages': len(text_by_page),
            'total_annotation_dates': len(annotation_dates),
            'total_source_pages': len(image_paths),
            'total_matched_pairs': len(matched_pairs),
            'total_training_samples': len(training_samples),
            'output_dir': str(self.output_dir),
            'processing_time': datetime.now().isoformat()
        }

        report_path = self.output_dir / 'processing_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("="*60)
        logger.info("处理完成")
        logger.info(f"匹配对数: {len(matched_pairs)}")
        logger.info(f"训练样本数: {len(training_samples)}")
        logger.info("="*60)

        return report

    def _date_extraction_quality_flags(
        self,
        text_by_page: Dict[int, str],
        dates: Dict[str, DateEntry],
    ) -> List[str]:
        flags: List[str] = []
        if not text_by_page:
            flags.append("no_annotation_text")
        if text_by_page and not dates:
            flags.append("no_dates_extracted")
        empty_pages = sum(1 for text in text_by_page.values() if not str(text).strip())
        if empty_pages:
            flags.append("empty_annotation_pages")
        return flags

    def _match_quality_flags(
        self,
        annotation_dates: Dict[str, DateEntry],
        source_results: Dict[int, Dict[str, Any]],
        matched_pairs: List[MatchedPair],
    ) -> List[str]:
        flags: List[str] = []
        if not annotation_dates:
            flags.append("no_annotation_dates")
        if not source_results:
            flags.append("no_source_results")
        source_date_count = sum(len(result.get('dates') or []) for result in source_results.values())
        if source_results and source_date_count == 0:
            flags.append("no_source_dates")
        if annotation_dates and source_results and not matched_pairs:
            flags.append("no_matched_pairs")
        errors = [result.get("error") for result in source_results.values() if result.get("error")]
        if errors:
            flags.append("source_result_errors")
        return flags

    def _training_quality_flags(
        self,
        matched_pairs: List[MatchedPair],
        training_samples: List[TrainingSample],
        save_artifacts: bool,
    ) -> List[str]:
        flags: List[str] = []
        if not matched_pairs:
            flags.append("no_matched_pairs")
        if matched_pairs and not training_samples:
            flags.append("no_training_samples")
        if not save_artifacts:
            flags.append("artifacts_not_saved")
        if any(not sample.annotation_text for sample in training_samples):
            flags.append("sample_missing_annotation_text")
        return flags

    def _estimate_confidence(
        self,
        *,
        item_count: int,
        quality_flags: List[str],
        base: float,
    ) -> float:
        confidence = base
        if item_count:
            confidence += 0.35
        confidence -= min(0.35, len(set(quality_flags)) * 0.07)
        return round(max(0.1, min(confidence, 0.95)), 2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='PDF日期匹配与训练数据生成')
    parser.add_argument('--source', required=True, help='原始史料PDF路径')
    parser.add_argument('--annotation', required=True, help='翻刻版PDF路径')
    parser.add_argument('--output', default='./output', help='输出目录')
    parser.add_argument('--start-page', type=int, default=1, help='起始页码')
    parser.add_argument('--end-page', type=int, default=10, help='结束页码')
    parser.add_argument('--no-llm', action='store_true', help='不使用LLM识别')

    args = parser.parse_args()

    matcher = PDFDateMatcher(
        source_pdf_path=args.source,
        annotation_pdf_path=args.annotation,
        output_dir=args.output
    )

    report = matcher.run_full_pipeline(
        start_page=args.start_page,
        end_page=args.end_page,
        use_llm=not args.no_llm
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
