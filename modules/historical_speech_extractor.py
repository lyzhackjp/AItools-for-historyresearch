"""
史料发言识别与年代提取模块

从OCR处理后的史料文本中识别发言内容、提取年代信息，并集成NER实体识别

核心功能：
1. 发言识别：识别史料中的对话、书信、公文等发言内容
2. 年代提取：从文本中提取年代信息（文本内年代、书籍出版年代等）
3. NER集成：调用NER模块识别历史实体
4. 结构化输出：生成结构化的史料分析结果

数据来源：
- LLM OCR处理后的JSON结果（推荐）
- CSV格式的OCR结果
- TXT格式的OCR结果

年代来源类型：
- text_internal: 文本内明确提到的年代（如"明治十年一月四日"）
- document_date: 文献本身的年代（如书信日期）
- publication_date: 书籍出版年代
- inferred_date: 根据上下文推断的年代

依赖模块：
- ner_processor.py
- llm_client.py
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from modules.ner_processor import NERProcessor, create_ner_processor
from modules.llm_client import LLMClient, create_llm_client


@dataclass
class SpeechSegment:
    """发言片段"""
    text: str
    speaker: str = ""
    speech_type: str = ""
    position: Tuple[int, int] = (0, 0)
    confidence: float = 0.0


@dataclass
class DateInfo:
    """年代信息"""
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    era_name: str = ""
    era_year: Optional[int] = None
    date_type: str = ""
    original_text: str = ""
    confidence: float = 0.0


@dataclass
class HistoricalSpeechRecord:
    """史料发言记录"""
    page_number: int
    original_page_number: Optional[int] = None
    text: str = ""
    speeches: List[SpeechSegment] = field(default_factory=list)
    dates: List[DateInfo] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    publication_info: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class HistoricalSpeechExtractor:
    """史料发言识别与年代提取处理器"""

    ERA_MAPPING = {
        '明治': {'start': 1868, 'end': 1912},
        '大正': {'start': 1912, 'end': 1926},
        '昭和': {'start': 1926, 'end': 1989},
        '平成': {'start': 1989, 'end': 2019},
        '令和': {'start': 2019, 'end': 2026},
        '慶応': {'start': 1865, 'end': 1868},
        '慶應': {'start': 1865, 'end': 1868},
        '元治': {'start': 1864, 'end': 1865},
        '文久': {'start': 1861, 'end': 1864},
        '安政': {'start': 1854, 'end': 1860},
        '嘉永': {'start': 1848, 'end': 1854},
    }

    SPEECH_PATTERNS = [
        (r'「([^」]+)」', 'direct_speech'),
        (r'『([^』]+)』', 'citation'),
        (r'（(.+?)）', 'parenthetical'),
        (r'\((.+?)\)', 'parenthetical'),
        (r'「(.+?)」', 'direct_speech'),
        (r'曰く、?(.+?)(?:と|云|言|述)', 'quoted'),
        (r'(.+?)と申候', 'formal_statement'),
        (r'(.+?)と申上候', 'formal_statement'),
        (r'(.+?)候', 'archaic_statement'),
    ]

    DATE_PATTERNS = [
        (r'(明治|大正|昭和|平成|令和|慶応|慶應|元治|文久|安政|嘉永)(\d+|元)年(\d+)月(\d+)日', 'full_date'),
        (r'(明治|大正|昭和|平成|令和|慶応|慶應|元治|文久|安政|嘉永)(\d+|元)年(\d+)月', 'year_month'),
        (r'(明治|大正|昭和|平成|令和|慶応|慶應|元治|文久|安政|嘉永)(\d+|元)年', 'era_year'),
        (r'(明治|大正|昭和|平成|令和|慶応|慶應|元治|文久|安政|嘉永)(\d+)', 'era_year_short'),
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', 'western_full_date'),
        (r'(\d{4})年(\d{1,2})月', 'western_year_month'),
        (r'(\d{4})年', 'western_year'),
        (r'(明治|大正|昭和|平成|令和|慶応|慶應|元治|文久|安政|嘉永)(\d+|元)年\s*(\d+)月\s*(\d+)日', 'full_date_space'),
        (r'([一二三四五六七八九十]+)月([一二三四五六七八九十]+)日', 'kanji_month_day'),
        (r'(\d{1,2})月(\d{1,2})日', 'month_day'),
    ]

    SPEAKER_PATTERNS = [
        r'(.+?)(?:曰|云|言|述|申|書|寄せ)',
        r'(.+?)殿',
        r'(.+?)卿',
        r'(.+?)公',
        r'(.+?)氏',
        r'(.+?)閣下',
        r'(.+?)より',
        r'(.+?)よりの書',
        r'(.+?)の書',
    ]

    SPEECH_TYPE_MAPPING = {
        'direct_speech': '直接引语',
        'citation': '引用文献',
        'parenthetical': '括号注释',
        'quoted': '间接引语',
        'formal_statement': '正式陈述',
        'archaic_statement': '古文陈述',
    }

    def __init__(self, api_provider: str = "qwen", test_mode: bool = False):
        """
        初始化处理器

        Args:
            api_provider: API提供商
            test_mode: 测试模式标志
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.ner_processor = None
        self.llm_client = None

        self._init_processors()

    def _init_processors(self):
        """初始化处理器组件"""
        if not self.test_mode:
            try:
                self.ner_processor = create_ner_processor(
                    api_provider=self.api_provider,
                    test_mode=False
                )
            except Exception as e:
                print(f"NER处理器初始化失败: {e}")
                self.ner_processor = create_ner_processor(
                    api_provider=self.api_provider,
                    test_mode=True
                )

            try:
                config = {
                    'provider': 'dashscope' if self.api_provider == 'qwen' else self.api_provider,
                    'model': 'qwen-turbo' if self.api_provider == 'qwen' else 'gpt-4'
                }
                self.llm_client = create_llm_client(config)
            except Exception as e:
                print(f"LLM客户端初始化失败: {e}")
                self.llm_client = None

    def load_ocr_result(self, file_path: str) -> Dict[str, Any]:
        """
        加载OCR结果文件

        Args:
            file_path: OCR结果文件路径

        Returns:
            dict: 加载的数据
        """
        path = Path(file_path)

        if path.suffix.lower() == '.json':
            return self._load_json_result(file_path)
        elif path.suffix.lower() == '.csv':
            return self._load_csv_result(file_path)
        elif path.suffix.lower() == '.txt':
            return self._load_txt_result(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {path.suffix}")

    def _load_json_result(self, file_path: str) -> Dict[str, Any]:
        """加载JSON格式的OCR结果"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        result = {
            'metadata': data.get('metadata', {}),
            'header_footer_changes': data.get('header_footer_changes', []),
            'pages': []
        }

        for page in data.get('pages', []):
            result['pages'].append({
                'pdf_page_number': page.get('pdf_page_number'),
                'ocr_page_number': page.get('ocr_page_number'),
                'header': page.get('header', ''),
                'footer': page.get('footer', ''),
                'text': page.get('text', ''),
                'text_length': page.get('text_length', 0)
            })

        return result

    def _load_csv_result(self, file_path: str) -> Dict[str, Any]:
        """加载CSV格式的OCR结果"""
        import csv

        result = {
            'metadata': {},
            'header_footer_changes': [],
            'pages': []
        }

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                result['pages'].append({
                    'pdf_page_number': int(row.get('PDF页码', 0)) if row.get('PDF页码') else None,
                    'ocr_page_number': int(row.get('原书页码', 0)) if row.get('原书页码') else None,
                    'header': row.get('页眉', ''),
                    'footer': row.get('页脚', ''),
                    'text': row.get('文本内容', ''),
                    'text_length': int(row.get('文本长度', 0)) if row.get('文本长度') else 0
                })

        return result

    def _load_txt_result(self, file_path: str) -> Dict[str, Any]:
        """加载TXT格式的OCR结果"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        result = {
            'metadata': {},
            'header_footer_changes': [],
            'pages': []
        }

        page_pattern = r'【PDF第(\d+)页(?:\s*/\s*原书第(.+?)页)?】\s*\n-+\n(.*?)(?=【PDF第|$)'
        matches = re.findall(page_pattern, content, re.DOTALL)

        for match in matches:
            pdf_page = int(match[0])
            ocr_page_text = match[1].strip() if match[1] else None
            text = match[2].strip()

            ocr_page = None
            if ocr_page_text:
                ocr_page = self._parse_page_number_text(ocr_page_text)

            result['pages'].append({
                'pdf_page_number': pdf_page,
                'ocr_page_number': ocr_page,
                'header': '',
                'footer': '',
                'text': text,
                'text_length': len(text)
            })

        return result

    def _parse_page_number_text(self, text: str) -> Optional[int]:
        """解析页码文本"""
        kanji_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '二十': 20, '三十': 30, '四十': 40, '五十': 50
        }

        text = text.strip()
        if text in kanji_map:
            return kanji_map[text]

        try:
            return int(text)
        except ValueError:
            return None

    def extract_speeches(self, text: str) -> List[SpeechSegment]:
        """
        从文本中提取发言内容

        Args:
            text: 待处理的文本

        Returns:
            list: 发言片段列表
        """
        speeches = []

        for pattern, speech_type in self.SPEECH_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                speech_text = match.group(1) if match.lastindex else match.group(0)

                speaker = self._extract_speaker(text, match.start())

                speeches.append(SpeechSegment(
                    text=speech_text.strip(),
                    speaker=speaker,
                    speech_type=self.SPEECH_TYPE_MAPPING.get(speech_type, speech_type),
                    position=(match.start(), match.end()),
                    confidence=0.8 if speaker else 0.6
                ))

        return speeches

    def _extract_speaker(self, text: str, position: int) -> str:
        """提取发言者"""
        context_start = max(0, position - 100)
        context = text[context_start:position]

        for pattern in self.SPEAKER_PATTERNS:
            match = re.search(pattern + r'\s*$', context)
            if match:
                speaker = match.group(1).strip()
                speaker = re.sub(r'[　\s]+', '', speaker)
                if len(speaker) <= 20 and speaker:
                    return speaker

        return ""

    def extract_dates(self, text: str) -> List[DateInfo]:
        """
        从文本中提取年代信息

        Args:
            text: 待处理的文本

        Returns:
            list: 年代信息列表
        """
        dates = []

        for pattern, date_type in self.DATE_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                date_info = self._parse_date_match(match, date_type)
                if date_info:
                    dates.append(date_info)

        return dates

    def _parse_date_match(self, match: re.Match, date_type: str) -> Optional[DateInfo]:
        """解析日期匹配"""
        try:
            groups = match.groups()
            original_text = match.group(0)

            if date_type == 'full_date':
                era_name = groups[0]
                era_year_str = groups[1]
                month = int(groups[2])
                day = int(groups[3])

                era_year = 1 if era_year_str == '元' else int(era_year_str)
                year = self._era_to_western_year(era_name, era_year)

                return DateInfo(
                    year=year,
                    month=month,
                    day=day,
                    era_name=era_name,
                    era_year=era_year,
                    date_type='text_internal',
                    original_text=original_text,
                    confidence=0.95
                )

            elif date_type == 'year_month':
                era_name = groups[0]
                era_year_str = groups[1]
                month = int(groups[2])

                era_year = 1 if era_year_str == '元' else int(era_year_str)
                year = self._era_to_western_year(era_name, era_year)

                return DateInfo(
                    year=year,
                    month=month,
                    era_name=era_name,
                    era_year=era_year,
                    date_type='text_internal',
                    original_text=original_text,
                    confidence=0.90
                )

            elif date_type == 'era_year':
                era_name = groups[0]
                era_year_str = groups[1]

                era_year = 1 if era_year_str == '元' else int(era_year_str)
                year = self._era_to_western_year(era_name, era_year)

                return DateInfo(
                    year=year,
                    era_name=era_name,
                    era_year=era_year,
                    date_type='text_internal',
                    original_text=original_text,
                    confidence=0.85
                )

            elif date_type == 'era_year_short':
                era_name = groups[0]
                era_year = int(groups[1])
                year = self._era_to_western_year(era_name, era_year)

                return DateInfo(
                    year=year,
                    era_name=era_name,
                    era_year=era_year,
                    date_type='text_internal',
                    original_text=original_text,
                    confidence=0.80
                )

            elif date_type == 'western_full_date':
                year = int(groups[0])
                month = int(groups[1])
                day = int(groups[2])

                return DateInfo(
                    year=year,
                    month=month,
                    day=day,
                    date_type='text_internal',
                    original_text=original_text,
                    confidence=0.95
                )

            elif date_type == 'western_year_month':
                year = int(groups[0])
                month = int(groups[1])

                return DateInfo(
                    year=year,
                    month=month,
                    date_type='text_internal',
                    original_text=original_text,
                    confidence=0.90
                )

            elif date_type == 'western_year':
                year = int(groups[0])

                return DateInfo(
                    year=year,
                    date_type='text_internal',
                    original_text=original_text,
                    confidence=0.85
                )

            elif date_type == 'full_date_space':
                era_name = groups[0]
                era_year_str = groups[1]
                month = int(groups[2])
                day = int(groups[3])

                era_year = 1 if era_year_str == '元' else int(era_year_str)
                year = self._era_to_western_year(era_name, era_year)

                return DateInfo(
                    year=year,
                    month=month,
                    day=day,
                    era_name=era_name,
                    era_year=era_year,
                    date_type='text_internal',
                    original_text=original_text,
                    confidence=0.95
                )

            elif date_type == 'kanji_month_day':
                kanji_month = self._kanji_to_number(groups[0])
                kanji_day = self._kanji_to_number(groups[1])

                if kanji_month and kanji_day:
                    return DateInfo(
                        month=kanji_month,
                        day=kanji_day,
                        date_type='text_internal',
                        original_text=original_text,
                        confidence=0.70
                    )

            elif date_type == 'month_day':
                month = int(groups[0])
                day = int(groups[1])

                return DateInfo(
                    month=month,
                    day=day,
                    date_type='text_internal',
                    original_text=original_text,
                    confidence=0.75
                )

        except (ValueError, IndexError):
            pass

        return None

    def _era_to_western_year(self, era_name: str, era_year: int) -> Optional[int]:
        """将年号转换为西历年份"""
        if era_name in self.ERA_MAPPING:
            era_info = self.ERA_MAPPING[era_name]
            return era_info['start'] + era_year - 1
        return None

    def _kanji_to_number(self, kanji: str) -> Optional[int]:
        """将汉字数字转换为阿拉伯数字"""
        kanji_map = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
            '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
            '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24, '二十五': 25,
            '二十六': 26, '二十七': 27, '二十八': 28, '二十九': 29, '三十': 30,
            '三十一': 31
        }

        kanji = kanji.strip()
        if kanji in kanji_map:
            return kanji_map[kanji]

        if '十' in kanji:
            match = re.match(r'([一二三四五六七八九])?十([一二三四五六七八九])?', kanji)
            if match:
                tens = kanji_map.get(match.group(1), 0) if match.group(1) else 1
                ones = kanji_map.get(match.group(2), 0) if match.group(2) else 0
                return tens * 10 + ones

        try:
            return int(kanji)
        except ValueError:
            return None

    def extract_entities(self, text: str, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        提取命名实体

        Args:
            text: 待处理的文本
            categories: 要提取的实体类型

        Returns:
            list: 实体列表
        """
        if self.ner_processor:
            try:
                return self.ner_processor.recognize_historical_entities(text, categories)
            except Exception as e:
                print(f"NER提取失败: {e}")

        return self._extract_entities_by_dict(text, categories)

    def _extract_entities_by_dict(self, text: str, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """使用词典提取实体"""
        entities = []

        dict_path = Path(__file__).parent.parent / 'data' / 'dictionaries' / 'historical_entities.json'

        if dict_path.exists():
            with open(dict_path, 'r', encoding='utf-8') as f:
                entity_dict = json.load(f)

            target_categories = categories or list(entity_dict.get('categories', {}).keys())

            for category in target_categories:
                if category in entity_dict.get('categories', {}):
                    entity_list = entity_dict['categories'][category].get('entities', [])

                    for entity_name in entity_list:
                        start = 0
                        while True:
                            pos = text.find(entity_name, start)
                            if pos == -1:
                                break

                            entities.append({
                                'entity': entity_name,
                                'category': category,
                                'start_pos': pos,
                                'end_pos': pos + len(entity_name),
                                'confidence': 1.0,
                                'source': 'dictionary'
                            })
                            start = pos + 1

        return entities

    def analyze_publication_date(self, ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析文献出版年代

        Args:
            ocr_data: OCR数据

        Returns:
            dict: 出版信息
        """
        publication_info = {
            'inferred_year': None,
            'era': None,
            'confidence': 0.0,
            'evidence': []
        }

        all_dates = []

        for page in ocr_data.get('pages', []):
            text = page.get('text', '')
            dates = self.extract_dates(text)
            all_dates.extend(dates)

        if all_dates:
            years = [d.year for d in all_dates if d.year]
            if years:
                max_year = max(years)
                publication_info['inferred_year'] = max_year
                publication_info['evidence'].append(f"文本中最晚年代: {max_year}年")

                for era_name, era_info in self.ERA_MAPPING.items():
                    if era_info['start'] <= max_year <= era_info['end']:
                        publication_info['era'] = era_name
                        break

                publication_info['confidence'] = 0.7

        headers = []
        for page in ocr_data.get('pages', []):
            header = page.get('header', '')
            if header:
                headers.append(header)

        for header in headers:
            for era_name in self.ERA_MAPPING.keys():
                if era_name in header:
                    publication_info['era'] = era_name
                    publication_info['evidence'].append(f"页眉包含年号: {era_name}")
                    publication_info['confidence'] = max(publication_info['confidence'], 0.6)

        all_text = ""
        for page in ocr_data.get('pages', []):
            all_text += page.get('text', '') + "\n"

        era_year_pattern = r'(明治|大正|昭和|平成|令和|慶応|慶應|元治|文久|安政|嘉永)\s*(\d+|元)\s*年'
        era_matches = re.findall(era_year_pattern, all_text)

        if era_matches:
            era_years = []
            for era_name, year_str in era_matches:
                year_num = 1 if year_str == '元' else int(year_str)
                western_year = self._era_to_western_year(era_name, year_num)
                if western_year:
                    era_years.append(western_year)

            if era_years:
                max_era_year = max(era_years)
                if not publication_info['inferred_year'] or max_era_year > publication_info['inferred_year']:
                    publication_info['inferred_year'] = max_era_year
                    publication_info['evidence'].append(f"年号推断年份: {max_era_year}年")
                    publication_info['confidence'] = max(publication_info['confidence'], 0.8)

        return publication_info

    def process_page(self, page_data: Dict[str, Any],
                    publication_info: Dict[str, Any]) -> HistoricalSpeechRecord:
        """
        处理单个页面

        Args:
            page_data: 页面数据
            publication_info: 出版信息

        Returns:
            HistoricalSpeechRecord: 处理结果
        """
        text = page_data.get('text', '')

        speeches = self.extract_speeches(text)

        dates = self.extract_dates(text)

        entities = self.extract_entities(text)

        for date in dates:
            date.date_type = 'text_internal'

        return HistoricalSpeechRecord(
            page_number=page_data.get('pdf_page_number', 0),
            original_page_number=page_data.get('ocr_page_number'),
            text=text,
            speeches=speeches,
            dates=dates,
            entities=entities,
            publication_info=publication_info,
            metadata={
                'header': page_data.get('header', ''),
                'footer': page_data.get('footer', ''),
                'text_length': len(text)
            }
        )

    def process_ocr_result(self, ocr_data: Dict[str, Any]) -> List[HistoricalSpeechRecord]:
        """
        处理OCR结果

        Args:
            ocr_data: OCR数据

        Returns:
            list: 处理结果列表
        """
        publication_info = self.analyze_publication_date(ocr_data)

        results = []
        for page_data in ocr_data.get('pages', []):
            record = self.process_page(page_data, publication_info)
            results.append(record)

        return results

    def get_capabilities(self) -> Dict[str, Any]:
        """Return a capability snapshot for workflow and agent routing."""

        return {
            "module": "historical_speech_extractor",
            "layer": "analysis",
            "backend": "script" if self.test_mode or not self.llm_client else "hybrid",
            "provider": self.api_provider,
            "model": None if self.test_mode or not self.llm_client else "configured_llm",
            "tasks": [
                "speech_segmentation",
                "date_resolution",
                "entity_attach",
                "ocr_speech_analysis",
            ],
            "output_types": ["historical_speech_analysis"],
            "components": {
                "speech_segmenter": "regex_rules",
                "date_resolver": "era_and_western_year_rules",
                "entity_attach": "ner_processor_or_dictionary",
                "llm_enhancement": bool(self.llm_client and not self.test_mode),
            },
            "supports": {
                "ocr_json": True,
                "ocr_csv": True,
                "ocr_txt": True,
                "package_output": True,
                "external_ai_backend": bool(self.llm_client and not self.test_mode),
            },
            "privacy": {
                "secrets_required": False if self.test_mode else bool(self.llm_client),
                "logs_raw_text": False,
                "local_first": True,
            },
        }

    def analyze_text_package(
        self,
        text: str,
        page_number: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        enhance: bool = False,
    ) -> Dict[str, Any]:
        """Analyze a single text block and return a package envelope."""

        metadata = metadata or {}
        ocr_data = {
            "metadata": metadata,
            "pages": [
                {
                    "pdf_page_number": page_number,
                    "ocr_page_number": metadata.get("ocr_page_number"),
                    "header": metadata.get("header", ""),
                    "footer": metadata.get("footer", ""),
                    "text": text or "",
                    "text_length": len(text or ""),
                }
            ],
        }
        return self.process_ocr_result_package(ocr_data, enhance=enhance)

    def process_ocr_result_package(
        self,
        ocr_data: Dict[str, Any],
        enhance: bool = False,
    ) -> Dict[str, Any]:
        """Analyze OCR data and return a workflow-friendly package envelope."""

        quality_flags = []
        records: List[HistoricalSpeechRecord] = []
        error = ""
        try:
            records = self.process_ocr_result(ocr_data)
            if enhance:
                records = [self.enhance_with_llm(record) for record in records]
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            quality_flags.append("speech_analysis_failed")

        stats = self.get_statistics(records) if records else {
            "total_pages": 0,
            "total_speeches": 0,
            "total_dates": 0,
            "total_entities": 0,
            "unique_speakers": 0,
            "top_speakers": [],
            "entity_type_distribution": {},
            "year_range": None,
        }
        page_count = len(ocr_data.get("pages", [])) if isinstance(ocr_data, dict) else 0
        if page_count == 0:
            quality_flags.append("no_pages")
        if records and stats.get("total_speeches", 0) == 0:
            quality_flags.append("no_speeches_detected")
        if records and stats.get("total_dates", 0) == 0:
            quality_flags.append("no_dates_detected")
        if records and stats.get("total_entities", 0) == 0:
            quality_flags.append("no_entities_attached")

        success = bool(records) and not error
        publication_info = records[0].publication_info if records else {}

        return {
            "type": "historical_speech_analysis",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script" if self.test_mode or not self.llm_client else "hybrid",
            "provider": self.api_provider,
            "model": None if self.test_mode or not self.llm_client else "configured_llm",
            "confidence": self._package_confidence(success, quality_flags, stats),
            "needs_review": (not success) or bool(quality_flags),
            "quality_flags": quality_flags,
            "records": [self._record_to_dict(record) for record in records],
            "statistics": stats,
            "publication_info": publication_info,
            "source_summary": {
                "page_count": page_count,
                "metadata_keys": sorted(list(ocr_data.get("metadata", {}).keys())) if isinstance(ocr_data, dict) else [],
            },
            "capabilities": self.get_capabilities(),
            "error": error,
        }

    def _record_to_dict(self, record: HistoricalSpeechRecord) -> Dict[str, Any]:
        return {
            "page_number": record.page_number,
            "original_page_number": record.original_page_number,
            "text_length": len(record.text or ""),
            "speeches": [asdict(speech) for speech in record.speeches],
            "dates": [asdict(date) for date in record.dates],
            "entities": record.entities,
            "publication_info": record.publication_info,
            "metadata": record.metadata,
        }

    def _package_confidence(
        self,
        success: bool,
        quality_flags: List[str],
        stats: Dict[str, Any],
    ) -> float:
        if not success:
            return 0.0
        score = 0.55
        if stats.get("total_speeches", 0) > 0:
            score += 0.15
        if stats.get("total_dates", 0) > 0:
            score += 0.15
        if stats.get("total_entities", 0) > 0:
            score += 0.10
        if quality_flags:
            score -= min(0.25, 0.05 * len(quality_flags))
        return round(max(0.0, min(1.0, score)), 2)

    def enhance_with_llm(self, record: HistoricalSpeechRecord) -> HistoricalSpeechRecord:
        """
        使用LLM增强分析结果

        Args:
            record: 原始记录

        Returns:
            HistoricalSpeechRecord: 增强后的记录
        """
        if not self.llm_client or self.test_mode:
            return record

        try:
            prompt = f"""请分析以下日本历史史料片段，识别：
1. 发言者及其发言内容
2. 年代信息
3. 重要历史实体

【史料文本】
{record.text[:2000]}

请以JSON格式输出：
{{
    "speeches": [
        {{
            "speaker": "发言者",
            "content": "发言内容",
            "type": "发言类型（书信/对话/公文等）"
        }}
    ],
    "dates": [
        {{
            "year": 年份,
            "month": 月份,
            "day": 日期,
            "era": "年号",
            "context": "年代上下文"
        }}
    ],
    "entities": [
        {{
            "name": "实体名称",
            "type": "实体类型",
            "significance": "历史意义"
        }}
    ]
}}"""

            response = self.llm_client._call_llm(prompt, temperature=0.1)
            content = response.get('content', '')

            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                llm_result = json.loads(json_match.group(0))

                for speech_data in llm_result.get('speeches', []):
                    for speech in record.speeches:
                        if speech_data.get('speaker') and not speech.speaker:
                            speech.speaker = speech_data['speaker']
                            speech.confidence = 0.9

                for date_data in llm_result.get('dates', []):
                    if date_data.get('year'):
                        existing_years = [d.year for d in record.dates]
                        if date_data['year'] not in existing_years:
                            record.dates.append(DateInfo(
                                year=date_data.get('year'),
                                month=date_data.get('month'),
                                day=date_data.get('day'),
                                era_name=date_data.get('era', ''),
                                date_type='llm_inferred',
                                original_text=date_data.get('context', ''),
                                confidence=0.75
                            ))

        except Exception as e:
            print(f"LLM增强失败: {e}")

        return record

    def export_results(self, records: List[HistoricalSpeechRecord],
                      output_path: str, format: str = 'json'):
        """
        导出处理结果

        Args:
            records: 处理结果列表
            output_path: 输出路径
            format: 输出格式 ('json', 'csv', 'markdown')
        """
        if format == 'json':
            self._export_json(records, output_path)
        elif format == 'csv':
            self._export_csv(records, output_path)
        elif format == 'markdown':
            self._export_markdown(records, output_path)

    def _export_json(self, records: List[HistoricalSpeechRecord], output_path: str):
        """导出JSON格式"""
        data = {
            'metadata': {
                'processing_date': datetime.now().isoformat(),
                'total_pages': len(records),
                'total_speeches': sum(len(r.speeches) for r in records),
                'total_dates': sum(len(r.dates) for r in records),
                'total_entities': sum(len(r.entities) for r in records)
            },
            'records': []
        }

        for record in records:
            record_dict = {
                'page_number': record.page_number,
                'original_page_number': record.original_page_number,
                'text': record.text,
                'speeches': [asdict(s) for s in record.speeches],
                'dates': [asdict(d) for d in record.dates],
                'entities': record.entities,
                'publication_info': record.publication_info,
                'metadata': record.metadata
            }
            data['records'].append(record_dict)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"JSON导出完成: {output_path}")

    def _export_csv(self, records: List[HistoricalSpeechRecord], output_path: str):
        """导出CSV格式"""
        import csv

        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)

            writer.writerow([
                'PDF页码', '原书页码', '发言者', '发言内容', '发言类型',
                '年代', '年号', '实体名称', '实体类型', '置信度'
            ])

            for record in records:
                for speech in record.speeches:
                    for date in record.dates:
                        for entity in record.entities:
                            writer.writerow([
                                record.page_number,
                                record.original_page_number or '',
                                speech.speaker,
                                speech.text[:100],
                                speech.speech_type,
                                date.year or '',
                                date.era_name,
                                entity.get('entity', ''),
                                entity.get('category', ''),
                                speech.confidence
                            ])

        print(f"CSV导出完成: {output_path}")

    def _export_markdown(self, records: List[HistoricalSpeechRecord], output_path: str):
        """导出Markdown格式"""
        lines = [
            "# 史料发言识别与年代提取结果",
            "",
            f"**处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**总页数**: {len(records)}",
            f"**总发言数**: {sum(len(r.speeches) for r in records)}",
            f"**总年代数**: {sum(len(r.dates) for r in records)}",
            f"**总实体数**: {sum(len(r.entities) for r in records)}",
            "",
            "---",
            ""
        ]

        for record in records:
            lines.append(f"## 第{record.page_number}页")
            if record.original_page_number:
                lines.append(f"**原书页码**: {record.original_page_number}")
            lines.append("")

            if record.speeches:
                lines.append("### 发言内容")
                for i, speech in enumerate(record.speeches, 1):
                    lines.append(f"**{i}. {speech.speech_type}**")
                    if speech.speaker:
                        lines.append(f"- 发言者: {speech.speaker}")
                    lines.append(f"- 内容: {speech.text[:200]}...")
                    lines.append(f"- 置信度: {speech.confidence:.2f}")
                    lines.append("")

            if record.dates:
                lines.append("### 年代信息")
                for date in record.dates:
                    date_str = f"{date.year}年"
                    if date.month:
                        date_str += f"{date.month}月"
                    if date.day:
                        date_str += f"{date.day}日"
                    if date.era_name:
                        date_str += f" ({date.era_name}{date.era_year or ''}年)"
                    lines.append(f"- {date_str}")
                    lines.append(f"  - 原文: {date.original_text}")
                    lines.append(f"  - 类型: {date.date_type}")
                    lines.append("")

            if record.entities:
                lines.append("### 命名实体")
                entity_by_type = defaultdict(list)
                for entity in record.entities:
                    entity_by_type[entity.get('category', 'unknown')].append(entity)

                for category, entities in entity_by_type.items():
                    lines.append(f"**{category}**: {', '.join([e['entity'] for e in entities[:10]])}")
                lines.append("")

            lines.append("---")
            lines.append("")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"Markdown导出完成: {output_path}")

    def get_statistics(self, records: List[HistoricalSpeechRecord]) -> Dict[str, Any]:
        """
        获取统计信息

        Args:
            records: 处理结果列表

        Returns:
            dict: 统计信息
        """
        total_speeches = sum(len(r.speeches) for r in records)
        total_dates = sum(len(r.dates) for r in records)
        total_entities = sum(len(r.entities) for r in records)

        speaker_counts = defaultdict(int)
        for record in records:
            for speech in record.speeches:
                if speech.speaker:
                    speaker_counts[speech.speaker] += 1

        entity_type_counts = defaultdict(int)
        for record in records:
            for entity in record.entities:
                entity_type_counts[entity.get('category', 'unknown')] += 1

        years = []
        for record in records:
            for date in record.dates:
                if date.year:
                    years.append(date.year)

        year_range = None
        if years:
            year_range = {
                'min': min(years),
                'max': max(years)
            }

        return {
            'total_pages': len(records),
            'total_speeches': total_speeches,
            'total_dates': total_dates,
            'total_entities': total_entities,
            'unique_speakers': len(speaker_counts),
            'top_speakers': sorted(speaker_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            'entity_type_distribution': dict(entity_type_counts),
            'year_range': year_range
        }


def create_speech_extractor(api_provider: str = "qwen",
                           test_mode: bool = False) -> HistoricalSpeechExtractor:
    """
    工厂函数：创建处理器实例

    Args:
        api_provider: API提供商
        test_mode: 是否使用测试模式

    Returns:
        HistoricalSpeechExtractor: 配置好的处理器实例
    """
    return HistoricalSpeechExtractor(api_provider=api_provider, test_mode=test_mode)
