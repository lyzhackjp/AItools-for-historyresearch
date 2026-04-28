import json
import csv
import re
from typing import Dict, Any, List, Optional
import io


class DataStructurer:
    """数据清洗与结构化输出模块"""

    def __init__(self):
        """初始化数据结构化处理器"""
        self.cleaning_rules = {
            'remove_extra_whitespace': True,
            'remove_special_chars': False,
            'normalize_unicode': True
        }

    def clean_text(self, text: str, rules: Optional[Dict[str, bool]] = None) -> str:
        """
        清洗文本数据

        Args:
            text: 待清洗的文本
            rules: 清洗规则

        Returns:
            str: 清洗后的文本
        """
        rules = rules or self.cleaning_rules
        cleaned = text

        if rules.get('remove_extra_whitespace'):
            cleaned = re.sub(r'\s+', ' ', cleaned)
            cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)

        if rules.get('normalize_unicode'):
            cleaned = cleaned.replace('\u3000', ' ')

        if rules.get('remove_special_chars'):
            cleaned = re.sub(r'[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', '', cleaned)

        return cleaned.strip()

    def extract_tables(self, text: str) -> List[List[str]]:
        """
        从文本中提取表格数据

        Args:
            text: 包含表格的文本

        Returns:
            list: 表格数据列表
        """
        lines = text.split('\n')
        tables = []
        current_table = []
        in_table = False

        for line in lines:
            line = line.strip()
            if not line:
                if in_table and current_table:
                    tables.append(current_table)
                    current_table = []
                in_table = False
                continue

            cells = re.split(r'\t+|,{2,}|，{2,}', line)

            if len(cells) > 1:
                in_table = True
                current_table.append([cell.strip() for cell in cells])
            else:
                if in_table and current_table:
                    tables.append(current_table)
                    current_table = []
                in_table = False

        if current_table:
            tables.append(current_table)

        return tables

    def extract_key_values(self, text: str, separator: str = '：') -> Dict[str, str]:
        """
        从文本中提取键值对

        Args:
            text: 包含键值对的文本
            separator: 分隔符

        Returns:
            dict: 键值对字典
        """
        key_values = {}
        lines = text.split('\n')

        for line in lines:
            if separator in line:
                parts = line.split(separator, 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    if key:
                        key_values[key] = value

        return key_values

    def extract_timeline(self, text: str) -> List[Dict[str, str]]:
        """
        从文本中提取时间线信息

        Args:
            text: 包含时间线信息的文本

        Returns:
            list: 时间线事件列表
        """
        timeline = []

        year_pattern = r'(\d{4})[年\-]?(\d{1,2})?[月\-]?(\d{1,2})?[日]?'
        patterns = [
            r'(\d{4}[年\-]\d{1,2}[月\-]?\d{0,2}[日]?)[：:、](.+)',
            r'(.*?)(\d{4})[年](.*)',
            r'(.*?)(\d{1,2})[/年](\d{1,2})[日]?(.*)'
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    date_str = ''.join([g for g in groups[:-1] if g])
                    event = groups[-1] if groups[-1] else groups[0]

                    if date_str and event:
                        timeline.append({
                            'date': date_str.strip(),
                            'event': event.strip()
                        })
                        break

        if not timeline:
            year_matches = re.findall(year_pattern, text)
            for match in year_matches:
                year = match[0]
                month = match[1] if len(match) > 1 and match[1] else ''
                day = match[2] if len(match) > 2 and match[2] else ''

                date_str = year
                if month:
                    date_str += f"-{month}"
                if day:
                    date_str += f"-{day}"

                timeline.append({
                    'date': date_str,
                    'event': text[text.find(year):text.find(year) + 50] if year in text else ''
                })

        return timeline

    def structure_text(self, text: str, structure_type: str = 'general') -> Dict[str, Any]:
        """
        根据类型结构化文本

        Args:
            text: 待结构化的文本
            structure_type: 结构化类型 ('general', 'table', 'key_value', 'timeline')

        Returns:
            dict: 结构化结果
        """
        cleaned_text = self.clean_text(text)

        if structure_type == 'table':
            tables = self.extract_tables(cleaned_text)
            return {
                'type': 'table',
                'data': tables,
                'table_count': len(tables)
            }

        elif structure_type == 'key_value':
            key_values = self.extract_key_values(cleaned_text)
            return {
                'type': 'key_value',
                'data': key_values,
                'key_count': len(key_values)
            }

        elif structure_type == 'timeline':
            timeline = self.extract_timeline(cleaned_text)
            return {
                'type': 'timeline',
                'data': timeline,
                'event_count': len(timeline)
            }

        else:
            paragraphs = [p.strip() for p in cleaned_text.split('\n\n') if p.strip()]
            return {
                'type': 'general',
                'data': paragraphs,
                'paragraph_count': len(paragraphs)
            }

    def to_json(self, data: Any, pretty: bool = True) -> str:
        """
        转换为JSON格式

        Args:
            data: 待转换的数据
            pretty: 是否格式化输出

        Returns:
            str: JSON字符串
        """
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False)

    def to_csv(self, data: List[Dict[str, Any]], output_path: Optional[str] = None) -> str:
        """
        转换为CSV格式

        Args:
            data: 列表数据
            output_path: 输出文件路径（可选）

        Returns:
            str: CSV字符串
        """
        if not data:
            return ''

        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            fieldnames = []
            for row in data:
                for key in row.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fieldnames)

            writer.writeheader()
            for row in data:
                writer.writerow(row)

            csv_content = output.getvalue()

            if output_path:
                with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                    f.write(csv_content)

            return csv_content

        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            output = io.StringIO()
            writer = csv.writer(output)

            for row in data:
                writer.writerow(row)

            csv_content = output.getvalue()

            if output_path:
                with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                    f.write(csv_content)

            return csv_content

        return ''

    def validate_schema(
        self,
        record: Dict[str, Any],
        required_fields: Optional[List[str]] = None,
        optional_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Validate one lightweight structured record."""
        required_fields = required_fields or []
        optional_fields = optional_fields or []
        missing = [field for field in required_fields if record.get(field) in (None, '')]
        known_fields = set(required_fields) | set(optional_fields)
        extra = [field for field in record.keys() if known_fields and field not in known_fields]
        confidence = 1.0 if not required_fields else (len(required_fields) - len(missing)) / len(required_fields)
        return {
            'is_valid': not missing,
            'missing_fields': missing,
            'extra_fields': extra,
            'confidence': round(confidence, 2),
            'needs_review': bool(missing),
        }

    def normalize_record(
        self,
        record: Dict[str, Any],
        schema: Optional[Dict[str, Any]] = None,
        source_type: str = 'generic',
    ) -> Dict[str, Any]:
        """Normalize one OCR/NER/citation-like record into a shared envelope."""
        schema = schema or {}
        required_fields = list(schema.get('required', []))
        optional_fields = list(schema.get('optional', []))
        cleaned: Dict[str, Any] = {}

        for key, value in dict(record or {}).items():
            if isinstance(value, str):
                cleaned[key] = self.clean_text(value)
            else:
                cleaned[key] = value

        validation = self.validate_schema(cleaned, required_fields, optional_fields)
        return {
            'type': source_type,
            'data': cleaned,
            'validation': validation,
            'confidence': validation['confidence'],
            'needs_review': validation['needs_review'],
            'backend': schema.get('backend', 'script'),
            'provider': schema.get('provider', 'data_structurer'),
            'model': schema.get('model'),
        }

    def normalize_records(
        self,
        records: List[Dict[str, Any]],
        schema: Optional[Dict[str, Any]] = None,
        source_type: str = 'generic',
    ) -> List[Dict[str, Any]]:
        """Normalize a batch of records with the same lightweight schema."""
        return [
            self.normalize_record(record, schema=schema, source_type=source_type)
            for record in records
        ]

    def build_export_payload(
        self,
        records: List[Dict[str, Any]],
        schema: Optional[Dict[str, Any]] = None,
        source_type: str = 'generic',
    ) -> Dict[str, Any]:
        """Build a workflow-friendly export payload from structured records."""
        normalized = self.normalize_records(records, schema=schema, source_type=source_type)
        return {
            'type': source_type,
            'records': normalized,
            'record_count': len(normalized),
            'records_needing_review': sum(1 for item in normalized if item.get('needs_review')),
            'backend': 'script',
            'provider': 'data_structurer',
            'model': None,
            'confidence': round(
                sum(item.get('confidence', 0.0) for item in normalized) / len(normalized),
                2
            ) if normalized else 0.0,
            'needs_review': any(item.get('needs_review') for item in normalized),
        }

    def export_structured_data(self, data: Dict[str, Any],
                              format: str = 'json',
                              output_path: Optional[str] = None) -> str:
        """
        导出结构化数据

        Args:
            data: 结构化数据
            format: 输出格式 ('json', 'csv')
            output_path: 输出文件路径

        Returns:
            str: 格式化后的数据字符串
        """
        if format == 'json':
            result = self.to_json(data)
        elif format == 'csv':
            if isinstance(data, dict) and 'data' in data:
                result = self.to_csv(data['data'], output_path)
            else:
                result = self.to_csv(data, output_path)
        else:
            result = str(data)

        if output_path and format != 'csv':
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result)

        return result

    def merge_ocr_results(self, ocr_results: List[Dict[str, Any]],
                         remove_duplicates: bool = True) -> str:
        """
        合并多个OCR结果

        Args:
            ocr_results: OCR结果列表
            remove_duplicates: 是否去除重复内容

        Returns:
            str: 合并后的文本
        """
        texts = []

        for result in ocr_results:
            if result.get('success') and result.get('text'):
                texts.append(result['text'])

        merged = '\n\n'.join(texts)

        if remove_duplicates:
            lines = merged.split('\n')
            unique_lines = []
            seen = set()

            for line in lines:
                normalized = line.strip().lower()
                if normalized and normalized not in seen:
                    unique_lines.append(line)
                    seen.add(normalized)

            merged = '\n'.join(unique_lines)

        return merged


def create_data_structurer() -> DataStructurer:
    """
    工厂函数 - 创建数据结构化处理器实例

    Returns:
        DataStructurer: 数据结构化处理器实例
    """
    return DataStructurer()
