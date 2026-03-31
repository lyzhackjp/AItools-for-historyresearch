"""
NDL OCR结果处理模块

负责处理和清洗NDL OCR-Lite的输出结果
支持文本清洗、结构调整、数据结构化等功能
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class TextCleaningConfig:
    """文本清洗配置"""
    remove_extra_spaces: bool = True
    normalize_unicode: bool = True
    fix_common_errors: bool = True
    remove_page_numbers: bool = True
    preserve_line_breaks: bool = True
    clean_special_chars: bool = False


class NDLOCRResultProcessor:
    """
    NDL OCR结果处理器

    专门用于处理NDL OCR-Lite的输出
    提供文本清洗、结构调整、数据结构化等功能
    """

    def __init__(self, config: Optional[TextCleaningConfig] = None):
        """
        初始化结果处理器

        Args:
            config: 文本清洗配置
        """
        self.config = config or TextCleaningConfig()
        self.cleaning_stats = {
            'spaces_removed': 0,
            'chars_cleaned': 0,
            'lines_processed': 0
        }

    def process_result(self, ocr_result) -> Dict[str, Any]:
        """
        处理NDL OCR结果

        Args:
            ocr_result: NDLOCRLiteResult对象

        Returns:
            dict: 处理后的结构化数据
        """
        if not ocr_result.success:
            return {
                'success': False,
                'error': ocr_result.error,
                'processed_text': '',
                'structured_data': {}
            }

        processed_text = self.clean_text(ocr_result.text)

        structured_data = self.extract_structure(ocr_result)

        cleaned_pages = []
        for page in ocr_result.pages:
            cleaned_page = {
                'page_number': self._extract_page_number(page['filename']),
                'original_text': page['text'],
                'cleaned_text': self.clean_text(page['text']),
                'word_count': len(page['text'].split()),
                'char_count': len(page['text'])
            }
            cleaned_pages.append(cleaned_page)

        return {
            'success': True,
            'processed_text': processed_text,
            'structured_data': structured_data,
            'pages': cleaned_pages,
            'statistics': {
                'total_pages': len(cleaned_pages),
                'total_words': sum(p['word_count'] for p in cleaned_pages),
                'total_chars': sum(p['char_count'] for p in cleaned_pages),
                'processing_time': ocr_result.processing_time,
                'cleaning_stats': self.cleaning_stats
            },
            'metadata': {
                'output_dir': ocr_result.output_dir,
                'visualization_available': len(ocr_result.visualization_paths) > 0,
                'visualization_count': len(ocr_result.visualization_paths)
            }
        }

    def clean_text(self, text: str) -> str:
        """
        清洗文本内容

        Args:
            text: 原始文本

        Returns:
            str: 清洗后的文本
        """
        cleaned = text

        if self.config.normalize_unicode:
            cleaned = self._normalize_unicode(cleaned)

        if self.config.remove_extra_spaces:
            cleaned = self._remove_extra_spaces(cleaned)

        if self.config.fix_common_errors:
            cleaned = self._fix_common_ocr_errors(cleaned)

        if self.config.remove_page_numbers:
            cleaned = self._remove_page_numbers(cleaned)

        if self.config.clean_special_chars:
            cleaned = self._clean_special_characters(cleaned)

        return cleaned

    def _normalize_unicode(self, text: str) -> str:
        """Unicode规范化"""
        text = text.replace('\u3000', ' ')
        text = text.replace('\u00a0', ' ')
        text = text.replace('\u200b', '')
        text = text.replace('\ufeff', '')
        return text

    def _remove_extra_spaces(self, text: str) -> str:
        """移除多余空格"""
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            line = re.sub(r'[ \t]+', ' ', line)
            line = line.strip()
            cleaned_lines.append(line)
            self.cleaning_stats['spaces_removed'] += len(line) - len(line.strip())

        if self.config.preserve_line_breaks:
            return '\n'.join(cleaned_lines)
        else:
            return ' '.join(cleaned_lines)

    def _fix_common_ocr_errors(self, text: str) -> str:
        """修复常见OCR错误"""
        common_corrections = {
            'ヱ': 'エ',
            'ヰ': 'イ',
            'ヱ': 'エ',
            'ヶ': 'か',
            'ゐ': 'い',
            '爲': '為',
            '武蔵': '武藏',
            ' всё ': ' ',
        }

        for wrong, correct in common_corrections.items():
            count = text.count(wrong)
            text = text.replace(wrong, correct)
            self.cleaning_stats['chars_cleaned'] += count

        text = re.sub(r'([。.!:?)])([^\s\d])', r'\1 \2', text)
        text = re.sub(r'([。.!:?)])\s+([A-Za-z])', r'\1 \2', text)

        return text

    def _remove_page_numbers(self, text: str) -> str:
        """移除页码"""
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            line = re.sub(r'^\s*\d+\s*$', '', line)
            line = re.sub(r'^[-—]\s*\d+\s*[-—]$', '', line)
            line = re.sub(r'^\s*Page\s*\d+\s*$', '', line, flags=re.IGNORECASE)

            if line.strip():
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def _clean_special_characters(self, text: str) -> str:
        """清理特殊字符"""
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        return text

    def extract_structure(self, ocr_result) -> Dict[str, Any]:
        """
        提取文本结构

        Args:
            ocr_result: NDLOCRLiteResult对象

        Returns:
            dict: 结构化数据
        """
        structure = {
            'paragraphs': [],
            'tables': [],
            'lists': [],
            'key_value_pairs': {},
            'metadata': {}
        }

        text = ocr_result.text
        lines = text.split('\n')

        paragraphs = self._extract_paragraphs(lines)
        structure['paragraphs'] = paragraphs

        tables = self._extract_tables(lines)
        structure['tables'] = tables

        lists_items = self._extract_lists(lines)
        structure['lists'] = lists_items

        kv_pairs = self._extract_key_value_pairs('\n'.join(paragraphs))
        structure['key_value_pairs'] = kv_pairs

        return structure

    def _extract_paragraphs(self, lines: List[str]) -> List[str]:
        """提取段落"""
        paragraphs = []
        current_para = []

        for line in lines:
            line = line.strip()
            if not line:
                if current_para:
                    para_text = ' '.join(current_para)
                    if para_text.strip():
                        paragraphs.append(para_text)
                    current_para = []
            else:
                current_para.append(line)

        if current_para:
            para_text = ' '.join(current_para)
            if para_text.strip():
                paragraphs.append(para_text)

        return paragraphs

    def _extract_tables(self, lines: List[str]) -> List[List[List[str]]]:
        """提取表格数据"""
        tables = []
        current_table = []
        in_table = False

        for line in lines:
            line = line.strip()

            if re.match(r'^[\|＋┌┬┌├┼┼│]', line):
                in_table = True
                continue

            if in_table and (line.startswith('|') or '│' in line):
                cells = re.split(r'\||│', line)
                cells = [cell.strip() for cell in cells if cell.strip()]

                if cells:
                    current_table.append(cells)
            else:
                if current_table:
                    if len(current_table) > 1:
                        tables.append(current_table)
                    current_table = []
                in_table = False

        if current_table and len(current_table) > 1:
            tables.append(current_table)

        return tables

    def _extract_lists(self, lines: List[str]) -> List[Dict[str, Any]]:
        """提取列表项"""
        lists = []
        current_list = None

        list_patterns = [
            r'^(\d+)[.、.]',
            r'^([①②③④⑤⑥⑦⑧⑨⑩])',
            r'^([A-Za-z])[.、.]',
            r'^[-•*][\s]'
        ]

        for line in lines:
            line = line.strip()
            matched = False

            for pattern in list_patterns:
                match = re.match(pattern, line)
                if match:
                    if current_list is None:
                        current_list = {'items': [], 'type': 'ordered' if match.group(1).isdigit() or match.group(1).isalpha() else 'bullet'}

                    item_text = re.sub(pattern, '', line).strip()
                    current_list['items'].append(item_text)
                    matched = True
                    break

            if not matched and current_list:
                lists.append(current_list)
                current_list = None

        if current_list:
            lists.append(current_list)

        return lists

    def _extract_key_value_pairs(self, text: str) -> Dict[str, str]:
        """提取键值对"""
        pairs = {}

        patterns = [
            r'([^：:\s]+?)[:：]\s*([^\n]+?)(?=\n[^：:\s]+?[:：]|$)',
            r'([^=\n]+?)\s*=\s*([^\n]+?)(?=\n[^=\n]+?\s*=|$)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                key = match.group(1).strip()
                value = match.group(2).strip()

                if len(key) > 1 and len(value) > 0:
                    pairs[key] = value

        return pairs

    def _extract_page_number(self, filename: str) -> int:
        """从文件名提取页码"""
        match = re.search(r'(\d+)', filename)
        return int(match.group(1)) if match else 0

    def to_json(self, data: Dict[str, Any], pretty: bool = True) -> str:
        """
        导出为JSON格式

        Args:
            data: 处理后的数据
            pretty: 是否格式化输出

        Returns:
            str: JSON字符串
        """
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False)

    def to_structured_dict(self, ocr_result) -> Dict[str, Any]:
        """
        转换为标准结构化字典格式

        Args:
            ocr_result: NDLOCRLiteResult对象

        Returns:
            dict: 标准化的结构化数据
        """
        processed = self.process_result(ocr_result)

        return {
            'ocr_method': 'ndlocr-lite',
            'success': processed['success'],
            'text': processed['processed_text'],
            'metadata': {
                'page_count': processed['statistics']['total_pages'],
                'word_count': processed['statistics']['total_words'],
                'char_count': processed['statistics']['total_chars'],
                'processing_time': processed['statistics']['processing_time'],
                'has_visualization': processed['metadata']['visualization_available']
            },
            'pages': [
                {
                    'number': page['page_number'],
                    'text': page['cleaned_text'],
                    'word_count': page['word_count']
                }
                for page in processed['pages']
            ],
            'structure': processed['structured_data'],
            'raw_result': ocr_result.to_dict()
        }

    def batch_process(self, ocr_results: List) -> List[Dict[str, Any]]:
        """
        批量处理多个OCR结果

        Args:
            ocr_results: OCR结果列表

        Returns:
            list: 处理结果列表
        """
        return [self.process_result(result) for result in ocr_results]


def create_result_processor(
    remove_extra_spaces: bool = True,
    normalize_unicode: bool = True,
    fix_common_errors: bool = True,
    remove_page_numbers: bool = True
) -> NDLOCRResultProcessor:
    """
    工厂函数 - 创建结果处理器实例

    Args:
        remove_extra_spaces: 移除多余空格
        normalize_unicode: Unicode规范化
        fix_common_errors: 修复常见错误
        remove_page_numbers: 移除页码

    Returns:
        NDLOCRResultProcessor: 结果处理器实例
    """
    config = TextCleaningConfig(
        remove_extra_spaces=remove_extra_spaces,
        normalize_unicode=normalize_unicode,
        fix_common_errors=fix_common_errors,
        remove_page_numbers=remove_page_numbers
    )
    return NDLOCRResultProcessor(config)
