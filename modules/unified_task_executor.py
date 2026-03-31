"""
统一任务执行框架

提供统一的任务执行接口，支持两种执行模式：
1. API模式：通过大语言模型API执行任务
2. 脚本模式：使用传统脚本/正则表达式执行任务

用户可以根据需求自由切换模式。

核心功能：
- 统一的任务执行接口
- 模式切换机制
- 任务注册与管理
- 结果缓存与验证
- 错误处理与重试

使用方法：
    from modules.unified_task_executor import UnifiedTaskExecutor
    
    executor = UnifiedTaskExecutor()
    
    # 使用API模式
    executor.set_mode('api')
    result = executor.execute('ner', text="伊藤博文是明治维新的重要人物...")
    
    # 使用脚本模式
    executor.set_mode('script')
    result = executor.execute('ner', text="伊藤博文是明治维新的重要人物...")
"""

import os
import re
import json
import time
import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Union, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from modules.secure_api_key_manager import get_secure_key_manager, SecureAPIKeyManager


class ExecutionMode(Enum):
    """执行模式枚举"""
    API = "api"
    SCRIPT = "script"
    AUTO = "auto"


class TaskType(Enum):
    """任务类型枚举"""
    NER = "ner"
    ACADEMIC_NOTE = "academic_note"
    PAPER_POLISH = "paper_polish"
    CITATION_NORMALIZE = "citation_normalize"
    STYLE_TRANSFER = "style_transfer"
    OCR_CORRECTION = "ocr_correction"
    TEXT_SUMMARY = "text_summary"
    ENTITY_DISAMBIGUATION = "entity_disambiguation"
    REVERSE_OUTLINE = "reverse_outline"
    VIRTUAL_PERSONA = "virtual_persona"
    DATA_STRUCTURE = "data_structure"
    CUSTOM = "custom"


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool
    data: Any
    mode: str
    task_type: str
    execution_time: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'data': self.data,
            'mode': self.mode,
            'task_type': self.task_type,
            'execution_time': self.execution_time,
            'error': self.error,
            'metadata': self.metadata
        }


@dataclass
class TaskConfig:
    """任务配置"""
    task_type: TaskType
    provider: str = "qwen"
    model: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3
    cache_enabled: bool = True
    custom_prompt: Optional[str] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


class BaseTaskHandler(ABC):
    """任务处理器基类"""
    
    @abstractmethod
    def execute_api(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        """API模式执行"""
        pass
    
    @abstractmethod
    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        """脚本模式执行"""
        pass
    
    def get_required_params(self) -> List[str]:
        """获取必需参数列表"""
        return []


class NERHandler(BaseTaskHandler):
    """命名实体识别任务处理器"""
    
    API_PROMPT = """请从以下文本中识别并标注命名实体。

【实体类型】
- person: 历史人物
- location: 地理位置
- organization: 机构组织
- event: 历史事件
- date: 历史年代
- work: 著作文献
- concept: 思想概念

【输出格式】
请以JSON格式输出，包含entities数组，每个实体包含：
- text: 实体文本
- category: 实体类型
- position: 在原文中的位置（可选）

【待处理文本】
{text}

请直接输出JSON格式的结果，不要添加任何解释。"""

    SCRIPT_PATTERNS = {
        'person': [
            r'[一-龥]{2,4}(氏|公爵|侯爵|伯爵|子爵|男爵|藩主|大名|将军|天皇|大臣)',
            r'[一-龥]{2,3}(之助|太郎|次郎|三郎|兵卫|卫门|助|介)',
        ],
        'date': [
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'\d{4}年',
            r'(明治|大正|昭和|平成|令和)\d{1,2}年',
            r'(奈良|平安|鎌倉|室町|戦国|江戸|幕末)时代',
        ],
        'location': [
            r'[一-龥]{2,4}(藩|国|郡|县|市|村|町)',
            r'(东京|京都|大阪|江户|奈良|京都|长崎|横滨|神户)',
        ],
        'organization': [
            r'[一-龥]{2,6}(幕府|朝廷|国会|省|部|院|会|党)',
            r'(萨摩藩|长州藩|土佐藩|肥前藩)',
        ]
    }
    
    def __init__(self, key_manager: SecureAPIKeyManager):
        self.key_manager = key_manager
        self.llm_client = None
    
    def _init_llm_client(self, config: TaskConfig):
        if self.llm_client is None:
            from modules.llm_client import create_llm_client
            llm_config = self.key_manager.create_provider_config(config.provider)
            if config.model:
                llm_config['model'] = config.model
            self.llm_client = create_llm_client(llm_config)
    
    def execute_api(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        categories = input_data.get('categories', None)
        
        self._init_llm_client(config)
        
        prompt = self.API_PROMPT.format(text=text)
        
        if categories:
            prompt = prompt.replace(
                "【实体类型】\n- person: 历史人物",
                f"【实体类型】\n仅识别以下类型: {', '.join(categories)}"
            )
        
        if config.custom_prompt:
            prompt = config.custom_prompt.format(text=text)
        
        result = self.llm_client._call_llm(prompt, temperature=config.temperature)
        
        content = result.get('content', '')
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            return {'entities': [], 'raw_response': content}
        except json.JSONDecodeError:
            return {'entities': [], 'raw_response': content}
    
    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        categories = input_data.get('categories')
        if categories is None:
            categories = list(self.SCRIPT_PATTERNS.keys())
        
        entities = []
        
        for category in categories:
            if category not in self.SCRIPT_PATTERNS:
                continue
            
            patterns = self.SCRIPT_PATTERNS[category]
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    entities.append({
                        'text': match.group(),
                        'category': category,
                        'position': match.start()
                    })
        
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e['text'], e['category'])
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)
        
        return {'entities': unique_entities}
    
    def get_required_params(self) -> List[str]:
        return ['text']


class AcademicNoteHandler(BaseTaskHandler):
    """学术笔记生成任务处理器"""
    
    API_PROMPT = """你是一位专业的学术研究助理，请根据以下文本生成结构化的学术笔记。

【输出格式】
请以Markdown格式输出，包含以下部分：
1. 标题
2. 总体摘要（使用[[双向链接]]标注实体）
3. 核心论点
4. 关键实体提取（人名、地名、事件、概念、文献）
5. 知识图谱节点

【待处理文本】
{text}

请直接输出Markdown格式的笔记内容。"""

    SCRIPT_TEMPLATE = """---
type: reading_note
created: {created_date}
source: {source}
---

# 笔记摘要

{summary}

## 关键实体

{entities}

## 原文片段

> {excerpt}
"""
    
    def __init__(self, key_manager: SecureAPIKeyManager):
        self.key_manager = key_manager
        self.llm_client = None
    
    def _init_llm_client(self, config: TaskConfig):
        if self.llm_client is None:
            from modules.llm_client import create_llm_client
            llm_config = self.key_manager.create_provider_config(config.provider)
            if config.model:
                llm_config['model'] = config.model
            self.llm_client = create_llm_client(llm_config)
    
    def execute_api(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        source = input_data.get('source', '未知来源')
        
        self._init_llm_client(config)
        
        prompt = self.API_PROMPT.format(text=text)
        
        if config.custom_prompt:
            prompt = config.custom_prompt.format(text=text, source=source)
        
        result = self.llm_client._call_llm(prompt, temperature=config.temperature, max_tokens=config.max_tokens)
        
        return {
            'note_content': result.get('content', ''),
            'source': source,
            'mode': 'api'
        }
    
    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        source = input_data.get('source', '未知来源')
        
        sentences = re.split(r'[。！？\n]', text)
        summary = sentences[0] if sentences else ''
        
        entities = re.findall(r'[一-龥]{2,4}', text[:500])
        unique_entities = list(set(entities))[:10]
        
        excerpt = text[:200] + '...' if len(text) > 200 else text
        
        note_content = self.SCRIPT_TEMPLATE.format(
            created_date=datetime.now().strftime('%Y-%m-%d'),
            source=source,
            summary=summary,
            entities='\n'.join([f'- [[{e}]]' for e in unique_entities]),
            excerpt=excerpt
        )
        
        return {
            'note_content': note_content,
            'source': source,
            'mode': 'script'
        }
    
    def get_required_params(self) -> List[str]:
        return ['text']


class PaperPolishHandler(BaseTaskHandler):
    """论文润色任务处理器"""
    
    API_PROMPT = """你是一位专业的学术论文编辑，请对以下文本进行润色。

【润色要求】
1. 修正语法错误
2. 提升学术表达规范度
3. 删除冗余内容
4. 保持原意不变
5. 保护历史专有名词

【输出格式】
请以JSON格式输出：
{{
    "polished_text": "润色后的文本",
    "changes": [
        {{"original": "原文", "modified": "修改后", "reason": "修改原因"}}
    ],
    "summary": "润色总结"
}}

【待润色文本】
{text}

请直接输出JSON格式的结果。"""

    REDUNDANT_PATTERNS = [
        (r'非常非常+', '非常'),
        (r'极其极其+', '极其'),
        (r'可以说是可以说', '可以说'),
        (r'基本上基本上', '基本上'),
        (r'\s+', ' '),
    ]
    
    def __init__(self, key_manager: SecureAPIKeyManager):
        self.key_manager = key_manager
        self.llm_client = None
    
    def _init_llm_client(self, config: TaskConfig):
        if self.llm_client is None:
            from modules.llm_client import create_llm_client
            llm_config = self.key_manager.create_provider_config(config.provider)
            if config.model:
                llm_config['model'] = config.model
            self.llm_client = create_llm_client(llm_config)
    
    def execute_api(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        language = input_data.get('language', 'zh')
        
        self._init_llm_client(config)
        
        prompt = self.API_PROMPT.format(text=text)
        
        if config.custom_prompt:
            prompt = config.custom_prompt.format(text=text, language=language)
        
        result = self.llm_client._call_llm(prompt, temperature=config.temperature, max_tokens=config.max_tokens)
        
        content = result.get('content', '')
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            return {'polished_text': content, 'changes': [], 'summary': 'API返回非JSON格式'}
        except json.JSONDecodeError:
            return {'polished_text': content, 'changes': [], 'summary': 'JSON解析失败'}
    
    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        
        polished_text = text
        changes = []
        
        for pattern, replacement in self.REDUNDANT_PATTERNS:
            matches = re.findall(pattern, polished_text)
            if matches:
                old_text = polished_text
                polished_text = re.sub(pattern, replacement, polished_text)
                changes.append({
                    'original': matches[0] if matches else '',
                    'modified': replacement,
                    'reason': '去除冗余表达'
                })
        
        polished_text = re.sub(r'\n{3,}', '\n\n', polished_text)
        
        return {
            'polished_text': polished_text,
            'changes': changes,
            'summary': f'脚本模式完成，共修改{len(changes)}处'
        }
    
    def get_required_params(self) -> List[str]:
        return ['text']


class CitationNormalizeHandler(BaseTaskHandler):
    """引用规范化任务处理器"""
    
    API_PROMPT = """请将以下引用文献规范化为指定格式。

【目标格式】
{target_style}

【待处理引用】
{citation}

【输出格式】
请以JSON格式输出：
{{
    "normalized": "规范化后的引用",
    "detected_format": "检测到的原格式",
    "fields": {{
        "author": "作者",
        "title": "标题",
        "year": "年份",
        "journal": "期刊",
        "volume": "卷",
        "pages": "页码"
    }}
}}

请直接输出JSON格式的结果。"""

    FORMAT_PATTERNS = {
        'gb7714': {
            'article': r'\[?\d+\]?\s*([^\[]+)\s*\[J\]\s*\.\s*([^\,]+),\s*(\d{4}),?\s*(\d+)?,?\s*(\d+-\d+)?',
            'book': r'\[?\d+\]?\s*([^\[]+)\s*\[M\]\s*\.\s*([^\:]+):\s*([^\,]+),\s*(\d{4})',
        },
        'apa': {
            'article': r'([^(]+)\s*\((\d{4})\)\.\s*([^\.]+)\.\s*([^,]+),\s*(\d+),\s*(\d+-\d+)',
            'book': r'([^(]+)\s*\((\d{4})\)\.\s*([^\.]+)\.\s*([^\:]+):\s*([^\.]+)',
        }
    }
    
    def __init__(self, key_manager: SecureAPIKeyManager):
        self.key_manager = key_manager
        self.llm_client = None
    
    def _init_llm_client(self, config: TaskConfig):
        if self.llm_client is None:
            from modules.llm_client import create_llm_client
            llm_config = self.key_manager.create_provider_config(config.provider)
            if config.model:
                llm_config['model'] = config.model
            self.llm_client = create_llm_client(llm_config)
    
    def execute_api(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        citation = input_data.get('citation', '')
        target_style = input_data.get('target_style', 'gb7714')
        
        self._init_llm_client(config)
        
        prompt = self.API_PROMPT.format(citation=citation, target_style=target_style)
        
        result = self.llm_client._call_llm(prompt, temperature=config.temperature)
        
        content = result.get('content', '')
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            return {'normalized': citation, 'error': '无法解析API响应'}
        except json.JSONDecodeError:
            return {'normalized': citation, 'error': 'JSON解析失败'}
    
    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        citation = input_data.get('citation', '')
        target_style = input_data.get('target_style', 'gb7714')
        
        detected_format = 'unknown'
        fields = {}
        
        for fmt_name, patterns in self.FORMAT_PATTERNS.items():
            for doc_type, pattern in patterns.items():
                match = re.search(pattern, citation)
                if match:
                    detected_format = fmt_name
                    groups = match.groups()
                    if doc_type == 'article':
                        fields = {
                            'author': groups[0] if len(groups) > 0 else '',
                            'year': groups[2] if len(groups) > 2 else '',
                            'title': '',
                            'journal': groups[1] if len(groups) > 1 else '',
                        }
                    break
            if detected_format != 'unknown':
                break
        
        return {
            'normalized': citation,
            'detected_format': detected_format,
            'fields': fields,
            'note': '脚本模式仅进行格式检测，完整转换请使用API模式'
        }
    
    def get_required_params(self) -> List[str]:
        return ['citation']


class OCRCorrectionHandler(BaseTaskHandler):
    """OCR校正任务处理器"""
    
    API_PROMPT = """请校正以下OCR识别文本中的错误。

【校正要求】
1. 修正错别字
2. 补充漏字
3. 删除多余字符
4. 修正格式错误
5. 保持原文结构

【待校正文本】
{text}

【输出格式】
请以JSON格式输出：
{{
    "corrected_text": "校正后的文本",
    "corrections": [
        {{"original": "原文", "corrected": "校正后", "type": "错误类型"}}
    ]
}}

请直接输出JSON格式的结果。"""

    COMMON_OCR_ERRORS = {
        '日': '曰',
        '曰': '日',
        '己': '已',
        '已': '己',
        '巳': '己',
        '戊': '戌',
        '戌': '戊',
        '0': 'O',
        'O': '0',
        'l': '1',
        '1': 'l',
    }
    
    def __init__(self, key_manager: SecureAPIKeyManager):
        self.key_manager = key_manager
        self.llm_client = None
    
    def _init_llm_client(self, config: TaskConfig):
        if self.llm_client is None:
            from modules.llm_client import create_llm_client
            llm_config = self.key_manager.create_provider_config(config.provider)
            if config.model:
                llm_config['model'] = config.model
            self.llm_client = create_llm_client(llm_config)
    
    def execute_api(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        language = input_data.get('language', 'zh')
        
        self._init_llm_client(config)
        
        prompt = self.API_PROMPT.format(text=text)
        
        result = self.llm_client._call_llm(prompt, temperature=config.temperature, max_tokens=config.max_tokens)
        
        content = result.get('content', '')
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            return {'corrected_text': text, 'corrections': []}
        except json.JSONDecodeError:
            return {'corrected_text': content, 'corrections': []}
    
    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        
        corrected_text = text
        corrections = []
        
        for wrong, right in self.COMMON_OCR_ERRORS.items():
            if wrong in corrected_text:
                corrected_text = corrected_text.replace(wrong, right)
                corrections.append({
                    'original': wrong,
                    'corrected': right,
                    'type': '常见OCR错误'
                })
        
        corrected_text = re.sub(r'\s+', ' ', corrected_text)
        corrected_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', corrected_text)
        
        return {
            'corrected_text': corrected_text,
            'corrections': corrections
        }
    
    def get_required_params(self) -> List[str]:
        return ['text']


class TextSummaryHandler(BaseTaskHandler):
    """文本摘要任务处理器"""
    
    API_PROMPT = """请为以下文本生成摘要。

【摘要要求】
1. 提取核心观点
2. 保留关键信息
3. 控制在{max_length}字以内
4. 语言简洁清晰

【待摘要文本】
{text}

请直接输出摘要内容。"""

    def __init__(self, key_manager: SecureAPIKeyManager):
        self.key_manager = key_manager
        self.llm_client = None
    
    def _init_llm_client(self, config: TaskConfig):
        if self.llm_client is None:
            from modules.llm_client import create_llm_client
            llm_config = self.key_manager.create_provider_config(config.provider)
            if config.model:
                llm_config['model'] = config.model
            self.llm_client = create_llm_client(llm_config)
    
    def execute_api(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        max_length = input_data.get('max_length', 200)
        
        self._init_llm_client(config)
        
        prompt = self.API_PROMPT.format(text=text, max_length=max_length)
        
        result = self.llm_client._call_llm(prompt, temperature=config.temperature, max_tokens=config.max_tokens)
        
        return {
            'summary': result.get('content', ''),
            'original_length': len(text),
            'mode': 'api'
        }
    
    def execute_script(self, input_data: Dict[str, Any], config: TaskConfig) -> Any:
        text = input_data.get('text', '')
        max_length = input_data.get('max_length', 200)
        
        sentences = re.split(r'[。！？\n]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        summary = ''
        for sentence in sentences:
            if len(summary) + len(sentence) <= max_length:
                summary += sentence + '。'
            else:
                break
        
        if not summary and sentences:
            summary = sentences[0][:max_length] + '...'
        
        return {
            'summary': summary,
            'original_length': len(text),
            'summary_length': len(summary),
            'mode': 'script'
        }
    
    def get_required_params(self) -> List[str]:
        return ['text']


class UnifiedTaskExecutor:
    """统一任务执行器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, default_mode: str = "api"):
        if not hasattr(self, '_initialized'):
            self.key_manager = get_secure_key_manager()
            self.mode = ExecutionMode(default_mode)
            self.default_provider = "qwen"
            self._handlers: Dict[TaskType, BaseTaskHandler] = {}
            self._cache: Dict[str, TaskResult] = {}
            self._cache_enabled = True
            self._execution_history: List[Dict[str, Any]] = []
            
            self._register_handlers()
            self._initialized = True
    
    def _register_handlers(self):
        """注册所有任务处理器"""
        self._handlers[TaskType.NER] = NERHandler(self.key_manager)
        self._handlers[TaskType.ACADEMIC_NOTE] = AcademicNoteHandler(self.key_manager)
        self._handlers[TaskType.PAPER_POLISH] = PaperPolishHandler(self.key_manager)
        self._handlers[TaskType.CITATION_NORMALIZE] = CitationNormalizeHandler(self.key_manager)
        self._handlers[TaskType.OCR_CORRECTION] = OCRCorrectionHandler(self.key_manager)
        self._handlers[TaskType.TEXT_SUMMARY] = TextSummaryHandler(self.key_manager)
    
    def set_mode(self, mode: Union[str, ExecutionMode]):
        """
        设置执行模式
        
        Args:
            mode: 'api', 'script', 或 'auto'
        """
        if isinstance(mode, str):
            self.mode = ExecutionMode(mode.lower())
        else:
            self.mode = mode
    
    def get_mode(self) -> str:
        """获取当前执行模式"""
        return self.mode.value
    
    def set_provider(self, provider: str):
        """设置默认API提供商"""
        self.default_provider = provider
    
    def enable_cache(self, enabled: bool = True):
        """启用/禁用缓存"""
        self._cache_enabled = enabled
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
    
    def _get_cache_key(self, task_type: str, input_data: Dict[str, Any], config: TaskConfig) -> str:
        """生成缓存键"""
        data_str = json.dumps(input_data, sort_keys=True, ensure_ascii=False)
        config_str = f"{config.provider}_{config.model}_{config.temperature}"
        return hashlib.md5(f"{task_type}_{data_str}_{config_str}".encode()).hexdigest()
    
    def execute(self, 
                task_type: Union[str, TaskType],
                config: Optional[TaskConfig] = None,
                **kwargs) -> TaskResult:
        """
        执行任务
        
        Args:
            task_type: 任务类型
            config: 任务配置
            **kwargs: 任务输入参数
            
        Returns:
            TaskResult: 执行结果
        """
        if isinstance(task_type, str):
            task_type = TaskType(task_type.lower())
        
        if config is None:
            config = TaskConfig(
                task_type=task_type,
                provider=self.default_provider
            )
        
        handler = self._handlers.get(task_type)
        if handler is None:
            return TaskResult(
                success=False,
                data=None,
                mode=self.mode.value,
                task_type=task_type.value,
                execution_time=0,
                error=f"未找到任务处理器: {task_type.value}"
            )
        
        required_params = handler.get_required_params()
        missing_params = [p for p in required_params if p not in kwargs]
        if missing_params:
            return TaskResult(
                success=False,
                data=None,
                mode=self.mode.value,
                task_type=task_type.value,
                execution_time=0,
                error=f"缺少必需参数: {missing_params}"
            )
        
        if self._cache_enabled:
            cache_key = self._get_cache_key(task_type.value, kwargs, config)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        start_time = time.time()
        
        try:
            if self.mode == ExecutionMode.API:
                result_data = handler.execute_api(kwargs, config)
            elif self.mode == ExecutionMode.SCRIPT:
                result_data = handler.execute_script(kwargs, config)
            else:
                try:
                    result_data = handler.execute_api(kwargs, config)
                except Exception:
                    result_data = handler.execute_script(kwargs, config)
            
            execution_time = time.time() - start_time
            
            task_result = TaskResult(
                success=True,
                data=result_data,
                mode=self.mode.value,
                task_type=task_type.value,
                execution_time=execution_time,
                metadata={
                    'provider': config.provider,
                    'model': config.model,
                    'timestamp': datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            task_result = TaskResult(
                success=False,
                data=None,
                mode=self.mode.value,
                task_type=task_type.value,
                execution_time=execution_time,
                error=str(e)
            )
        
        self._execution_history.append({
            'task_type': task_type.value,
            'mode': self.mode.value,
            'success': task_result.success,
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat()
        })
        
        if self._cache_enabled and task_result.success:
            self._cache[cache_key] = task_result
        
        return task_result
    
    def execute_with_prompt(self,
                           task_type: Union[str, TaskType],
                           custom_prompt: str,
                           **kwargs) -> TaskResult:
        """
        使用自定义提示词执行任务
        
        Args:
            task_type: 任务类型
            custom_prompt: 自定义提示词模板
            **kwargs: 任务输入参数
            
        Returns:
            TaskResult: 执行结果
        """
        if isinstance(task_type, str):
            task_type = TaskType(task_type.lower())
        
        config = TaskConfig(
            task_type=task_type,
            provider=self.default_provider,
            custom_prompt=custom_prompt
        )
        
        return self.execute(task_type, config=config, **kwargs)
    
    def batch_execute(self,
                     task_type: Union[str, TaskType],
                     input_list: List[Dict[str, Any]],
                     config: Optional[TaskConfig] = None) -> List[TaskResult]:
        """
        批量执行任务
        
        Args:
            task_type: 任务类型
            input_list: 输入数据列表
            config: 任务配置
            
        Returns:
            List[TaskResult]: 执行结果列表
        """
        results = []
        for input_data in input_list:
            result = self.execute(task_type, config=config, **input_data)
            results.append(result)
        return results
    
    def get_supported_tasks(self) -> List[str]:
        """获取支持的任务类型列表"""
        return [t.value for t in self._handlers.keys()]
    
    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self._execution_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取执行统计"""
        if not self._execution_history:
            return {
                'total_executions': 0,
                'success_rate': 0,
                'average_time': 0
            }
        
        total = len(self._execution_history)
        success_count = sum(1 for h in self._execution_history if h['success'])
        total_time = sum(h['execution_time'] for h in self._execution_history)
        
        return {
            'total_executions': total,
            'success_rate': success_count / total,
            'average_time': total_time / total,
            'cache_size': len(self._cache),
            'current_mode': self.mode.value
        }


def get_task_executor() -> UnifiedTaskExecutor:
    """获取任务执行器单例"""
    return UnifiedTaskExecutor()


if __name__ == '__main__':
    executor = UnifiedTaskExecutor()
    
    print("=" * 60)
    print("统一任务执行器")
    print("=" * 60)
    
    print(f"\n当前模式: {executor.get_mode()}")
    print(f"支持的任务: {executor.get_supported_tasks()}")
    
    print("\n" + "=" * 60)
    print("测试脚本模式 - NER任务")
    print("=" * 60)
    
    executor.set_mode('script')
    result = executor.execute('ner', text="伊藤博文出生于1841年，是明治维新的重要人物。")
    print(f"成功: {result.success}")
    print(f"结果: {result.data}")
    
    print("\n" + "=" * 60)
    print("测试API模式 - 摘要任务")
    print("=" * 60)
    
    executor.set_mode('api')
    result = executor.execute('text_summary', text="这是一段很长的文本..." * 10)
    print(f"成功: {result.success}")
    if result.error:
        print(f"错误: {result.error}")
    
    print("\n" + "=" * 60)
    print("执行统计")
    print("=" * 60)
    stats = executor.get_statistics()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
