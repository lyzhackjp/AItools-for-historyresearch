"""
引用规范化处理器模块

实现学术引用的规范化处理和批量管理
支持多种引用格式的识别、转换和验证

根据WORKFLOW_DIAGRAM.md中的6.1引用格式转换流程优化：
输入引用列表 → parse_citation解析 → 识别格式类型 → 应用正则模式 → validate_fields验证 → 规范化字段 → convert_format转换 → 输出目标格式

核心功能：
- 格式识别与转换：多格式支持（Chicago, APA, MLA, GB/T 7714等）
- 来源规范化：统一来源格式、版本信息补全
- 引用完整性检查：缺失字段检测、格式错误纠正
- 重复引用识别：自动去重
- 智能格式检测：根据WORKFLOW流程自动识别引用格式
- LLM辅助识别：整合大语言模型辅助复杂引用解析
- 外部资料搜集：支持学术数据库查询补全元数据

使用方法：
    from modules.citation_normalizer import CitationNormalizer
    
    normalizer = CitationNormalizer(style='gb7714')
    normalized = normalizer.normalize(citations)
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple, Callable
from pathlib import Path
from urllib.parse import urlparse
import hashlib

try:
    from prompts.prompt_loader import PromptLoader, PromptTemplate
    PROMPT_LOADER_AVAILABLE = True
except ImportError:
    PROMPT_LOADER_AVAILABLE = False

try:
    from modules.llm_client import create_llm_client
    LLM_CLIENT_AVAILABLE = True
except ImportError:
    LLM_CLIENT_AVAILABLE = False


class CitationNormalizer:
    """引用规范化处理器 - 根据WORKFLOW_DIAGRAM.md流程优化"""
    
    SUPPORTED_STYLES = ['chicago', 'apa', 'mla', 'gb7714', 'ieee', 'harvard']
    
    FIELD_VALIDATION_RULES = {
        'year': {
            'type': 'int',
            'min': 1900,
            'max': 2030,
            'warn_future': True
        },
        'doi': {
            'type': 'regex',
            'pattern': r'^10\.\d{4,}/[^\s]+$',
            'normalize': True
        },
        'pages': {
            'type': 'pages_range',
            'normalize': True
        },
        'volume': {
            'type': 'positive_int',
            'allow_zero': False
        }
    }
    
    FORMAT_TEMPLATES = {
        'chicago': {
            'article': '{author}. "{title}" [J]. {journal}, {year}, {volume}({issue}): {pages}',
            'book': '{author}. {title} [M]. {publisher}, {year}.',
            'conference': '{author}. "{title}" [C]. {conference_name}, {year}, pp. {pages}',
            'dissertation': '{author}. {title} [D]. {institution}, {year}.',
            'electronic': '{author}. "{title}" [EB/OL]. {journal}, {year}. Available at: {url}'
        },
        'apa': {
            'article': '{author} ({year}). {title}. {journal}, {volume}({issue}), {pages}.',
            'book': '{author} ({year}). {title}. {publisher}.',
            'conference': '{author} ({year}). {title}. In {conference_name} (pp. {pages}).',
            'dissertation': '{author} ({year}). {title} [Doctoral dissertation, {institution}].',
            'electronic': '{author} ({year}). {title}. {journal}. Retrieved from {url}'
        },
        'mla': {
            'article': '{author}. "{title}" [J]. {journal}, vol. {volume}, no. {issue}, {year}, pp. {pages}.',
            'book': '{author}. {title} [M]. {publisher}, {year}.',
            'conference': '{author}. "{title}" [C]. {conference_name}, {year}, pp. {pages}.',
            'dissertation': '{author}. {title} [D]. {institution}, {year}.',
            'electronic': '{author}. "{title}" [EB/OL]. {journal}, {year}, pp. {pages}. Accessed: {access_date}'
        },
        'gb7714': {
            'article': '[{index}] {author}. {title} [J]. {journal}, {year}, {volume}({issue}): {pages}.',
            'book': '[{index}] {author}. {title} [M]. {publisher}, {year}.',
            'conference': '[{index}] {author}. {title} [C]. {conference_name}, {year}.',
            'dissertation': '[{index}] {author}. {title} [D]. {institution}, {year}.',
            'electronic': '[{index}] {author}. {title} [EB/OL]. {journal}, {year}. Available at: {url}'
        },
        'ieee': {
            'article': '[{index}] {author}, "{title}," {journal}, vol. {volume}, no. {issue}, pp. {pages}, {year}.',
            'book': '[{index}] {author}, {title}. {publisher}, {year}.',
            'conference': '[{index}] {author}, "{title}," in {conference_name}, {year}, pp. {pages}.',
            'dissertation': '[{index}] {author}, "{title}," {degree}, {institution}, {year}.',
            'electronic': '[{index}] {author}, "{title}," {journal}, {year}. [Online]. Available: {url}'
        },
        'harvard': {
            'article': '{author} ({year}) \'{title}\', {journal}, {volume}({issue}), pp. {pages}.',
            'book': '{author} ({year}) {title}. {publisher}.',
            'conference': '{author} ({year}) \'{title}\', {conference_name}, pp. {pages}.',
            'dissertation': '{author} ({year}) {title}. {institution}.',
            'electronic': '{author} ({year}) {title}. {journal}. Available at: {url}'
        }
    }
    
    STYLE_PATTERNS = {
        'chicago': {
            'book': r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\.\s*([^\.]+)\s*\[M\]\.\s*([^\:]+):\s*([^\,]+),\s*(\d{4})',
            'article': r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\.\s*"([^"]+)"\s*\[J\]\.\s*([^\.]+),\s*(\d{4}),?\s*(?:vol\.?\s*(\d+),?\s*)?(?:no\.?\s*(\d+),?\s*)?(?:pp\.?\s*(\d+(?:-\d+)?))?'
        },
        'apa': {
            'book': r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\((\d{4})\)\.\s*([^\.]+)\.\s*([^\:]+):\s*([^\.]+)',
            'article': r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\((\d{4})\)\.\s*([^"]+)"?\s*\.?\s*([^\.]+),\s*(\d+),\s*(\d+(?:-\d+)?)'
        },
        'mla': {
            'book': r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\.\s*([^\.]+)\.\s*([^\:]+):\s*([^\,]+),\s*(\d{4})',
            'article': r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\.\s*"([^"]+)"\s*([^\.]+),\s*vol\.\s*(\d+),\s*(\d{4}),\s*pp\.\s*(\d+(?:-\d+)?)'
        },
        'gb7714': {
            'book': r'\[序号\]\s*([^\[]+)\s*\[M\]\s*\.\s*([^\:]+):\s*([^\,]+),\s*(\d{4})',
            'article': r'\[序号\]\s*([^\[]+)\s*\[J\]\s*\.\s*([^\,]+),\s*(\d{4}),?\s*(\d+)?,?\s*(\d+-\d+)?'
        },
        'ieee': {
            'book': r'\[?\d+)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*([^\,]+),\s*[^\,]+,\s*(\d{4})',
            'article': r'\[?\d+)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*"([^"]+)",\s*([^\,]+),\s*vol\.\s*(\d+),\s*pp\.\s*(\d+(?:-\d+)?),\s*(\d{4})'
        },
        'harvard': {
            'book': r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\((\d{4})\)\s*([^\.]+)\.\s*([^\:]+):\s*([^\.]+)',
            'article': r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\((\d{4})\)\s*\'([^\']+)\'\s*([^\.]+),\s*(\d+)\s*\(([^)]+)\),\s*pp\.\s*(\d+(?:-\d+)?)'
        }
    }
    
    FORMAT_DETECTION_PATTERNS = {
        'chicago': [
            r'\.\s*"[^"]+"\s*\[J\]\.',
            r'\.\s*([^\.]+)\s*\[M\]\.',
        ],
        'apa': [
            r'\s*\((\d{4})\)\.',
            r'\.\s*([^\.]+)\.\s*[A-Z][a-z]+:\s*[A-Z]',
        ],
        'mla': [
            r'\.\s*"[^"]+"\s*[^\.]+,\s*vol\.',
            r'\.\s*([^\.]+)\.\s*[^\:]+:\s*[^\,]+,\s*(\d{4})',
        ],
        'gb7714': [
            r'\[序号\]',
            r'\s*\[J\]\s*\.',
            r'\s*\[M\]\s*\.',
        ],
        'ieee': [
            r'\[?\d+\]?',
            r',\s*vol\.\s*\d+',
            r',\s*pp\.\s*\d+',
        ],
        'harvard': [
            r'\s*\((\d{4})\)\s*\'[^\']+\'',
            r'\s*\((\d{4})\)\s*[^\.]+\.',
        ]
    }
    
    def __init__(self, style: str = 'chicago', test_mode: bool = True, use_llm: bool = False):
        """
        初始化引用规范化处理器
        
        Args:
            style: 目标引用格式 ('chicago', 'apa', 'mla', 'gb7714', 'ieee', 'harvard')
            test_mode: 测试模式标志
            use_llm: 是否使用LLM辅助识别（整合外部资料搜集）
        """
        if style not in self.SUPPORTED_STYLES:
            raise ValueError(f"不支持的引用格式: {style}。支持: {self.SUPPORTED_STYLES}")
        
        self.style = style
        self.test_mode = test_mode
        self.use_llm = use_llm and LLM_CLIENT_AVAILABLE
        self._prompt_loader = None
        self._prompt_template = None
        self.llm_client = None
        
        self.field_normalizers = {
            'author': self._normalize_author,
            'title': self._normalize_title,
            'year': self._normalize_year,
            'journal': self._normalize_journal,
            'volume': self._normalize_volume,
            'pages': self._normalize_pages,
            'doi': self._normalize_doi,
            'url': self._normalize_url
        }
    
    def _get_prompt_loader(self):
        """获取提示词加载器"""
        if self._prompt_loader is None and PROMPT_LOADER_AVAILABLE:
            self._prompt_loader = PromptLoader()
        return self._prompt_loader
    
    def _get_prompt_template(self):
        """获取提示词模板"""
        if self._prompt_template is None:
            loader = self._get_prompt_loader()
            self._prompt_template = PromptTemplate(loader) if loader else None
        return self._prompt_template
    
    def _init_llm_client(self):
        """初始化LLM客户端用于辅助识别"""
        if self.llm_client is None and self.use_llm:
            try:
                self.llm_client = create_llm_client()
            except Exception as e:
                print(f"初始化LLM客户端失败: {e}")
                self.use_llm = False
        return self.llm_client
    
    def detect_format(self, citation: str) -> str:
        """
        根据WORKFLOW流程自动识别引用格式（节点D：识别格式类型）
        
        Args:
            citation: 原始引用字符串
            
        Returns:
            str: 识别的格式类型 ('chicago', 'apa', 'mla', 'gb7714', 'ieee', 'harvard', 'unknown')
        """
        scores = {style: 0 for style in self.SUPPORTED_STYLES}
        
        for style, patterns in self.FORMAT_DETECTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, citation):
                    scores[style] += 1
        
        max_score = max(scores.values())
        if max_score == 0:
            return 'unknown'
        
        detected_styles = [style for style, score in scores.items() if score == max_score]
        
        return detected_styles[0]
    
    def normalize(self, citations: List[str], target_style: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        规范化引用列表 - 遵循WORKFLOW 6.1流程
        
        工作流程：输入引用列表 → parse_citation解析 → 识别格式类型 → 
                  应用正则模式 → validate_fields验证 → 规范化字段
        
        Args:
            citations: 原始引用列表
            target_style: 目标格式，默认使用初始化时的格式
            
        Returns:
            List[Dict]: 规范化后的引用字典列表
        """
        target_style = target_style or self.style
        
        normalized = []
        
        for citation in citations:
            parsed = self._parse_citation(citation)
            
            if parsed:
                validated = self._validate_fields(parsed)
                normalized.append(validated)
            else:
                normalized.append({
                    'original': citation,
                    'parsed': False,
                    'fields': {},
                    'errors': ['无法解析引用格式']
                })
        
        return normalized
    
    def convert_format(self, citation: Dict[str, Any], 
                     target_style: str,
                     use_template: bool = True) -> str:
        """
        将引用转换为目标格式 - 遵循WORKFLOW节点K：convert_format转换
        
        优化说明：支持使用模板系统进行格式化，提高输出格式的一致性和可维护性
        
        Args:
            citation: 引用字典
            target_style: 目标格式
            use_template: 是否使用模板系统（默认True）
            
        Returns:
            str: 格式化后的引用字符串
        """
        if target_style not in self.SUPPORTED_STYLES:
            raise ValueError(f"不支持的引用格式: {target_style}")
        
        if not citation.get('parsed'):
            return citation.get('original', '')
        
        fields = citation.get('fields', {})
        
        if use_template:
            formatted = self._format_with_template(fields, target_style)
            if formatted:
                return formatted
        
        formatters = {
            'chicago': self._format_chicago,
            'apa': self._format_apa,
            'mla': self._format_mla,
            'gb7714': self._format_gb7714,
            'ieee': self._format_ieee,
            'harvard': self._format_harvard
        }
        
        formatter = formatters.get(target_style, self._format_chicago)
        return formatter(fields)
    
    def _format_with_template(self, fields: Dict[str, Any], target_style: str) -> Optional[str]:
        """
        使用模板系统格式化引用 - 提升输出格式一致性
        
        Args:
            fields: 引用字段字典
            target_style: 目标格式
            
        Returns:
            Optional[str]: 格式化后的引用字符串，如果模板不可用则返回None
        """
        citation_type = fields.get('type', 'article')
        
        templates = self.FORMAT_TEMPLATES.get(target_style, {})
        template = templates.get(citation_type)
        
        if not template:
            template = templates.get('article')
        
        if not template:
            return None
        
        try:
            formatted_fields = {}
            for key, value in fields.items():
                if value is None or value == '':
                    formatted_fields[key] = ''
                else:
                    formatted_fields[key] = str(value)
            
            for key in ['issue', 'pages', 'volume']:
                if key not in formatted_fields or not formatted_fields[key]:
                    formatted_fields[key] = ''
            
            formatted = template.format(**formatted_fields)
            
            formatted = re.sub(r'\s+', ' ', formatted)
            formatted = re.sub(r',\s*,', ',', formatted)
            formatted = re.sub(r'\s+\.', '.', formatted)
            formatted = re.sub(r'\.\s+', '. ', formatted)
            formatted = re.sub(r'\(\s*\)', '', formatted)
            formatted = re.sub(r':\s*:', ':', formatted)
            
            return formatted.strip()
            
        except (KeyError, ValueError) as e:
            print(f"模板格式化失败: {e}")
            return None
    
    def validate(self, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        验证引用列表的完整性和正确性 - WORKFLOW节点I：validate_fields验证
        
        Args:
            citations: 规范化后的引用列表
            
        Returns:
            Dict: 验证报告
        """
        report = {
            'total': len(citations),
            'valid': 0,
            'invalid': 0,
            'warnings': [],
            'errors': [],
            'duplicates': [],
            'suggestions': []
        }
        
        for i, citation in enumerate(citations):
            if not citation.get('parsed'):
                report['invalid'] += 1
                report['errors'].append({
                    'index': i,
                    'message': citation.get('errors', ['Unknown error'])
                })
            else:
                report['valid'] += 1
                report['warnings'].extend(self._check_field_completeness(citation))
        
        duplicate_indices = self._find_duplicates(citations)
        if duplicate_indices:
            report['duplicates'] = duplicate_indices
            report['suggestions'].append('发现重复引用，建议去重')
        
        for field in ['author', 'title', 'year']:
            missing_count = sum(1 for c in citations 
                             if not c.get('parsed') or not c.get('fields', {}).get(field))
            if missing_count > 0:
                report['suggestions'].append(f'{missing_count}条引用缺少{field}字段')
        
        return report
    
    def normalize_fields(self, citation: Dict[str, Any]) -> Dict[str, Any]:
        """
        规范化字段 - WORKFLOW节点J：规范化字段
        
        应用字段规范化规则，确保所有字段符合标准格式
        
        Args:
            citation: 引用字典
            
        Returns:
            Dict[str, Any]: 规范化后的引用字典
        """
        if not citation.get('parsed'):
            return citation
        
        normalized_citation = citation.copy()
        fields = citation.get('fields', {})
        normalized_fields = {}
        
        for field_name, field_value in fields.items():
            if field_value is None:
                continue
            
            if field_name in self.field_normalizers:
                normalizer = self.field_normalizers[field_name]
                normalized_fields[field_name] = normalizer(field_value)
            else:
                normalized_fields[field_name] = field_value
        
        normalized_fields['type'] = fields.get('type', 'unknown')
        normalized_fields['detected_format'] = fields.get('detected_format', 'unknown')
        
        normalized_citation['fields'] = normalized_fields
        
        return normalized_citation
    
    def normalize_batch(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量规范化引用字段
        
        Args:
            citations: 引用列表
            
        Returns:
            List[Dict]: 规范化后的引用列表
        """
        return [self.normalize_fields(citation) for citation in citations]
    
    def deduplicate(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去除重复引用
        
        Args:
            citations: 引用列表
            
        Returns:
            List[Dict]: 去重后的引用列表
        """
        seen = set()
        unique_citations = []
        
        for citation in citations:
            if not citation.get('parsed'):
                unique_citations.append(citation)
                continue
            
            citation_hash = self._generate_citation_hash(citation)
            
            if citation_hash not in seen:
                seen.add(citation_hash)
                unique_citations.append(citation)
            else:
                print(f"发现重复引用: {citation.get('fields', {}).get('title', 'Unknown')}")
        
        return unique_citations
    
    def extract_metadata(self, citation: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取引用元数据
        
        Args:
            citation: 引用字典
            
        Returns:
            Dict: 元数据字典
        """
        if not citation.get('parsed'):
            return {}
        
        fields = citation.get('fields', {})
        
        metadata = {
            'type': fields.get('type', 'unknown'),
            'authors': self._parse_authors(fields.get('author', '')),
            'year': fields.get('year', ''),
            'title': fields.get('title', ''),
            'doi': fields.get('doi', ''),
            'url': fields.get('url', ''),
            'is_complete': self._is_complete(fields)
        }
        
        return metadata
    
    def _parse_citation(self, citation: str) -> Optional[Dict[str, Any]]:
        """
        解析单个引用 - 遵循WORKFLOW节点C和D：parse_citation解析 + 识别格式类型
        
        工作流程：
        1. C[parse_citation解析]
        2. D{识别格式类型} - Chicago/APA/GB7714/其他
        3. E/F/G/H[应用正则模式]
        4. 如果启用LLM，调用外部资料搜集进行辅助识别
        
        Args:
            citation: 原始引用字符串
            
        Returns:
            Optional[Dict]: 解析后的引用字段字典
        """
        citation = citation.strip()
        
        if not citation:
            return None
        
        detected_format = self.detect_format(citation)
        
        fields = {}
        fields['detected_format'] = detected_format
        
        if detected_format != 'unknown' and detected_format in self.STYLE_PATTERNS:
            fields.update(self._parse_with_format(citation, detected_format))
        else:
            fields.update(self._parse_generic(citation))
        
        if not fields.get('author') or not fields.get('title'):
            if self.use_llm:
                llm_fields = self._parse_with_llm(citation)
                if llm_fields:
                    fields.update(llm_fields)
        
        fields['type'] = self._detect_citation_type(citation)
        
        return fields if fields else None
    
    def _parse_with_format(self, citation: str, style: str) -> Dict[str, Any]:
        """
        根据识别的格式类型应用相应的正则表达式（WORKFLOW节点E/F/G/H：应用正则模式）
        
        Args:
            citation: 原始引用字符串
            style: 识别的格式类型
            
        Returns:
            Dict: 解析后的字段字典
        """
        fields = {}
        patterns = self.STYLE_PATTERNS.get(style, {})
        
        citation_type = self._detect_citation_type(citation)
        if citation_type in patterns:
            pattern = patterns[citation_type]
            match = re.search(pattern, citation)
            if match:
                groups = match.groups()
                if style == 'chicago':
                    if citation_type == 'book':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['title'] = groups[1] if len(groups) > 1 else None
                        fields['publisher'] = groups[2] if len(groups) > 2 else None
                        fields['year'] = groups[3] if len(groups) > 3 else None
                    elif citation_type == 'article':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['title'] = groups[1] if len(groups) > 1 else None
                        fields['journal'] = groups[2] if len(groups) > 2 else None
                        fields['year'] = groups[3] if len(groups) > 3 else None
                        fields['volume'] = groups[4] if len(groups) > 4 else None
                        fields['issue'] = groups[5] if len(groups) > 5 else None
                        fields['pages'] = groups[6] if len(groups) > 6 else None
                elif style == 'apa':
                    if citation_type == 'book':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['year'] = groups[1] if len(groups) > 1 else None
                        fields['title'] = groups[2] if len(groups) > 2 else None
                        fields['publisher'] = groups[3] if len(groups) > 3 else None
                    elif citation_type == 'article':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['year'] = groups[1] if len(groups) > 1 else None
                        fields['title'] = groups[2] if len(groups) > 2 else None
                        fields['journal'] = groups[3] if len(groups) > 3 else None
                        fields['volume'] = groups[4] if len(groups) > 4 else None
                        fields['pages'] = groups[5] if len(groups) > 5 else None
                elif style == 'mla':
                    if citation_type == 'book':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['title'] = groups[1] if len(groups) > 1 else None
                        fields['publisher'] = groups[2] if len(groups) > 2 else None
                        fields['year'] = groups[3] if len(groups) > 3 else None
                    elif citation_type == 'article':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['title'] = groups[1] if len(groups) > 1 else None
                        fields['journal'] = groups[2] if len(groups) > 2 else None
                        fields['volume'] = groups[3] if len(groups) > 3 else None
                        fields['year'] = groups[4] if len(groups) > 4 else None
                        fields['pages'] = groups[5] if len(groups) > 5 else None
                elif style == 'gb7714':
                    if citation_type == 'book':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['title'] = groups[1] if len(groups) > 1 else None
                        fields['publisher'] = groups[2] if len(groups) > 2 else None
                        fields['year'] = groups[3] if len(groups) > 3 else None
                    elif citation_type == 'article':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['title'] = groups[1] if len(groups) > 1 else None
                        fields['journal'] = groups[1] if len(groups) > 1 else None
                        fields['year'] = groups[2] if len(groups) > 2 else None
                        fields['volume'] = groups[3] if len(groups) > 3 else None
                        fields['pages'] = groups[4] if len(groups) > 4 else None
                elif style == 'ieee':
                    if citation_type == 'book':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['title'] = groups[1] if len(groups) > 1 else None
                        fields['year'] = groups[2] if len(groups) > 2 else None
                    elif citation_type == 'article':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['title'] = groups[1] if len(groups) > 1 else None
                        fields['journal'] = groups[2] if len(groups) > 2 else None
                        fields['volume'] = groups[3] if len(groups) > 3 else None
                        fields['pages'] = groups[4] if len(groups) > 4 else None
                        fields['year'] = groups[5] if len(groups) > 5 else None
                elif style == 'harvard':
                    if citation_type == 'book':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['year'] = groups[1] if len(groups) > 1 else None
                        fields['title'] = groups[2] if len(groups) > 2 else None
                        fields['publisher'] = groups[3] if len(groups) > 3 else None
                    elif citation_type == 'article':
                        fields['author'] = groups[0] if len(groups) > 0 else None
                        fields['year'] = groups[1] if len(groups) > 1 else None
                        fields['title'] = groups[2] if len(groups) > 2 else None
                        fields['journal'] = groups[3] if len(groups) > 3 else None
                        fields['volume'] = groups[4] if len(groups) > 4 else None
                        fields['issue'] = groups[5] if len(groups) > 5 else None
                        fields['pages'] = groups[6] if len(groups) > 6 else None
        
        if not fields:
            fields.update(self._parse_generic(citation))
        
        return fields
    
    def _parse_generic(self, citation: str) -> Dict[str, Any]:
        """
        通用解析方法 - WORKFLOW节点H：通用解析
        
        当无法识别特定格式时使用通用提取方法
        
        Args:
            citation: 原始引用字符串
            
        Returns:
            Dict: 解析后的字段字典
        """
        fields = {}
        
        author_match = self._extract_author(citation)
        if author_match:
            fields['author'] = author_match
        
        title_match = self._extract_title(citation)
        if title_match:
            fields['title'] = title_match
        
        year_match = self._extract_year(citation)
        if year_match:
            fields['year'] = year_match
        
        journal_match = self._extract_journal(citation)
        if journal_match:
            fields['journal'] = journal_match
        
        volume_match = self._extract_volume(citation)
        if volume_match:
            fields['volume'] = volume_match
        
        pages_match = self._extract_pages(citation)
        if pages_match:
            fields['pages'] = pages_match
        
        doi_match = self._extract_doi(citation)
        if doi_match:
            fields['doi'] = doi_match
        
        url_match = self._extract_url(citation)
        if url_match:
            fields['url'] = url_match
        
        return fields
    
    def _parse_with_llm(self, citation: str) -> Optional[Dict[str, Any]]:
        """
        使用LLM辅助识别 - 整合外部资料搜集
        
        当正则表达式无法完全解析引用时，调用LLM进行辅助识别。
        根据优化报告建议，优化提示词，增加具体示例，提升解析准确率。
        
        Args:
            citation: 原始引用字符串
            
        Returns:
            Optional[Dict]: LLM解析后的字段字典
        """
        if not self.use_llm:
            return None
        
        try:
            client = self._init_llm_client()
            if not client:
                return None
            
            CITATION_FORMAT_EXAMPLES = """
支持的格式类型示例：
1. Chicago格式: 作者."标题"[J].期刊,年份,卷(期):页码
   示例: Smith J. "Deep Learning for NLP"[J]. Nature, 2020, 10(2): 123-145.

2. APA格式: 作者(年份).标题.期刊,卷(期),页码
   示例: Smith, J. (2020). Deep Learning for NLP. Nature, 10(2), 123-145.

3. GB/T 7714格式: [序号]作者.标题[J].期刊,年份,卷(期):页码
   示例: [1] Smith J. Deep Learning for NLP[J]. Nature, 2020, 10(2): 123-145.

4. MLA格式: 作者."标题"[J].期刊, vol.卷, no.期, 年份, pp.页码
   示例: Smith, John. "Deep Learning for NLP." Nature, vol. 10, no. 2, 2020, pp. 123-145.

5. IEEE格式: [序号] 作者, "标题", 期刊, vol.卷, no.期, pp.页码, 年份
   示例: [1] J. Smith, "Deep Learning for NLP," Nature, vol. 10, no. 2, pp. 123-145, 2020.

6. Harvard格式: 作者(年份)'标题', 期刊, 卷(期), 页码
   示例: Smith (2020) 'Deep Learning for NLP', Nature, 10(2), pp. 123-145.
"""
            
            prompt = f"""请解析以下学术引用，提取关键字段。
{CITATION_FORMAT_EXAMPLES}

引用：{citation}

请以JSON格式返回以下字段（如果存在）：
- author: 作者姓名（多个作者用","分隔）
- title: 文章标题
- year: 出版年份（四位数字）
- journal: 期刊名称
- volume: 卷号
- issue: 期号
- pages: 页码范围（格式：起始页-结束页，如123-145）
- doi: DOI（格式：10.XXXX/...）
- url: 网址URL
- type: 文献类型（article/book/dissertation/conference/electronic）
- publisher: 出版社（仅图书需要）
- isbn: ISBN号（仅图书需要）

重要要求：
1. 严格按照JSON格式返回，只返回JSON，不要有其他内容
2. 所有字段值使用字符串类型
3. 如果字段不存在或无法确定，设置为null
4. 年份必须是四位数字，在1900-2030之间
5. 页码范围使用"-"连接，如"123-145"
6. DOI必须以"10."开头

请直接返回JSON格式的解析结果。"""
            
            response = client.call(prompt)
            
            if response:
                try:
                    import json
                    response_clean = response.strip()
                    if response_clean.startswith('```json'):
                        response_clean = response_clean[7:]
                    if response_clean.endswith('```'):
                        response_clean = response_clean[:-3]
                    response_clean = response_clean.strip()
                    
                    fields = json.loads(response_clean)
                    if isinstance(fields, dict):
                        return {k: v for k, v in fields.items() if v is not None and v != ''}
                    return None
                except json.JSONDecodeError as e:
                    print(f"JSON解析失败: {e}")
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        try:
                            fields = json.loads(json_match.group())
                            return {k: v for k, v in fields.items() if v is not None and v != ''}
                        except json.JSONDecodeError:
                            pass
                    return None
            
        except Exception as e:
            print(f"LLM辅助解析失败: {e}")
        
        return None
    
    def _detect_citation_type(self, citation: str) -> str:
        """检测引用类型"""
        citation_upper = citation.upper()
        citation_lower = citation.lower()
        
        if '[J]' in citation or '[j]' in citation:
            return 'article'
        elif '[M]' in citation or '[m]' in citation:
            return 'book'
        elif '[D]' in citation or '[d]' in citation:
            return 'dissertation'
        elif '[C]' in citation or '[c]' in citation:
            return 'conference'
        elif '[EB]' in citation or '[EB/OL]' in citation:
            return 'electronic'
        
        if 'doi' in citation_lower or 'DOI' in citation:
            return 'article'
        
        if any(word in citation_lower for word in ['journal', 'vol', 'no.', 'pp.']):
            return 'article'
        
        return 'unknown'
    
    def _extract_author(self, citation: str) -> Optional[str]:
        """提取作者"""
        patterns = [
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\.',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(',
            r'author[:\s]+([^\,\.\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, citation)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_title(self, citation: str) -> Optional[str]:
        """提取标题"""
        patterns = [
            r'"([^"]+)"',
            r'《([^》]+)》',
            r'title[:\s]+([^\,\.\n]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, citation)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_year(self, citation: str) -> Optional[str]:
        """提取年份"""
        patterns = [
            r'\((\d{4})\)',
            r',?\s*(\d{4}),?\s',
            r'\.(\d{4})\.',
            r'year[:\s]+(\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, citation)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_journal(self, citation: str) -> Optional[str]:
        """提取期刊名"""
        patterns = [
            r'\[J\]\s*\.\s*([^\,]+),',
            r'in\s+([^\.]+)\.',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, citation, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_volume(self, citation: str) -> Optional[str]:
        """提取卷号"""
        patterns = [
            r'vol\.?\s*(\d+)',
            r'第(\d+)卷',
            r',\s*(\d+)\s*,',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, citation, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_pages(self, citation: str) -> Optional[str]:
        """提取页码"""
        patterns = [
            r'pp?\.?\s*(\d+(?:-\d+)?)',
            r':\s*(\d+-\d+)\s',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, citation, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_doi(self, citation: str) -> Optional[str]:
        """提取DOI"""
        patterns = [
            r'doi[:\s]+([^\s]+)',
            r'(10\.\d{4,}/[^\s]+)',
            r'(https?://doi\.org/[^\s]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, citation, re.IGNORECASE)
            if match:
                doi = match.group(1)
                if doi.startswith('http'):
                    return doi
                return f"https://doi.org/{doi}"
        
        return None
    
    def _extract_url(self, citation: str) -> Optional[str]:
        """提取URL"""
        pattern = r'(https?://[^\s\]]+)'
        match = re.search(pattern, citation)
        if match:
            return match.group(1)
        
        return None
    
    def _validate_fields(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证字段完整性 - WORKFLOW节点I：validate_fields验证
        
        增强验证逻辑：
        1. 必填字段验证
        2. 字段格式验证
        3. 引用完整性评分
        4. 格式特定验证规则
        5. 字段关联性验证
        
        Args:
            parsed: 解析后的字段字典
            
        Returns:
            Dict[str, Any]: 验证结果字典
        """
        result = {
            'original': '',
            'parsed': True,
            'fields': parsed,
            'errors': [],
            'warnings': [],
            'completeness_score': 0.0
        }
        
        required_fields = ['author', 'title', 'year']
        optional_fields = ['journal', 'volume', 'pages', 'doi', 'url', 'publisher']
        
        missing_required = []
        for field in required_fields:
            if not parsed.get(field):
                missing_required.append(field)
                result['errors'].append(f'缺少必填字段: {field}')
        
        missing_optional = []
        for field in optional_fields:
            if not parsed.get(field):
                missing_optional.append(field)
                result['warnings'].append(f'缺少可选字段: {field}')
        
        if parsed.get('year'):
            try:
                year = int(parsed['year'])
                if year < 1900 or year > 2030:
                    result['errors'].append(f'年份异常: {year}，应在1900-2030之间')
                if year > 2026:
                    result['warnings'].append(f'年份{year}为未来日期，请确认')
            except ValueError:
                result['errors'].append(f'年份格式错误: {parsed["year"]}，应为四位数字')
        
        if parsed.get('doi'):
            doi = parsed['doi']
            if not self._validate_doi_format(doi):
                result['warnings'].append(f'DOI格式可能不正确: {doi}')
        
        if parsed.get('pages'):
            pages = parsed['pages']
            if not self._validate_pages_format(pages):
                result['warnings'].append(f'页码格式可能不正确: {pages}')
        
        if parsed.get('volume'):
            try:
                volume = int(parsed['volume'])
                if volume < 0:
                    result['errors'].append(f'卷号不能为负数: {volume}')
            except ValueError:
                result['warnings'].append(f'卷号格式异常: {parsed["volume"]}')
        
        self._validate_field_consistency(parsed, result)
        
        completeness_score = self._calculate_completeness_score(parsed, required_fields, optional_fields)
        result['completeness_score'] = completeness_score
        
        if completeness_score < 0.5:
            result['warnings'].append(f'引用完整度较低: {completeness_score:.1%}，建议补充更多字段')
        
        return result
    
    def _validate_doi_format(self, doi: str) -> bool:
        """
        验证DOI格式
        
        Args:
            doi: DOI字符串
            
        Returns:
            bool: 是否符合DOI格式
        """
        doi_pattern = r'^10\.\d{4,}/[^\s]+$'
        return bool(re.match(doi_pattern, doi))
    
    def _validate_pages_format(self, pages: str) -> bool:
        """
        验证页码格式
        
        Args:
            pages: 页码字符串
            
        Returns:
            bool: 是否符合页码格式
        """
        pages_pattern = r'^\d+(-\d+)?$'
        return bool(re.match(pages_pattern, pages))
    
    def _validate_field_consistency(self, parsed: Dict[str, Any], result: Dict[str, Any]):
        """
        验证字段关联性
        
        Args:
            parsed: 解析后的字段字典
            result: 验证结果字典
        """
        citation_type = parsed.get('type', 'unknown')
        
        if citation_type == 'article':
            if not parsed.get('journal'):
                result['warnings'].append('期刊文章缺少期刊名字段')
            if parsed.get('doi') and parsed.get('url'):
                if parsed['doi'] in parsed['url']:
                    result['warnings'].append('DOI和URL可能重复，请检查')
        
        if citation_type == 'book':
            if not parsed.get('publisher'):
                result['warnings'].append('图书缺少出版机构字段')
        
        author = parsed.get('author', '')
        title = parsed.get('title', '')
        if author and title:
            if author in title:
                result['warnings'].append('作者名可能错误地包含在标题中')
            if title in author:
                result['warnings'].append('标题可能错误地包含在作者名中')
    
    def _calculate_completeness_score(self, parsed: Dict[str, Any], 
                                    required: List[str], 
                                    optional: List[str]) -> float:
        """
        计算引用完整度评分
        
        Args:
            parsed: 解析后的字段字典
            required: 必填字段列表
            optional: 可选字段列表
            
        Returns:
            float: 完整度评分 (0.0 - 1.0)
        """
        required_present = sum(1 for field in required if parsed.get(field))
        optional_present = sum(1 for field in optional if parsed.get(field))
        
        required_score = required_present / len(required)
        optional_score = optional_present / len(optional) if optional else 0
        
        completeness = required_score * 0.7 + optional_score * 0.3
        
        return completeness
    
    def _check_field_completeness(self, citation: Dict[str, Any]) -> List[Dict]:
        """
        检查字段完整性 - 提供详细的可选字段检查
        
        Args:
            citation: 引用字典
            
        Returns:
            List[Dict]: 警告列表
        """
        warnings = []
        
        optional_fields = ['journal', 'volume', 'pages', 'doi', 'url']
        
        for field in optional_fields:
            if not citation.get('fields', {}).get(field):
                warnings.append({
                    'type': 'missing_optional_field',
                    'field': field,
                    'message': f'缺少可选字段: {field}'
                })
        
        return warnings
    
    def _find_duplicates(self, citations: List[Dict[str, Any]]) -> List[List[int]]:
        """查找重复引用"""
        duplicates = []
        seen = {}
        
        for i, citation in enumerate(citations):
            if not citation.get('parsed'):
                continue
            
            citation_hash = self._generate_citation_hash(citation)
            
            if citation_hash in seen:
                if seen[citation_hash] not in [d[0] for d in duplicates]:
                    duplicates.append([seen[citation_hash], i])
                else:
                    for dup in duplicates:
                        if dup[0] == seen[citation_hash]:
                            dup.append(i)
            else:
                seen[citation_hash] = i
        
        return duplicates
    
    def _generate_citation_hash(self, citation: Dict[str, Any]) -> str:
        """生成引用哈希"""
        fields = citation.get('fields', {})
        
        hash_content = f"{fields.get('author', '')}_{fields.get('title', '')}_{fields.get('year', '')}"
        
        return hashlib.md5(hash_content.encode('utf-8')).hexdigest()
    
    def _parse_authors(self, author_str: str) -> List[str]:
        """解析作者列表"""
        if not author_str:
            return []
        
        authors = re.split(r'[,，&and]+', author_str)
        return [a.strip() for a in authors if a.strip()]
    
    def _is_complete(self, fields: Dict[str, Any]) -> bool:
        """检查引用是否完整"""
        required = ['author', 'title', 'year']
        return all(fields.get(field) for field in required)
    
    def _normalize_author(self, author: str) -> str:
        """规范化作者名"""
        author = author.strip()
        
        parts = author.split()
        if len(parts) > 1:
            last_name = parts[-1]
            initials = ''.join(p[0] + '.' for p in parts[:-1] if p)
            return f"{last_name}, {initials}"
        
        return author
    
    def _normalize_title(self, title: str) -> str:
        """规范化标题"""
        title = title.strip()
        
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1]
        if title.startswith('《') and title.endswith('》'):
            title = title[1:-1]
        
        return title
    
    def _normalize_year(self, year: str) -> str:
        """规范化年份"""
        try:
            return str(int(year))
        except ValueError:
            return year
    
    def _normalize_journal(self, journal: str) -> str:
        """规范化期刊名"""
        return journal.strip()
    
    def _normalize_volume(self, volume: str) -> str:
        """规范化卷号"""
        try:
            return str(int(volume))
        except ValueError:
            return volume
    
    def _normalize_pages(self, pages: str) -> str:
        """规范化页码"""
        pages = pages.strip()
        
        if '-' in pages:
            start, end = pages.split('-')
            return f"{int(start.strip())}-{int(end.strip())}"
        
        return pages
    
    def _normalize_doi(self, doi: str) -> str:
        """规范化DOI"""
        if doi.startswith('https://doi.org/'):
            return doi
        if doi.startswith('doi:'):
            return f"https://doi.org/{doi[5:].strip()}"
        return f"https://doi.org/{doi}"
    
    def _normalize_url(self, url: str) -> str:
        """规范化URL"""
        if not url.startswith(('http://', 'https://')):
            return f"https://{url}"
        return url
    
    def _format_chicago(self, fields: Dict[str, Any]) -> str:
        """Chicago格式"""
        parts = []
        
        if fields.get('author'):
            parts.append(f"{fields['author']}.")
        
        if fields.get('title'):
            parts.append(f'"{fields["title"]}"')
        
        if fields.get('journal'):
            parts.append(f"{fields['journal']}")
            if fields.get('volume'):
                parts.append(f"{fields['volume']}")
            if fields.get('pages'):
                parts.append(f": {fields['pages']}")
        
        if fields.get('year'):
            parts.append(f"({fields['year']})")
        
        return '. '.join(parts)
    
    def _format_apa(self, fields: Dict[str, Any]) -> str:
        """APA格式"""
        parts = []
        
        if fields.get('author'):
            parts.append(fields['author'])
        
        if fields.get('year'):
            parts.append(f"({fields['year']})")
        
        if fields.get('title'):
            parts.append(f"{fields['title']}.")
        
        if fields.get('journal'):
            journal_part = fields['journal']
            if fields.get('volume'):
                journal_part += f", {fields['volume']}"
            if fields.get('pages'):
                journal_part += f", {fields['pages']}"
            parts.append(journal_part)
        
        return ' '.join(parts)
    
    def _format_mla(self, fields: Dict[str, Any]) -> str:
        """MLA格式"""
        parts = []
        
        if fields.get('author'):
            parts.append(f"{fields['author']}.")
        
        if fields.get('title'):
            parts.append(f'"{fields["title"]}"')
        
        if fields.get('journal'):
            parts.append(f"{fields['journal']},")
        
        if fields.get('volume'):
            parts.append(f"vol. {fields['volume']},")
        
        if fields.get('year'):
            parts.append(f"{fields['year']},")
        
        if fields.get('pages'):
            parts.append(f"pp. {fields['pages']}")
        
        return ' '.join(parts)
    
    def _format_gb7714(self, fields: Dict[str, Any]) -> str:
        """GB/T 7714格式"""
        parts = []
        
        if fields.get('author'):
            parts.append(fields['author'])
        
        if fields.get('title'):
            parts.append(f"[{fields.get('type', 'J').upper()}]")
            parts.append(fields['title'])
        
        if fields.get('journal'):
            if parts:
                parts[-1] += '.'
            parts.append(fields['journal'])
        
        if fields.get('year'):
            parts.append(fields['year'])
        
        if fields.get('volume'):
            parts.append(fields['volume'])
        
        if fields.get('pages'):
            parts.append(fields['pages'])
        
        return ', '.join(parts)
    
    def _format_ieee(self, fields: Dict[str, Any]) -> str:
        """IEEE格式"""
        parts = []
        
        if fields.get('author'):
            parts.append(fields['author'])
        
        if fields.get('title'):
            parts.append(f'"{fields["title"]}"')
        
        if fields.get('journal'):
            parts.append(fields['journal'])
        
        if fields.get('volume'):
            parts.append(f"vol. {fields['volume']}")
        
        if fields.get('pages'):
            parts.append(f"pp. {fields['pages']}")
        
        if fields.get('year'):
            parts.append(f"{fields['year']}")
        
        return ', '.join(parts)
    
    def _format_harvard(self, fields: Dict[str, Any]) -> str:
        """Harvard格式"""
        parts = []
        
        if fields.get('author'):
            parts.append(fields['author'])
        
        if fields.get('year'):
            parts.append(f"({fields['year']})")
        
        if fields.get('title'):
            parts.append(f"'{fields['title']}'")
        
        if fields.get('journal'):
            parts.append(fields['journal'])
        
        if fields.get('volume'):
            parts.append(f"vol. {fields['volume']}")
        
        if fields.get('pages'):
            parts.append(f"pp. {fields['pages']}")
        
        return ', '.join(parts)
