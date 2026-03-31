"""
学术笔记生成器 - 优化版

专为历史研究设计的智能笔记生成工具

优化内容 (v2.0.0):
- 添加Markdown模板系统
- 支持自定义模板
- 增加标签系统
- 支持多种笔记类型

核心功能：
- 智能笔记生成：基于文献内容自动生成结构化笔记
- Markdown模板：支持多种预设模板和自定义模板
- 标签系统：自动提取和添加标签
- 多种笔记类型：阅读笔记、研究笔记、会议笔记等

支持的笔记类型：
- reading_note: 阅读笔记
- research_note: 研究笔记
- meeting_note: 会议笔记
- literature_review: 文献综述
- concept_note: 概念笔记
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from string import Template


class NoteType(Enum):
    """笔记类型枚举"""
    READING_NOTE = 'reading_note'
    RESEARCH_NOTE = 'research_note'
    MEETING_NOTE = 'meeting_note'
    LITERATURE_REVIEW = 'literature_review'
    CONCEPT_NOTE = 'concept_note'


@dataclass
class NoteTag:
    """笔记标签数据类"""
    name: str
    category: str
    weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'category': self.category,
            'weight': self.weight
        }


@dataclass
class GeneratedNote:
    """生成的笔记数据类"""
    title: str
    content: str
    note_type: str
    tags: List[NoteTag] = field(default_factory=list)
    source: str = ""
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class MarkdownTemplates:
    """Markdown模板库"""
    
    TEMPLATES = {
        'reading_note': Template('''# ${title}

> **阅读笔记** | ${created_at}
> **来源**: ${source}

## 📖 文献信息

- **标题**: ${document_title}
- **作者**: ${author}
- **出版年份**: ${year}
- **关键词**: ${keywords}

## 📝 核心观点

${main_points}

## 💡 重要论据

${key_arguments}

## 🔍 研究方法

${methodology}

## 📚 参考文献

${references}

## 💭 个人思考

${personal_reflections}

---
**标签**: ${tags}
'''),
        
        'research_note': Template('''# ${title}

> **研究笔记** | ${created_at}

## 🎯 研究问题

${research_question}

## 📊 研究现状

${current_status}

## 🔬 研究发现

${findings}

## 💎 创新点

${innovations}

## ⚠️ 研究局限

${limitations}

## 🔮 后续方向

${future_directions}

## 📎 相关资料

${related_materials}

---
**标签**: ${tags}
'''),
        
        'meeting_note': Template('''# ${title}

> **会议笔记** | ${created_at}
> **会议时间**: ${meeting_time}
> **会议地点**: ${location}

## 👥 参会人员

${participants}

## 📋 会议议题

${agenda}

## 💬 讨论要点

${discussion_points}

## ✅ 决议事项

${decisions}

## 📌 待办事项

${action_items}

## 📎 附件

${attachments}

---
**标签**: ${tags}
'''),
        
        'literature_review': Template('''# ${title}

> **文献综述** | ${created_at}

## 📖 综述主题

${review_topic}

## 🔍 文献范围

${scope}

## 📚 主要文献

${main_literature}

## 🧩 理论框架

${theoretical_framework}

## 📊 研究趋势

${research_trends}

## 🔗 研究脉络

${research_lineage}

## ⚖️ 不同观点

${different_views}

## 🎯 研究空白

${research_gaps}

## 📝 总结与展望

${conclusion}

---
**标签**: ${tags}
'''),
        
        'concept_note': Template('''# ${title}

> **概念笔记** | ${created_at}

## 📌 概念定义

${definition}

## 📖 词源与演变

${etymology}

## 🔗 相关概念

${related_concepts}

## 📚 学术应用

${academic_usage}

## 🌐 历史语境

${historical_context}

## 💭 批判性思考

${critical_thinking}

## 📎 参考文献

${references}

---
**标签**: ${tags}
''')
    }
    
    @classmethod
    def get_template(cls, note_type: str) -> Template:
        """获取指定类型的模板"""
        return cls.TEMPLATES.get(note_type, cls.TEMPLATES['reading_note'])
    
    @classmethod
    def get_available_templates(cls) -> List[str]:
        """获取所有可用模板"""
        return list(cls.TEMPLATES.keys())
    
    @classmethod
    def add_custom_template(cls, name: str, template_str: str):
        """添加自定义模板"""
        cls.TEMPLATES[name] = Template(template_str)


class TagExtractor:
    """标签提取器"""
    
    DEFAULT_TAG_CATEGORIES = {
        'period': ['明治时期', '大正时期', '昭和时期', '幕末', '江户时代', '战国时代'],
        'region': ['日本', '中国', '朝鲜', '东亚', '西方'],
        'topic': ['政治', '经济', '社会', '文化', '思想', '外交', '军事'],
        'method': ['比较研究', '概念史', '社会史', '思想史', '文献研究'],
        'concept': ['近代化', '民族主义', '天皇制', '民主', '自由', '权利']
    }
    
    def __init__(self, custom_tags: Optional[Dict[str, List[str]]] = None):
        """
        初始化标签提取器
        
        Args:
            custom_tags: 自定义标签字典
        """
        self.tag_categories = self.DEFAULT_TAG_CATEGORIES.copy()
        if custom_tags:
            for category, tags in custom_tags.items():
                if category in self.tag_categories:
                    self.tag_categories[category].extend(tags)
                else:
                    self.tag_categories[category] = tags
    
    def extract_tags(self, text: str, max_tags: int = 10) -> List[NoteTag]:
        """
        从文本中提取标签
        
        Args:
            text: 输入文本
            max_tags: 最大标签数量
            
        Returns:
            list: 提取的标签列表
        """
        found_tags = []
        text_lower = text.lower()
        
        for category, tags in self.tag_categories.items():
            for tag in tags:
                if tag in text or tag.lower() in text_lower:
                    weight = self._calculate_weight(text, tag)
                    found_tags.append(NoteTag(
                        name=tag,
                        category=category,
                        weight=weight
                    ))
        
        found_tags.sort(key=lambda x: x.weight, reverse=True)
        return found_tags[:max_tags]
    
    def _calculate_weight(self, text: str, tag: str) -> float:
        """计算标签权重"""
        count = text.count(tag) + text.lower().count(tag.lower())
        position_bonus = 1.5 if tag in text[:500] else 1.0
        return count * position_bonus
    
    def add_tag_category(self, category: str, tags: List[str]):
        """添加标签类别"""
        if category in self.tag_categories:
            self.tag_categories[category].extend(tags)
        else:
            self.tag_categories[category] = tags


class AcademicNoteGeneratorOptimized:
    """学术笔记生成器 - 优化版"""
    
    DEFAULT_SYSTEM_PROMPT = """你是一位专业的学术研究助理，擅长为历史研究文献生成结构化的学术笔记。

【任务说明】
请根据给定的文献内容，生成一份结构清晰、内容准确的学术笔记。

【笔记要求】
1. 准确提炼核心观点和论据
2. 保留重要的史实和数据
3. 梳理清晰的逻辑结构
4. 使用学术规范的语言
5. 标注关键概念和术语

【输出格式】
请以JSON格式输出笔记内容：
{
    "title": "笔记标题",
    "main_points": "核心观点内容",
    "key_arguments": "重要论据内容",
    "methodology": "研究方法内容",
    "references": "参考文献内容",
    "personal_reflections": "个人思考内容",
    "keywords": ["关键词1", "关键词2"],
    "suggested_tags": ["标签1", "标签2"]
}"""

    def __init__(self, llm_client=None, 
                 template_dir: Optional[str] = None,
                 custom_tags: Optional[Dict[str, List[str]]] = None):
        """
        初始化笔记生成器
        
        Args:
            llm_client: LLM客户端
            template_dir: 自定义模板目录
            custom_tags: 自定义标签字典
        """
        self.llm_client = llm_client
        self.template_dir = Path(template_dir) if template_dir else None
        self.templates = MarkdownTemplates()
        self.tag_extractor = TagExtractor(custom_tags)
        self.custom_templates = {}
        
        if self.template_dir and self.template_dir.exists():
            self._load_custom_templates()
    
    def _load_custom_templates(self):
        """加载自定义模板"""
        for template_file in self.template_dir.glob('*.md'):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                template_name = template_file.stem
                self.templates.add_custom_template(template_name, template_content)
                self.custom_templates[template_name] = True
            except Exception as e:
                print(f"警告: 加载模板 {template_file} 失败: {e}")
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.llm_client is None:
            from modules.llm_client import create_llm_client
            self.llm_client = create_llm_client({'provider': 'dashscope'})
    
    def generate_note(self, content: str,
                     note_type: str = 'reading_note',
                     source_info: Optional[Dict[str, str]] = None,
                     custom_template: Optional[str] = None) -> GeneratedNote:
        """
        生成学术笔记
        
        Args:
            content: 文献内容
            note_type: 笔记类型
            source_info: 来源信息
            custom_template: 自定义模板名称
            
        Returns:
            GeneratedNote: 生成的笔记
        """
        self._init_llm_client()
        
        source_info = source_info or {}
        
        prompt = f"""请为以下文献内容生成学术笔记：

【文献内容】
{content[:3000]}

【来源信息】
标题: {source_info.get('title', '未知')}
作者: {source_info.get('author', '未知')}

请按JSON格式输出笔记内容："""
        
        try:
            response = self.llm_client._call_llm(prompt, temperature=0.3)
            result_text = response.get('content', '')
            
            try:
                note_data = json.loads(self._extract_json(result_text))
            except json.JSONDecodeError:
                note_data = {
                    'title': source_info.get('title', '未命名笔记'),
                    'main_points': result_text,
                    'key_arguments': '',
                    'methodology': '',
                    'references': '',
                    'personal_reflections': '',
                    'keywords': [],
                    'suggested_tags': []
                }
            
            tags = self.tag_extractor.extract_tags(content)
            
            for suggested_tag in note_data.get('suggested_tags', []):
                tags.append(NoteTag(
                    name=suggested_tag,
                    category='auto',
                    weight=0.8
                ))
            
            template_vars = {
                'title': note_data.get('title', source_info.get('title', '未命名笔记')),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'source': source_info.get('source', ''),
                'document_title': source_info.get('title', ''),
                'author': source_info.get('author', ''),
                'year': source_info.get('year', ''),
                'keywords': ', '.join(note_data.get('keywords', [])),
                'main_points': note_data.get('main_points', ''),
                'key_arguments': note_data.get('key_arguments', ''),
                'methodology': note_data.get('methodology', ''),
                'references': note_data.get('references', ''),
                'personal_reflections': note_data.get('personal_reflections', ''),
                'tags': self._format_tags(tags)
            }
            
            template_vars.update(self._get_type_specific_vars(note_type, note_data))
            
            template_name = custom_template or note_type
            template = self.templates.get_template(template_name)
            
            note_content = template.safe_substitute(template_vars)
            
            return GeneratedNote(
                title=template_vars['title'],
                content=note_content,
                note_type=note_type,
                tags=tags[:10],
                source=source_info.get('source', ''),
                created_at=datetime.now().isoformat(),
                metadata={
                    'keywords': note_data.get('keywords', []),
                    'template_used': template_name
                }
            )
            
        except Exception as e:
            print(f"笔记生成失败: {e}")
            return GeneratedNote(
                title=source_info.get('title', '生成失败'),
                content=f"笔记生成失败: {str(e)}",
                note_type=note_type,
                source=source_info.get('source', ''),
                created_at=datetime.now().isoformat()
            )
    
    def _get_type_specific_vars(self, note_type: str, note_data: Dict) -> Dict[str, str]:
        """获取特定笔记类型的模板变量"""
        common_vars = {
            'research_question': note_data.get('research_question', '暂无'),
            'current_status': note_data.get('current_status', '暂无'),
            'findings': note_data.get('findings', '暂无'),
            'innovations': note_data.get('innovations', '暂无'),
            'limitations': note_data.get('limitations', '暂无'),
            'future_directions': note_data.get('future_directions', '暂无'),
            'related_materials': note_data.get('related_materials', '暂无'),
            'meeting_time': note_data.get('meeting_time', '暂无'),
            'location': note_data.get('location', '暂无'),
            'participants': note_data.get('participants', '暂无'),
            'agenda': note_data.get('agenda', '暂无'),
            'discussion_points': note_data.get('discussion_points', '暂无'),
            'decisions': note_data.get('decisions', '暂无'),
            'action_items': note_data.get('action_items', '暂无'),
            'attachments': note_data.get('attachments', '暂无'),
            'review_topic': note_data.get('review_topic', '暂无'),
            'scope': note_data.get('scope', '暂无'),
            'main_literature': note_data.get('main_literature', '暂无'),
            'theoretical_framework': note_data.get('theoretical_framework', '暂无'),
            'research_trends': note_data.get('research_trends', '暂无'),
            'research_lineage': note_data.get('research_lineage', '暂无'),
            'different_views': note_data.get('different_views', '暂无'),
            'research_gaps': note_data.get('research_gaps', '暂无'),
            'conclusion': note_data.get('conclusion', '暂无'),
            'definition': note_data.get('definition', '暂无'),
            'etymology': note_data.get('etymology', '暂无'),
            'related_concepts': note_data.get('related_concepts', '暂无'),
            'academic_usage': note_data.get('academic_usage', '暂无'),
            'historical_context': note_data.get('historical_context', '暂无'),
            'critical_thinking': note_data.get('critical_thinking', '暂无')
        }
        return common_vars
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON"""
        json_pattern = r'\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            if 'title' in match or 'main_points' in match:
                return match
        
        return text
    
    def _format_tags(self, tags: List[NoteTag]) -> str:
        """格式化标签为Markdown"""
        if not tags:
            return "暂无标签"
        
        tag_strs = [f"`{tag.name}`" for tag in tags[:10]]
        return " ".join(tag_strs)
    
    def save_note(self, note: GeneratedNote, output_path: str) -> str:
        """
        保存笔记到文件
        
        Args:
            note: 笔记对象
            output_path: 输出路径
            
        Returns:
            str: 保存的文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(note.content)
        
        return str(output_path)
    
    def add_custom_template(self, name: str, template_str: str):
        """
        添加自定义模板
        
        Args:
            name: 模板名称
            template_str: 模板内容
        """
        self.templates.add_custom_template(name, template_str)
        self.custom_templates[name] = True
    
    def get_available_templates(self) -> List[str]:
        """获取所有可用模板"""
        return self.templates.get_available_templates()
    
    def get_available_tags(self) -> Dict[str, List[str]]:
        """获取所有可用标签类别"""
        return self.tag_extractor.tag_categories.copy()


def create_academic_note_generator_optimized(
    llm_client=None,
    template_dir: Optional[str] = None,
    custom_tags: Optional[Dict[str, List[str]]] = None
) -> AcademicNoteGeneratorOptimized:
    """
    工厂函数 - 创建优化版学术笔记生成器
    
    Args:
        llm_client: LLM客户端
        template_dir: 自定义模板目录
        custom_tags: 自定义标签字典
        
    Returns:
        AcademicNoteGeneratorOptimized: 笔记生成器实例
    """
    return AcademicNoteGeneratorOptimized(llm_client, template_dir, custom_tags)


if __name__ == "__main__":
    print("学术笔记生成器 - 优化版 v2.0.0")
    print("="*60)
    print("\n可用模板:")
    templates = MarkdownTemplates.get_available_templates()
    for t in templates:
        print(f"  - {t}")
    
    print("\n使用方法:")
    print("```python")
    print("from modules.academic_note_generator_optimized import create_academic_note_generator_optimized")
    print("")
    print("# 创建生成器")
    print("generator = create_academic_note_generator_optimized()")
    print("")
    print("# 生成笔记")
    print("note = generator.generate_note(")
    print("    content='文献内容...',")
    print("    note_type='reading_note',")
    print("    source_info={'title': '文章标题', 'author': '作者'}")
    print(")")
    print("")
    print("# 保存笔记")
    print("generator.save_note(note, 'output/note.md')")
    print("```")
