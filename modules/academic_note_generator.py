"""
学术笔记智能生成模块

基于大语言模型，从学术文献中自动生成符合Obsidian格式的结构化阅读笔记
支持双向链接、知识图谱构建等高级功能

核心功能：
- 生成带双向链接的学术笔记
- 提取五类核心实体（人名、地名、事件、概念、文献）
- 构建知识图谱节点数据
- 支持多种API提供商（通义千问、MiniMax等）

API优先级：
1. 阿里通义千问 (dashscope)
2. MiniMax
3. Gemini/ChatGPT（备选）

测试模式：使用模拟数据，不调用真实API

提示词管理：
- 系统提示词: AN_G001
- 笔记模板: AN_T001
- 用户提示词: AN_U001, AN_U002
"""

import re
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import hashlib

from modules.llm_client import create_llm_client

try:
    from prompts.prompt_loader import PromptLoader, PromptTemplate
    PROMPT_LOADER_AVAILABLE = True
except ImportError:
    PROMPT_LOADER_AVAILABLE = False


class AcademicNoteGenerator:
    """学术笔记智能生成器"""
    
    ENTITY_TYPES = {
        'person': '人名 (Person)',
        'location': '地名 (Location)', 
        'event': '事件 (Event)',
        'concept': '概念/术语 (Concept)',
        'literature': '引用文献 (Literature)'
    }
    
    DEFAULT_SYSTEM_PROMPT = """你是一位专业的学术研究助理和知识管理专家，精通复杂文本分析与Obsidian知识图谱（Knowledge Graph）的构建。

请分析以下学术文章，严格按照要求输出Markdown格式的阅读笔记。

【核心任务】
1. 提取五类核心实体并使用Obsidian双向链接语法 [[实体名称]] 包裹
2. 生成结构化的章节脉络
3. 构建知识图谱节点数据

【实体类型定义】
- 人名 (Person)：历史人物、学者等
- 地名 (Location)：国家、城市、地区等
- 事件 (Event)：历史事件、会议、运动等
- 概念/术语 (Concept)：学术术语、理论、主义等
- 引用文献 (Literature)：著作、论文、史料等

【输出格式要求】
1. 在"总体摘要"和"章节脉络"的正文中，只要实体出现，就必须加上 [[ ]] 
2. 绝对不要使用普通的Markdown超链接格式 [文本](链接)
3. 只能使用 [[文本]] 格式
"""
    
    DEFAULT_NOTE_TEMPLATE = """---
type: reading_note
tags:
  - #文献笔记
  - #{subject_tag}
created: {created_date}
source: {source_title}
---

# {title}

## 📋 总体摘要

{summary}

## 📑 章节核心论点

{chapter_outline}

## 🔗 核心图谱节点提取

{knowledge_graph}

---

**元数据**
- 作者：{authors}
- 发表年份：{year}
- 关键词：{keywords}
"""

    def __init__(self, api_provider: str = "qwen", test_mode: bool = True):
        """
        初始化学术笔记生成器
        
        Args:
            api_provider: API提供商 ('qwen', 'minimax', 'gemini', 'chatgpt')
            test_mode: 测试模式标志，True时使用模拟数据
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.llm_client = None
        self._prompt_loader = None
        self._prompt_template = None
        
        self.provider_mapping = {
            'qwen': 'dashscope',
            'minimax': 'minimax',
            'gemini': 'custom',
            'chatgpt': 'openai'
        }
    
    def _get_prompt_loader(self):
        """获取提示词加载器实例"""
        if self._prompt_loader is None and PROMPT_LOADER_AVAILABLE:
            self._prompt_loader = PromptLoader()
        return self._prompt_loader
    
    def _get_prompt_template(self):
        """获取提示词模板管理器"""
        if self._prompt_template is None:
            loader = self._get_prompt_loader()
            self._prompt_template = PromptTemplate(loader) if loader else None
        return self._prompt_template
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        loader = self._get_prompt_loader()
        if loader:
            try:
                return loader.load_prompt('academic_note_generator', 'AN_G001')
            except Exception:
                pass
        return self.DEFAULT_SYSTEM_PROMPT
    
    def _load_note_template(self) -> str:
        """加载笔记模板"""
        loader = self._get_prompt_loader()
        if loader:
            try:
                return loader.load_prompt('academic_note_generator', 'AN_T001')
            except Exception:
                pass
        return self.DEFAULT_NOTE_TEMPLATE
    
    def _load_generation_prompt(self, **kwargs) -> str:
        """加载并渲染笔记生成提示词"""
        template = self._get_prompt_template()
        if template:
            try:
                return template.load_template('academic_note_generator', 'AN_U001', **kwargs)
            except Exception:
                pass
        return None
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.test_mode:
            return None
            
        if self.llm_client is None:
            provider = self.provider_mapping.get(self.api_provider, 'dashscope')
            
            config = self._create_provider_config(provider)
            self.llm_client = create_llm_client(config)
    
    def _create_provider_config(self, provider: str) -> Dict[str, Any]:
        """创建provider配置字典"""
        configs = {
            'dashscope': {
                'provider': 'dashscope',
                'model': 'qwen-turbo',
                'api_key': os.getenv('DASHSCOPE_API_KEY'),
                'base_url': 'https://dashscope.aliyuncs.com/api/v1'
            },
            'minimax': {
                'provider': 'minimax',
                'model': 'abab6-chat',
                'api_key': os.getenv('MINIMAX_API_KEY'),
                'base_url': 'https://api.minimax.chat/v1'
            },
            'openai': {
                'provider': 'openai',
                'model': 'gpt-4',
                'api_key': os.getenv('OPENAI_API_KEY'),
                'base_url': None
            }
        }
        
        return configs.get(provider, configs['dashscope'])

    def generate_reading_note(self, text: str, metadata: Optional[Dict[str, Any]] = None,
                              custom_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        生成学术阅读笔记
        
        Args:
            text: 学术文献文本内容
            metadata: 文献元数据（标题、作者、年份等）
            custom_prompt: 自定义提示词
            
        Returns:
            dict: 包含笔记内容和实体信息的字典
        """
        metadata = metadata or {}
        
        if self.test_mode:
            return self._generate_mock_note(text, metadata)
        
        self._init_llm_client()
        
        system_prompt = custom_prompt or self._load_system_prompt()
        
        prompt = self._build_generation_prompt(text, metadata)
        
        response = self._call_llm(system_prompt, prompt)
        
        return self._parse_llm_response(response, metadata)

    def extract_entities(self, text: str, entity_types: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """
        从文本中提取指定类型的实体
        
        Args:
            text: 待分析的文本
            entity_types: 要提取的实体类型列表
            
        Returns:
            dict: 按类型分类的实体字典
        """
        if self.test_mode:
            return self._extract_mock_entities(text, entity_types)
        
        self._init_llm_client()
        
        entity_types = entity_types or list(self.ENTITY_TYPES.keys())
        
        prompt = f"""请从以下文本中提取指定的实体类型。

实体类型说明：
- person: 历史人物、学者、思想家等
- location: 国家、城市、地区、机构所在地等
- event: 历史事件、会议、运动、战争等
- concept: 学术术语、理论、主义、思想等
- literature: 著作、论文、史料、档案等

待分析文本：
{text}

请以JSON格式输出，格式如下：
{{
    "person": ["人物1", "人物2"],
    "location": ["地名1", "地名2"],
    "event": ["事件1", "事件2"],
    "concept": ["概念1", "概念2"],
    "literature": ["文献1", "文献2"]
}}
"""
        
        system_prompt = self._load_system_prompt()
        response = self._call_llm(system_prompt, prompt)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return self._parse_entities_from_text(response)

    def build_knowledge_graph(self, entities: Dict[str, List[str]], 
                             relationships: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        构建知识图谱节点数据
        
        Args:
            entities: 提取的实体字典
            relationships: 实体间关系列表
            
        Returns:
            dict: 知识图谱数据
        """
        nodes = []
        links = []
        node_id_map = {}
        
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                entity_id = self._generate_entity_id(entity)
                node_id_map[entity] = entity_id
                
                nodes.append({
                    'id': entity_id,
                    'label': entity,
                    'type': entity_type,
                    'category': self.ENTITY_TYPES.get(entity_type, entity_type)
                })
        
        if relationships:
            for rel in relationships:
                source = rel.get('source')
                target = rel.get('target')
                relation_type = rel.get('type', 'related_to')
                
                if source in node_id_map and target in node_id_map:
                    links.append({
                        'source': node_id_map[source],
                        'target': node_id_map[target],
                        'type': relation_type,
                        'label': rel.get('label', relation_type)
                    })
        
        return {
            'nodes': nodes,
            'links': links,
            'stats': {
                'total_nodes': len(nodes),
                'total_links': len(links),
                'entity_types': {k: len(v) for k, v in entities.items()}
            }
        }

    def apply_note_template(self, content: Dict[str, Any], 
                           template: Optional[str] = None) -> str:
        """
        应用笔记模板生成最终Markdown
        
        Args:
            content: 笔记内容字典
            template: 自定义模板
            
        Returns:
            str: 格式化的Markdown文本
        """
        template = template or self.DEFAULT_NOTE_TEMPLATE
        
        subject_tag = content.get('subject_tag', '日本史')
        created_date = content.get('created_date', datetime.now().strftime('%Y-%m-%d'))
        source_title = content.get('source_title', 'Unknown')
        
        chapter_outline = self._format_chapter_outline(content.get('chapters', []))
        
        knowledge_graph = self._format_knowledge_graph(content.get('entities', {}))
        
        note_content = template.format(
            title=content.get('title', 'Untitled'),
            summary=content.get('summary', ''),
            chapter_outline=chapter_outline,
            knowledge_graph=knowledge_graph,
            created_date=created_date,
            source_title=source_title,
            subject_tag=subject_tag,
            authors=content.get('authors', 'Unknown'),
            year=content.get('year', 'Unknown'),
            keywords=', '.join(content.get('keywords', []))
        )
        
        return note_content

    def create_bidirectional_links(self, text: str, entities: Dict[str, List[str]]) -> str:
        """
        在文本中创建双向链接
        
        Args:
            text: 原始文本
            entities: 实体字典
            
        Returns:
            str: 添加了双向链接的文本
        """
        linked_text = text
        
        all_entities = []
        for entity_list in entities.values():
            all_entities.extend(entity_list)
        
        all_entities.sort(key=len, reverse=True)
        
        for entity in all_entities:
            if entity in linked_text:
                linked_text = linked_text.replace(
                    entity, 
                    f'[[{entity}]]'
                )
        
        return linked_text

    def batch_process(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量处理多个文档
        
        Args:
            documents: 文档列表，每个文档包含text和metadata
            
        Returns:
            list: 处理结果列表
        """
        results = []
        
        for doc in documents:
            text = doc.get('text', '')
            metadata = doc.get('metadata', {})
            
            result = self.generate_reading_note(text, metadata)
            results.append(result)
        
        return results

    def _build_generation_prompt(self, text: str, metadata: Dict[str, Any]) -> str:
        """构建生成提示词"""
        title = metadata.get('title', '未知标题')
        authors = metadata.get('authors', '未知作者')
        year = metadata.get('year', '未知年份')
        
        prompt = f"""请为以下学术文献生成结构化的Obsidian阅读笔记。

【文献信息】
- 标题：{title}
- 作者：{authors}
- 年份：{year}

【文献内容】
{text[:8000]}

【输出要求】
请严格按照以下JSON格式输出：
{{
    "summary": "总体摘要（300字左右，包含双向链接）",
    "chapters": [
        {{
            "title": "章节标题",
            "main_points": ["核心论点1（含双向链接）", "核心论点2"]
        }}
    ],
    "entities": {{
        "person": ["人物1", "人物2"],
        "location": ["地名1", "地名2"],
        "event": ["事件1", "事件2"],
        "concept": ["概念1", "概念2"],
        "literature": ["文献1", "文献2"]
    }},
    "keywords": ["关键词1", "关键词2", "关键词3"]
}}
"""
        return prompt

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用LLM API"""
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            result = self.llm_client._call_llm(full_prompt, temperature=0.3)
            return result.get('content', '')
        except Exception as e:
            raise RuntimeError(f"LLM API调用失败: {str(e)}")

    def _parse_llm_response(self, response: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            data = self._parse_json_from_text(response)
        
        content = {
            'title': metadata.get('title', '未知标题'),
            'summary': data.get('summary', ''),
            'chapters': data.get('chapters', []),
            'entities': data.get('entities', {}),
            'keywords': data.get('keywords', []),
            'authors': metadata.get('authors', ''),
            'year': metadata.get('year', ''),
            'created_date': datetime.now().strftime('%Y-%m-%d'),
            'source_title': metadata.get('title', '')
        }
        
        content['markdown'] = self.apply_note_template(content)
        
        return content

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取JSON"""
        json_pattern = r'\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        return {}

    def _parse_entities_from_text(self, text: str) -> Dict[str, List[str]]:
        """从文本中解析实体"""
        entities = {
            'person': [],
            'location': [],
            'event': [],
            'concept': [],
            'literature': []
        }
        
        current_type = None
        for line in text.split('\n'):
            line = line.strip()
            
            if 'person' in line.lower() or '人名' in line or '人物' in line:
                current_type = 'person'
            elif 'location' in line.lower() or '地名' in line or '地点' in line:
                current_type = 'location'
            elif 'event' in line.lower() or '事件' in line:
                current_type = 'event'
            elif 'concept' in line.lower() or '概念' in line or '术语' in line:
                current_type = 'concept'
            elif 'literature' in line.lower() or '文献' in line or '著作' in line:
                current_type = 'literature'
            elif line.startswith('-') or line.startswith('*'):
                entity = line.lstrip('-* ').strip()
                if current_type and entity:
                    entities[current_type].append(entity)
        
        return entities

    def _format_chapter_outline(self, chapters: List[Dict]) -> str:
        """格式化章节脉络"""
        if not chapters:
            return "无章节信息"
        
        outline = []
        for i, chapter in enumerate(chapters, 1):
            title = chapter.get('title', f'章节{i}')
            points = chapter.get('main_points', [])
            
            outline.append(f"### {title}")
            for point in points:
                outline.append(f"- {point}")
            outline.append("")
        
        return "\n".join(outline)

    def _format_knowledge_graph(self, entities: Dict[str, List[str]]) -> str:
        """格式化知识图谱"""
        if not entities:
            return "无实体信息"
        
        graph = []
        
        type_labels = {
            'person': '👤 关键人物',
            'location': '🌍 重要地名',
            'event': '⏳ 历史事件',
            'concept': '💡 核心概念',
            'literature': '📚 核心文献'
        }
        
        for entity_type, entity_list in entities.items():
            if entity_list:
                label = type_labels.get(entity_type, entity_type)
                entities_str = ', '.join([f'[[{e}]]' for e in entity_list[:10]])
                if len(entity_list) > 10:
                    entities_str += f' ... (共{len(entity_list)}个)'
                graph.append(f"- **{label}**：{entities_str}")
        
        return "\n".join(graph) if graph else "无实体信息"

    def _generate_entity_id(self, entity: str) -> str:
        """生成实体唯一ID"""
        hash_obj = hashlib.md5(entity.encode('utf-8'))
        return f"node_{hash_obj.hexdigest()[:8]}"

    def _generate_mock_note(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """生成模拟笔记数据（测试模式）"""
        title = metadata.get('title', '测试文献标题')
        authors = metadata.get('authors', '测试作者')
        year = metadata.get('year', '2024')
        
        mock_entities = {
            'person': ['丸山真男', '福泽谕吉', '霍布斯'],
            'location': ['东京', '京都', '明治日本'],
            'event': ['明治维新', '甲午战争', '大正民主'],
            'concept': ['国体论', '超国家主义', '文明开化'],
            'literature': ['《日本政治思想史研究》', '《文明论概略》']
        }
        
        mock_chapters = [
            {
                'title': '第一章 近代日本政治思想的形成',
                'main_points': [
                    '探讨了[[丸山真男]]对[[明治日本]]政治思想的影响',
                    '分析了[[国体论]]在近代日本的传播',
                    '批判了[[超国家主义]]的思想根源'
                ]
            },
            {
                'title': '第二章 西方政治思想的接受与转化',
                'main_points': [
                    '论述[[福泽谕吉]]的[[文明论]]思想',
                    '分析[[霍布斯]]政治哲学的东渐',
                    '考察[[明治维新]]对政治思想的影响'
                ]
            }
        ]
        
        content = {
            'title': title,
            'summary': f'''本文探讨了近代日本政治思想的形成与发展。研究的核心问题是[[明治日本]]如何在接受西方政治思想的过程中形成独特的政治哲学体系。

文章首先分析了[[丸山真男]]对[[国体论]]的批判性研究，指出[[超国家主义]]的思想根源在于对传统政治概念的错误理解。其次，通过考察[[福泽谕吉]]的《[[文明论概略]]》，揭示了[[文明开化]]运动在日本政治思想现代化中的关键作用。研究方法上，本文采用了思想史与政治哲学相结合的综合视角。

研究表明，近代日本政治思想的形成是一个复杂的本土化过程，既吸收了[[霍布斯]]等西方政治哲学家的思想，又保留了传统[[国体论]]的某些核心概念。这一研究对于理解当代日本政治思想史具有重要的参考价值。''',
            'chapters': mock_chapters,
            'entities': mock_entities,
            'keywords': ['日本政治思想', '丸山真男', '国体论', '明治维新', '文明开化'],
            'authors': authors,
            'year': year,
            'created_date': datetime.now().strftime('%Y-%m-%d'),
            'source_title': title
        }
        
        content['markdown'] = self.apply_note_template(content)
        
        return content

    def _extract_mock_entities(self, text: str, 
                              entity_types: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """提取模拟实体数据（测试模式）"""
        entity_types = entity_types or list(self.ENTITY_TYPES.keys())
        
        mock_entities = {
            'person': ['丸山真男', '福泽谕吉', '霍布斯', '洛克', '卢梭'],
            'location': ['东京', '京都', '大阪', '明治日本', '江户'],
            'event': ['明治维新', '甲午战争', '日俄战争', '大正民主', '战后改革'],
            'concept': ['国体论', '超国家主义', '文明开化', '实学', '独立自尊'],
            'literature': ['《日本政治思想史研究》', '《文明论概略》', '《西洋事情》']
        }
        
        return {k: v for k, v in mock_entities.items() if k in entity_types}


def create_academic_note_generator(api_provider: str = "qwen", 
                                   test_mode: bool = True) -> 'AcademicNoteGenerator':
    """
    工厂函数：创建学术笔记生成器实例
    
    Args:
        api_provider: API提供商
        test_mode: 是否使用测试模式
        
    Returns:
        AcademicNoteGenerator: 配置好的生成器实例
    """
    return AcademicNoteGenerator(api_provider=api_provider, test_mode=test_mode)
