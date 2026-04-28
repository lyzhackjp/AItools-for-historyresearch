"""
人物传记NER模块
从识别文本中提取：人名、本籍、学历、工作经历、工作单位、时间
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class PersonEntity:
    """人物实体"""
    name: str = ""                           # 姓名
    original_text: str = ""                  # 原始文本
    hometown: Optional[str] = None           # 本籍
    education: Optional[str] = None          # 学历
    work_experiences: List[Dict[str, str]] = field(default_factory=list)  # 工作经历 [{unit, position, date_range, description}]
    photo_area: Optional[str] = None        # 照片区域文本
    page_number: Optional[int] = None        # 页码
    block_index: Optional[int] = None       # 块索引


@dataclass
class WorkExperience:
    """工作经历"""
    unit: str = ""                          # 工作单位
    position: Optional[str] = None          # 职位
    start_date: Optional[str] = None        # 开始时间
    end_date: Optional[str] = None         # 结束时间
    description: Optional[str] = None       # 描述
    original_text: str = ""                  # 原始文本


class BiographicalNER:
    """传记NER处理器"""

    # 日文年份转换
    WAREKI_MAP = {
        '明治': 1868, '大正': 1912, '昭和': 1926, '平成': 1989, '令和': 2019,
        '元年': 1
    }

    # 常见学历关键词
    EDUCATION_PATTERNS = [
        r'(?:東京大学|東北大|北大|名大|阪大|九大|九州大学| Harvard| Yale| Oxford| Cambridge)',
        r'卒業[于人]?\s*：?\s*([^\n,，]+)',
        r'学歴[：:]\s*([^\n]+)',
        r'(?:学士|修士|博士|学位)',
        r'教育[：:]\s*([^\n]+)',
    ]

    # 本籍关键词
    HOMETOWN_PATTERNS = [
        r'本籍[：:]\s*([^\n,，]+)',
        r'出身地[：:]\s*([^\n,，]+)',
        r'生于[^\n,，]+',
        r'出生[^\n,，]+',
    ]

    # 工作经历关键词
    WORK_PATTERNS = [
        # 格式: "单位 职位 时间"
        r'([^\n,，]{2,20}?(?:大学|学校|省|庁|庁|部|課|会社|銀行|鉄路|満鉄|満炭|満業|会社))[^\n,，]{0,30}?((?:昭和|平成|令和|明治|大正)\s*\d+年?(?:-\d+年?)?)',
        r'([^\n,，]{2,30}?)[^\n,，]*?((?:昭和|平成|令和|明治|大正)\d+年[^\n,，]{0,20})',
        r'昭和\d+年[^\n,，]+?([^\n,，]{2,30}?(?:大学|学校|省|庁|公司|銀行|鉄道|満鉄|満炭))',
        r'任职[^\n,，]+',
        r'履歴[：:]\s*([^\n]+)',
    ]

    # 日期待识别模式
    DATE_PATTERNS = [
        r'(昭和|平成|令和|明治|大正)\s*(\d+)年(?:\s*(\d+)月)?(?:\s*(\d+)日)?',
        r'(\d{4})年(?:\s*(\d{1,2})月)?(?:\s*(\d{1,2})日)?',
        r'(\d+)年(?:-\d+年)?',
    ]

    def __init__(self):
        """初始化NER"""
        self.persons: List[PersonEntity] = []

    def get_capabilities(self) -> Dict[str, Any]:
        """Return an agent/workflow-facing capability snapshot."""
        return {
            "module": "biographical_ner",
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "layer": "specialized_analysis",
            "input_formats": ["text_blocks"],
            "output_types": ["biography_entities"],
            "capabilities": [
                "person_name_extraction",
                "hometown_extraction",
                "education_extraction",
                "work_experience_extraction",
                "wareki_date_normalization",
                "package_output",
            ],
            "fallback_order": ["script:local_rules", "biography_extractor", "local_llm", "skill", "mcp"],
            "privacy": {
                "offline_by_default": True,
                "external_api_required": False,
                "secret_file_loading": False,
            },
        }

    def process_text_blocks_package(self, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process text blocks and return a stable package."""
        persons = self.process_text_blocks(blocks)
        self.sort_work_experiences_by_date()
        quality_flags = self._quality_flags(blocks, persons)
        return {
            "type": "biography_entities",
            "schema_version": "1.0",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "script",
            "provider": "local_rules",
            "model": None,
            "confidence": self._estimate_confidence(len(persons), quality_flags),
            "needs_review": bool(quality_flags),
            "quality_flags": quality_flags,
            "persons": [asdict(person) for person in persons],
            "summary": {
                "block_count": len(blocks or []),
                "person_count": len(persons),
                "persons_with_name": sum(1 for person in persons if person.name),
                "persons_with_work_experiences": sum(1 for person in persons if person.work_experiences),
            },
            "capabilities": self.get_capabilities(),
        }

    def parse_wareki_date(self, date_str: str) -> Optional[Tuple[int, int, int]]:
        """
        解析和历日期

        Args:
            date_str: 和历日期字符串，如"昭和15年3月"

        Returns:
            (年, 月, 日)元组
        """
        # 和历匹配
        for era_name, era_start in self.WAREKI_MAP.items():
            pattern = rf'{era_name}\s*(\d+)年(?:\s*(\d+)月)?(?:\s*(\d+)日)?'
            match = re.search(pattern, date_str)
            if match:
                year = int(match.group(1))
                month = int(match.group(2)) if match.group(2) else 1
                day = int(match.group(3)) if match.group(3) else 1
                return (era_start + year - 1, month, day)

        # 西历匹配
        pattern = r'(\d{4})年(?:\s*(\d{1,2})月)?(?:\s*(\d{1,2})日)?'
        match = re.search(pattern, date_str)
        if match:
            year = int(match.group(1))
            month = int(match.group(2)) if match.group(2) else 1
            day = int(match.group(3)) if match.group(3) else 1
            return (year, month, day)

        return None

    def parse_date_range(self, date_range_str: str) -> Tuple[Optional[Tuple], Optional[Tuple]]:
        """
        解析日期范围

        Args:
            date_range_str: 如"昭和15年-昭和20年"或"1930年-1940年"

        Returns:
            ((开始年,月,日), (结束年,月,日))
        """
        parts = re.split(r'[-–—]', date_range_str)
        if len(parts) >= 2:
            start = self.parse_wareki_date(parts[0].strip())
            end = self.parse_wareki_date(parts[1].strip())
            return (start, end)
        elif len(parts) == 1:
            single = self.parse_wareki_date(parts[0].strip())
            return (single, single)
        return (None, None)

    def extract_name(self, text: str) -> Optional[str]:
        """
        从文本中提取姓名

        Args:
            text: 输入文本

        Returns:
            姓名或None
        """
        # 匹配粗体大字（通常是姓名）
        # 在日文文献中，姓名通常是大字粗体
        patterns = [
            r'^([一-龥]{2,5})\s*(?:氏|君|name)',  # 姓名+氏/君
            r'([一-龥]{2,5})\s*[（(].*?[）)]',   # 姓名（括号内通常是读音）
            r'^([一-龥]{2,5})\s*$',               # 行首姓名
        ]

        candidates = [text] + [line.strip() for line in text.splitlines() if line.strip()]
        for candidate in candidates:
            for pattern in patterns:
                match = re.search(pattern, candidate)
                if match:
                    name = match.group(1).strip()
                    if len(name) >= 2 and len(name) <= 5:
                        return name

        return None

    def extract_hometown(self, text: str) -> Optional[str]:
        """
        提取本籍/出身地

        Args:
            text: 输入文本

        Returns:
            本籍或None
        """
        for pattern in self.HOMETOWN_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def extract_education(self, text: str) -> Optional[str]:
        """
        提取学历信息

        Args:
            text: 输入文本

        Returns:
            学历或None
        """
        for pattern in self.EDUCATION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return None

    def extract_work_experiences(self, text: str) -> List[Dict[str, str]]:
        """
        提取工作经历

        Args:
            text: 输入文本

        Returns:
            工作经历列表
        """
        experiences = []

        # 分割可能的工作条目
        lines = text.split('\n')

        for line in lines:
            # 跳过太短的行
            if len(line.strip()) < 5:
                continue

            # 查找日期模式
            date_match = None
            for date_pattern in self.DATE_PATTERNS:
                date_match = re.search(date_pattern, line)
                if date_match:
                    break

            if not date_match:
                continue

            # 提取日期范围
            date_str = date_match.group(0)
            start_end = self.parse_date_range(date_str)

            # 查找单位名称
            unit_patterns = [
                r'([^\n,，]{2,20}?(?:大学|学校|省|庁|公司|銀行|病院|鉄道|局|部|課))',
                r'([^\n,，]{2,30}?(?:満鉄|満炭|満業|南満洲鉄道|鞍山製鉄))',
            ]

            unit = None
            for unit_pattern in unit_patterns:
                unit_match = re.search(unit_pattern, line)
                if unit_match:
                    unit = unit_match.group(1).strip()
                    break

            if unit:
                exp = {
                    'unit': unit,
                    'date_range': date_str,
                    'start': start_end[0],
                    'end': start_end[1],
                    'description': line.strip(),
                }
                experiences.append(exp)

        return experiences

    def extract_person_from_block(self, text: str, page_num: int = None, block_idx: int = None) -> Optional[PersonEntity]:
        """
        从文本块中提取人物信息

        Args:
            text: 文本块
            page_num: 页码
            block_idx: 块索引

        Returns:
            PersonEntity或None
        """
        person = PersonEntity()
        person.original_text = text
        person.page_number = page_num
        person.block_index = block_idx

        # 提取姓名
        name = self.extract_name(text)
        if name:
            person.name = name

        # 提取本籍
        hometown = self.extract_hometown(text)
        if hometown:
            person.hometown = hometown

        # 提取学历
        education = self.extract_education(text)
        if education:
            person.education = education

        # 提取工作经历
        experiences = self.extract_work_experiences(text)
        if experiences:
            person.work_experiences = experiences

        # 只有姓名或工作经历才认为有效
        if person.name or person.work_experiences:
            return person

        return None

    def process_text_blocks(self, blocks: List[Dict[str, Any]]) -> List[PersonEntity]:
        """
        处理文本块列表

        Args:
            blocks: 文本块列表，每个块包含text, page_num, block_idx

        Returns:
            识别的人物列表
        """
        self.persons = []

        for block in blocks:
            text = block.get('text', '')
            page_num = block.get('page_num')
            block_idx = block.get('block_idx')

            person = self.extract_person_from_block(text, page_num, block_idx)
            if person and (person.name or person.work_experiences):
                self.persons.append(person)

        return self.persons

    def sort_work_experiences_by_date(self) -> None:
        """
        按时间排序所有人物的工作经历
        """
        for person in self.persons:
            if person.work_experiences:
                # 按开始时间排序
                person.work_experiences.sort(
                    key=lambda x: x.get('start') or (9999, 12, 31)
                )

    def get_persons(self) -> List[PersonEntity]:
        """获取识别的人物列表"""
        return self.persons

    def to_dict(self) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        result = []
        for person in self.persons:
            result.append({
                'name': person.name,
                'original_text': person.original_text,
                'hometown': person.hometown,
                'education': person.education,
                'work_experiences': person.work_experiences,
                'photo_area': person.photo_area,
                'page_number': person.page_number,
                'block_index': person.block_index,
            })
        return result

    def _quality_flags(
        self,
        blocks: List[Dict[str, Any]],
        persons: List[PersonEntity],
    ) -> List[str]:
        flags: List[str] = []
        if not blocks:
            flags.append("no_text_blocks")
        if blocks and not persons:
            flags.append("no_biography_entities")
        if any(not str(block.get("text", "")).strip() for block in (blocks or [])):
            flags.append("empty_text_blocks")
        if any(not person.name for person in persons):
            flags.append("person_missing_name")
        if any(not person.work_experiences for person in persons):
            flags.append("person_missing_work_experiences")
        return sorted(set(flags))

    def _estimate_confidence(self, person_count: int, quality_flags: List[str]) -> float:
        confidence = 0.45
        if person_count:
            confidence += 0.35
        confidence -= min(0.35, len(set(quality_flags)) * 0.07)
        return round(max(0.1, min(confidence, 0.95)), 2)


def extract_biographical_entities(
    text_blocks: List[Dict[str, Any]]
) -> List[PersonEntity]:
    """
    便捷函数：从文本块中提取人物传记实体

    Args:
        text_blocks: 文本块列表 [{text, page_num, block_idx}, ...]

    Returns:
        人物实体列表
    """
    ner = BiographicalNER()
    persons = ner.process_text_blocks(text_blocks)
    ner.sort_work_experiences_by_date()
    return persons


def extract_biographical_entities_package(text_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience function returning the package contract."""
    return BiographicalNER().process_text_blocks_package(text_blocks)


if __name__ == "__main__":
    # 测试代码
    test_text = """
    鈴木梅四郎

    本籍：東京府豊島郡巣鴨町字上富士見前三十二番戸

    学歴：東京帝国大学経済学部卒業

    昭和5年 満鉄調査部
    昭和10年 南満洲鉄道株式会社調査部部長
    昭和15年 満炭理事
    """

    ner = BiographicalNER()
    person = ner.extract_person_from_block(test_text, 1, 0)

    if person:
        print(f"姓名: {person.name}")
        print(f"本籍: {person.hometown}")
        print(f"学历: {person.education}")
        print(f"工作经历: {person.work_experiences}")
