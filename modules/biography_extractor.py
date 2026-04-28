"""
人物传记批量提取管道
从PDF中识别竖排日文文献，提取人物信息并输出CSV
"""
import os
import sys
import json
import time
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re


@dataclass
class PersonEntity:
    """人物实体"""
    name: str = ""                           # 姓名
    reading: str = ""                         # 读音
    original_text: str = ""                  # 原始文本
    hometown: Optional[str] = None           # 本籍
    birth_date: Optional[str] = None         # 出生年月
    education: Optional[str] = None           # 学历
    work_experiences: List[Dict[str, str]] = field(default_factory=list)  # 工作经历
    page_number: Optional[int] = None        # 页码
    column_index: Optional[int] = None       # 列索引(0=left, 1=middle, 2=right)


class BiographicalNER:
    """传记NER处理器"""

    WAREKI_MAP = {
        '明治': 1868, '大正': 1912, '昭和': 1926, '平成': 1989, '令和': 2019
    }

    # 学历关键词
    EDUCATION_PATTERNS = [
        r'(?:東京大学|東京帝大|東北大|北大|名大|阪大|九大|京大|京都帝大)\s*[^\s,，,。]*',
        r'(?:卒業|學歴|学历)[：:]\s*([^\n]*)',
        r'(?:学士|修士|博士)[^\n]*',
    ]

    # 本籍关键词
    HOMETOWN_PATTERNS = [
        r'本籍[：:]\s*([^\n,，]+)',
        r'出身地[：:]\s*([^\n,，]+)',
        r'生地[：:]\s*([^\n,，]+)',
    ]

    # 工作经历模式
    WORK_PATTERNS = [
        # 单位 + 时间
        r'([^\n,，]{2,20}?(?:大学|学校|省|庁|公司|銀行|病院|鉄道|局|部|課|満鉄|満炭|満業|南満洲鉄道))[^\n]{0,50}?((?:昭和|平成|令和|明治|大正)\d+年(?:-\d+年)?)',
        # 时间 + 单位
        r'((?:昭和|平成|令和|明治|大正)\d+年[^\n]{0,30}?)([^\n,，]{2,20}?(?:大学|学校|省|庁|公司|銀行|病院|鉄道|局|部|課))',
    ]

    def __init__(self):
        self.persons: List[PersonEntity] = []

    def parse_wareki_date(self, date_str: str) -> Optional[Tuple[int, int, int]]:
        """解析和历日期"""
        for era_name, era_start in self.WAREKI_MAP.items():
            pattern = rf'({era_name})\s*(\d+)年(?:\s*(\d+)月)?(?:\s*(\d+)日)?'
            match = re.search(pattern, date_str)
            if match:
                year = int(match.group(2))
                month = int(match.group(3)) if match.group(3) else 1
                day = int(match.group(4)) if match.group(4) else 1
                return (era_start + year - 1, month, day)
        return None

    def parse_date_range(self, date_str: str) -> Tuple[Optional[Tuple[int, int, int]], Optional[Tuple[int, int, int]]]:
        """解析日期范围"""
        parts = re.split(r'[-–—]', date_str)
        if len(parts) >= 2:
            start = self.parse_wareki_date(parts[0].strip())
            end = self.parse_wareki_date(parts[1].strip())
            return (start, end)
        single = self.parse_wareki_date(date_str)
        return (single, single)

    def extract_name(self, text: str) -> Optional[Tuple[str, str]]:
        """提取姓名和读音"""
        patterns = [
            r'^([一-龥]{2,4})\s*[（(]([ァ-ヶー\s]+)[）)]',  # 姓名（读音）
            r'^([一-龥]{2,4})\s*$',  # 单独一行姓名
            r'([一-龥]{2,4})\s*(?:氏|君|殿)',  # 姓名+敬称
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1)
                reading = match.group(2) if match.lastindex >= 2 else ""
                return (name.strip(), reading.strip())
        return None

    def extract_hometown(self, text: str) -> Optional[str]:
        """提取本籍"""
        for pattern in self.HOMETOWN_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def extract_education(self, text: str) -> Optional[str]:
        """提取学历"""
        for pattern in self.EDUCATION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return None

    def extract_work_experiences(self, text: str) -> List[Dict[str, str]]:
        """提取工作经历"""
        experiences = []

        for pattern in self.WORK_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                groups = match.groups()
                exp = {}

                if len(groups) >= 2:
                    # 根据模式确定单位/时间顺序
                    if any(era in groups[0] for era in ['昭和', '平成', '令和', '明治', '大正']):
                        exp['date_range'] = groups[0].strip()
                        exp['unit'] = groups[1].strip()
                    else:
                        exp['unit'] = groups[0].strip()
                        exp['date_range'] = groups[1].strip()

                    # 解析日期
                    start_end = self.parse_date_range(exp['date_range'])
                    exp['start'] = start_end[0]
                    exp['end'] = start_end[1]
                    exp['description'] = match.group(0)

                    experiences.append(exp)

        return experiences

    def parse_text_block(self, text: str, page_num: int = None, column_idx: int = None) -> Optional[PersonEntity]:
        """解析文本块提取人物信息"""
        person = PersonEntity()
        person.page_number = page_num
        person.column_index = column_idx
        person.original_text = text

        # 提取姓名
        name_result = self.extract_name(text)
        if name_result:
            person.name, person.reading = name_result

        # 提取本籍
        person.hometown = self.extract_hometown(text)

        # 提取学历
        person.education = self.extract_education(text)

        # 提取工作经历
        person.work_experiences = self.extract_work_experiences(text)

        # 只有有效的才返回
        if person.name or person.work_experiences:
            return person
        return None

    def process_vertical_layout(self, text: str, page_num: int = None) -> List[PersonEntity]:
        """
        处理竖排版文本
        竖排文本特点：每列从上到下，从右到左
        """
        persons = []

        # 按列分割（通过换行或空行）
        lines = text.split('\n')

        current_block = []
        for line in lines:
            line = line.strip()
            if not line:
                # 空行分隔块
                if current_block:
                    block_text = '\n'.join(current_block)
                    person = self.parse_text_block(block_text, page_num, 0)
                    if person:
                        persons.append(person)
                    current_block = []
            else:
                current_block.append(line)

        # 处理最后一块
        if current_block:
            block_text = '\n'.join(current_block)
            person = self.parse_text_block(block_text, page_num, 0)
            if person:
                persons.append(person)

        return persons

    def sort_work_experiences(self) -> None:
        """按时间排序所有工作经历"""
        for person in self.persons:
            if person.work_experiences:
                person.work_experiences.sort(
                    key=lambda x: x.get('start') or (9999, 12, 31)
                )


class BiographyExtractor:
    """传记提取器"""

    def __init__(
        self,
        pdf_path: str,
        output_dir: str,
        dpi: int = 200,
        use_llm_fallback: bool = False,
        api_key: Optional[str] = None,
        batch_size: int = 10,
        auto_load_api_key: bool = False,
    ):
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.dpi = dpi
        self.use_llm_fallback = use_llm_fallback
        self.auto_load_api_key = auto_load_api_key
        self.api_key = api_key or (self._load_api_key() if auto_load_api_key else os.getenv("QWEN_API_KEY", ""))
        self.batch_size = batch_size

        self.images_dir = self.output_dir / 'images'
        self.ocr_dir = self.output_dir / 'ocr_results'

        self.ner = BiographicalNER()
        self.ocr_processor = None
        self.llm_ocr = None

        self.persons: List[PersonEntity] = []

    def get_capabilities(self) -> Dict[str, Any]:
        """Return an agent/workflow-facing capability snapshot."""
        return {
            "module": "biography_extractor",
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "layer": "specialized_analysis",
            "input_formats": ["ocr_text", "ocr_result", "pdf"],
            "output_types": ["biography_entities", "biography_batch"],
            "capabilities": [
                "vertical_japanese_biography_parsing",
                "person_name_extraction",
                "hometown_extraction",
                "education_extraction",
                "work_experience_extraction",
                "csv_json_export",
                "package_output",
            ],
            "fallback_order": [
                "script:local_rules",
                "local_engine:ndl_ocr",
                "llm_api:qwen_vl",
                "local_llm",
                "skill",
                "mcp",
            ],
            "privacy": {
                "offline_by_default": True,
                "auto_load_api_key": self.auto_load_api_key,
                "llm_fallback_enabled": self.use_llm_fallback,
                "secret_file_loading_disabled_by_default": True,
            },
        }

    def extract_entities_package(
        self,
        text: str,
        *,
        page_num: Optional[int] = None,
        source_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract biography entities from text and return a stable package."""
        persons = self.ner.process_vertical_layout(text or "", page_num)
        quality_flags = self._entity_quality_flags(text, persons)
        return self._build_entities_package(
            persons,
            source_summary={
                "source_id": source_id,
                "page_number": page_num,
                "text_length": len(text or ""),
            },
            quality_flags=quality_flags,
        )

    def process_ocr_results_package(
        self,
        ocr_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Extract biography entities from OCR result dictionaries."""
        all_persons: List[PersonEntity] = []
        for index, result in enumerate(ocr_results or [], 1):
            page_num = result.get("page_number") or result.get("page") or index
            text = result.get("text", "")
            if text:
                all_persons.extend(self.ner.process_vertical_layout(text, page_num))
        self.persons = all_persons
        self.ner.persons = all_persons
        quality_flags = self._batch_quality_flags(ocr_results, all_persons)
        return self._build_entities_package(
            all_persons,
            package_type="biography_batch",
            source_summary={
                "ocr_result_count": len(ocr_results or []),
                "successful_ocr_results": sum(1 for item in (ocr_results or []) if item.get("success", True)),
            },
            quality_flags=quality_flags,
        )

    def _load_api_key(self) -> str:
        """加载API密钥"""
        keys_file = Path(__file__).parent.parent / 'secrets' / 'api_keys.txt'
        try:
            with open(keys_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('qwen'):
                        return line.split('=')[1].strip()
        except:
            pass
        return ""

    def convert_pages(self, start_page: int = None, end_page: int = None,
                     progress_callback: Callable = None) -> List[str]:
        """PDF转图片"""
        from .pdf_image_converter import convert_pdf_to_images

        self.images_dir.mkdir(parents=True, exist_ok=True)

        def progress(c, t, p):
            if progress_callback:
                progress_callback(c, t, f"转换图片: 页{p}")

        return convert_pdf_to_images(
            self.pdf_path,
            str(self.images_dir),
            dpi=self.dpi,
            start_page=start_page,
            end_page=end_page,
            progress_callback=progress
        )

    def process_ocr_batch(
        self,
        image_paths: List[str],
        use_llm: bool = False,
        progress_callback: Callable = None
    ) -> List[Dict[str, Any]]:
        """批量OCR处理"""
        results = []
        total = len(image_paths)

        for i, img_path in enumerate(image_paths, 1):
            if progress_callback:
                progress_callback(i, total, f"OCR处理: {Path(img_path).name}")

            if use_llm:
                llm_ocr = self._get_llm_ocr()
                if llm_ocr is None:
                    results.append({
                        'success': False,
                        'text': '',
                        'image_path': img_path,
                        'error': 'llm_ocr_unavailable',
                    })
                    continue
                result = llm_ocr.process_image(img_path)
                results.append(result)
            else:
                # 使用NDL OCR
                ocr_processor = self._get_ocr_processor()
                success, text = self.ocr_processor.process_image(
                    img_path,
                    str(self.ocr_dir / Path(img_path).stem)
                )
                results.append({
                    'success': success,
                    'text': text if success else '',
                    'image_path': img_path
                })

            # 避免过快
            time.sleep(0.1)

        return results

    def run(
        self,
        start_page: int = None,
        end_page: int = None,
        max_pages: int = None,
        progress_callback: Callable = None
    ) -> bool:
        """
        运行完整管道

        Args:
            start_page: 起始页
            end_page: 结束页
            max_pages: 最大处理页数（用于测试）
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        try:
            total_steps = 5
            current = 0

            # Step 1: PDF转图片
            current += 1
            if progress_callback:
                progress_callback(current, total_steps, "Step 1/5: PDF转图片...")

            image_paths = self.convert_pages(start_page, end_page)

            if max_pages:
                image_paths = image_paths[:max_pages]

            if not image_paths:
                print("PDF转图片失败")
                return False

            if progress_callback:
                progress_callback(current, total_steps, f"转换完成: {len(image_paths)}张图片")

            # Step 2: OCR识别（先尝试NDL OCR）
            current += 1
            if progress_callback:
                progress_callback(current, total_steps, "Step 2/5: NDL OCR识别...")

            ocr_results = self.process_ocr_batch(image_paths, use_llm=False)

            # 检查NDL OCR成功率
            ndl_success_rate = sum(1 for r in ocr_results if r.get('success')) / len(ocr_results)

            if ndl_success_rate < 0.5 and self.use_llm_fallback and self.llm_ocr:
                if progress_callback:
                    progress_callback(current, total_steps, f"NDL OCR成功率低({ndl_success_rate:.0%})，切换到LLM OCR...")

                # 切换到LLM OCR
                ocr_results = self.process_ocr_batch(image_paths, use_llm=True)

            # Step 3: NER提取
            current += 1
            if progress_callback:
                progress_callback(current, total_steps, "Step 3/5: 提取人物实体...")

            all_persons = []
            for page_num, ocr_result in enumerate(ocr_results, 1):
                text = ocr_result.get('text', '')
                if not text:
                    continue

                # 解析竖排布局
                page_persons = self.ner.process_vertical_layout(text, page_num)
                all_persons.extend(page_persons)

            self.persons = all_persons
            self.ner.persons = all_persons

            if progress_callback:
                progress_callback(current, total_steps, f"提取到 {len(self.persons)} 个人物")

            # Step 4: 排序
            current += 1
            if progress_callback:
                progress_callback(current, total_steps, "Step 4/5: 排序工作经历...")

            self.ner.sort_work_experiences()

            # Step 5: 导出CSV
            current += 1
            if progress_callback:
                progress_callback(current, total_steps, "Step 5/5: 导出CSV...")

            csv_path = self.output_dir / 'biography_data.csv'
            self.export_csv(csv_path)

            json_path = self.output_dir / 'biography_data.json'
            self.export_json(json_path)

            if progress_callback:
                progress_callback(total_steps, total_steps, f"完成! 共{len(self.persons)}人")

            return True

        except Exception as e:
            print(f"管道执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def export_csv(self, csv_path: Path) -> None:
        """导出CSV"""
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # 表头
            writer.writerow([
                '姓名', '读音', '本籍', '出生年月', '学历',
                '工作经历1_单位', '工作经历1_时间', '工作经历1_开始', '工作经历1_结束',
                '工作经历2_单位', '工作经历2_时间', '工作经历2_开始', '工作经历2_结束',
                '工作经历3_单位', '工作经历3_时间', '工作经历3_开始', '工作经历3_结束',
                '页码', '列索引', '原始文本摘要'
            ])

            # 数据
            for person in self.persons:
                experiences = person.work_experiences[:3]

                row = [
                    person.name or '',
                    person.reading or '',
                    person.hometown or '',
                    person.birth_date or '',
                    person.education or '',
                ]

                for i in range(3):
                    if i < len(experiences):
                        exp = experiences[i]
                        row.extend([
                            exp.get('unit', ''),
                            exp.get('date_range', ''),
                            str(exp.get('start', '')),
                            str(exp.get('end', '')),
                        ])
                    else:
                        row.extend(['', '', '', ''])

                row.extend([
                    person.page_number or '',
                    person.column_index or '',
                    (person.original_text[:100] + '...') if len(person.original_text or '') > 100 else person.original_text or '',
                ])

                writer.writerow(row)

        print(f"CSV已导出: {csv_path}")

    def export_json(self, json_path: Path) -> None:
        """导出JSON"""
        data = {
            'total': len(self.persons),
            'persons': [
                {
                    'name': p.name,
                    'reading': p.reading,
                    'hometown': p.hometown,
                    'birth_date': p.birth_date,
                    'education': p.education,
                    'work_experiences': p.work_experiences,
                    'page_number': p.page_number,
                    'column_index': p.column_index,
                    'original_text': p.original_text,
                }
                for p in self.persons
            ]
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"JSON已导出: {json_path}")

    def _get_ocr_processor(self):
        if self.ocr_processor is None:
            from .ndl_ocr_batch_processor import NDLOCRBatchProcessor

            self.ocr_processor = NDLOCRBatchProcessor()
        return self.ocr_processor

    def _get_llm_ocr(self):
        if not self.use_llm_fallback:
            return None
        if self.llm_ocr is None:
            from .llm_ocr_processor import QwenVLOCRProcessor

            self.llm_ocr = QwenVLOCRProcessor(self.api_key)
        return self.llm_ocr

    def _build_entities_package(
        self,
        persons: List[PersonEntity],
        *,
        package_type: str = "biography_entities",
        source_summary: Optional[Dict[str, Any]] = None,
        quality_flags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        flags = sorted(set(quality_flags or []))
        return {
            "type": package_type,
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": self._estimate_confidence(len(persons), flags),
            "needs_review": bool(flags),
            "quality_flags": flags,
            "persons": [asdict(person) for person in persons],
            "summary": {
                "person_count": len(persons),
                "persons_with_name": sum(1 for person in persons if person.name),
                "persons_with_work_experiences": sum(1 for person in persons if person.work_experiences),
                **(source_summary or {}),
            },
            "capabilities": self.get_capabilities(),
        }

    def _entity_quality_flags(self, text: str, persons: List[PersonEntity]) -> List[str]:
        flags: List[str] = []
        if not (text or "").strip():
            flags.append("empty_text")
        if text and not persons:
            flags.append("no_biography_entities")
        if any(not person.name for person in persons):
            flags.append("person_missing_name")
        if any(not person.work_experiences for person in persons):
            flags.append("person_missing_work_experiences")
        return flags

    def _batch_quality_flags(
        self,
        ocr_results: List[Dict[str, Any]],
        persons: List[PersonEntity],
    ) -> List[str]:
        flags: List[str] = []
        if not ocr_results:
            flags.append("no_ocr_results")
        if ocr_results and not persons:
            flags.append("no_biography_entities")
        if any(not item.get("success", True) for item in (ocr_results or [])):
            flags.append("ocr_failures_present")
        if any(not item.get("text") for item in (ocr_results or [])):
            flags.append("empty_ocr_text")
        return flags

    def _estimate_confidence(self, person_count: int, quality_flags: List[str]) -> float:
        confidence = 0.45
        if person_count:
            confidence += 0.35
        confidence -= min(0.35, len(set(quality_flags)) * 0.07)
        return round(max(0.1, min(confidence, 0.95)), 2)


def extract_biographies(
    pdf_path: str,
    output_dir: str,
    dpi: int = 200,
    start_page: int = None,
    end_page: int = None,
    max_pages: int = None,
    progress_callback: Callable = None
) -> bool:
    """
    便捷函数：提取人物传记

    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        dpi: 图片分辨率
        start_page: 起始页
        end_page: 结束页
        max_pages: 最大处理页数
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    extractor = BiographyExtractor(
        pdf_path=pdf_path,
        output_dir=output_dir,
        dpi=dpi
    )

    return extractor.run(
        start_page=start_page,
        end_page=end_page,
        max_pages=max_pages,
        progress_callback=progress_callback
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="人物传记批量提取")
    parser.add_argument('pdf_path', help="PDF文件路径")
    parser.add_argument('output_dir', help="输出目录")
    parser.add_argument('--dpi', type=int, default=200, help="图片DPI")
    parser.add_argument('--start-page', type=int, help="起始页")
    parser.add_argument('--end-page', type=int, help="结束页")
    parser.add_argument('--max-pages', type=int, help="最大处理页数")

    args = parser.parse_args()

    def progress(current, total, desc):
        print(f"[{current}/{total}] {desc}")

    extract_biographies(
        args.pdf_path,
        args.output_dir,
        dpi=args.dpi,
        start_page=args.start_page,
        end_page=args.end_page,
        max_pages=args.max_pages,
        progress_callback=progress
    )
