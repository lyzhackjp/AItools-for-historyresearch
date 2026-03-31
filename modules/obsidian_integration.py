"""
Obsidian笔记系统集成模块

与Obsidian笔记系统深度集成，支持双向链接、知识图谱等功能
为学术研究提供现代化的知识管理能力

核心功能：
- 创建Obsidian vault并管理笔记
- 生成双向链接 [[链接]] 语法
- 应用自定义Eta模板格式化笔记
- 同步Zotero批注到Obsidian
- 构建知识图谱数据
- 批量导入Markdown文件

依赖模块：
- llm_client.py
- data_structurer.py
"""

import os
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import shutil


class ObsidianIntegration:
    """Obsidian笔记系统集成器"""
    
    DEFAULT_VAULT_SETTINGS = {
        'name': 'ResearchVault',
        'created': datetime.now().isoformat(),
        'plugins': {
            'daily_notes': False,
            'templates': False,
            'graph_view': True
        }
    }
    
    NOTE_TEMPLATES = {
        'reading_note': '''---
type: {note_type}
tags: [{tags}]
created: {created_date}
source: {source}
---

# {title}

## 摘要

{summary}

## 关键要点

{key_points}

## 双向链接

{backlinks}

## 元数据

- **作者**: {author}
- **年份**: {year}
- **主题**: {subject}

---

*由AI辅助生成 - {generation_date}*
''',
        'concept_note': '''---
type: concept
tags: [{tags}]
created: {created_date}
related_concepts: [{related}]
---

# {concept_name}

## 定义

{definition}

## 核心特征

{characteristics}

## 相关人物

{related_persons}

## 相关事件

{related_events}

## 应用场景

{applications}

## 参考文献

{references}
''',
        'person_note': '''---
type: person
tags: [{tags}]
birth: {birth_date}
death: {death_date}
era: {era}
occupation: {occupation}
---

# {person_name}

## 基本信息

- **出生**: {birth_date}
- **逝世**: {death_date}
- **时代**: {era}
- **身份**: {occupation}

## 生平简介

 biography}

## 主要贡献

{contributions}

## 代表作品

{works}

## 相关概念

{related_concepts}

## 历史评价

{historical_assessment}
'''
    }
    
    def __init__(self, vault_path: Optional[str] = None):
        """
        初始化Obsidian集成器
        
        Args:
            vault_path: Obsidian vault路径
        """
        self.vault_path = Path(vault_path) if vault_path else None
        self.current_vault = None
        
        self.settings = {}
        self.template_engine = 'eta'
    
    def create_vault(self, vault_name: str, 
                   vault_root: Optional[str] = None) -> bool:
        """
        创建新的Obsidian vault
        
        Args:
            vault_name: vault名称
            vault_root: vault根目录
            
        Returns:
            bool: 是否创建成功
        """
        if vault_root:
            base_path = Path(vault_root)
        else:
            base_path = Path.cwd()
        
        vault_path = base_path / vault_name
        
        try:
            vault_path.mkdir(parents=True, exist_ok=True)
            
            folders = ['Notes', 'Attachments', 'Templates', 'Scripts', 'Daily']
            for folder in folders:
                (vault_path / folder).mkdir(exist_ok=True)
            
            self.vault_path = vault_path
            self.current_vault = vault_name
            
            vault_settings = self.DEFAULT_VAULT_SETTINGS.copy()
            vault_settings['name'] = vault_name
            vault_settings['path'] = str(vault_path)
            
            with open(vault_path / '.obsidian' / 'vault.json', 'w', encoding='utf-8') as f:
                json.dump(vault_settings, f, ensure_ascii=False, indent=2)
            
            self.settings = vault_settings
            
            return True
        except Exception as e:
            print(f"创建vault失败: {e}")
            return False
    
    def open_vault(self, vault_path: str) -> bool:
        """
        打开现有的Obsidian vault
        
        Args:
            vault_path: vault路径
            
        Returns:
            bool: 是否打开成功
        """
        try:
            vault_path = Path(vault_path)
            
            if not vault_path.exists():
                return False
            
            self.vault_path = vault_path
            
            settings_file = vault_path / '.obsidian' / 'vault.json'
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            
            self.current_vault = self.settings.get('name', vault_path.name)
            
            return True
        except Exception as e:
            print(f"打开vault失败: {e}")
            return False
    
    def create_bidirectional_links(self, text: str, 
                                   entities: Dict[str, List[str]]) -> str:
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
    
    def apply_eta_template(self, template_name: str, 
                          context: Dict[str, Any]) -> str:
        """
        应用Eta模板格式化笔记
        
        Args:
            template_name: 模板名称
            context: 模板上下文
            
        Returns:
            str: 格式化后的笔记内容
        """
        if template_name not in self.NOTE_TEMPLATES:
            return ""
        
        template = self.NOTE_TEMPLATES[template_name]
        
        required_fields = ['title', 'created_date', 'tags']
        
        for field in required_fields:
            if field not in context:
                context[field] = 'N/A'
        
        try:
            formatted = template.format(**context)
            return formatted
        except KeyError as e:
            print(f"模板格式化失败: 缺少字段 {e}")
            return template
    
    def create_note(self, title: str, content: str,
                  note_type: str = 'note',
                  folder: Optional[str] = None) -> Tuple[bool, str]:
        """
        创建新笔记
        
        Args:
            title: 笔记标题
            content: 笔记内容
            note_type: 笔记类型
            folder: 存放文件夹
            
        Returns:
            Tuple[bool, str]: (是否成功, 文件路径或错误信息)
        """
        if self.vault_path is None:
            return False, "vault未初始化"
        
        try:
            safe_title = self._sanitize_filename(title)
            
            if folder:
                note_folder = self.vault_path / folder
            else:
                note_folder = self.vault_path / 'Notes'
            
            note_folder.mkdir(parents=True, exist_ok=True)
            
            filename = f"{safe_title}.md"
            filepath = note_folder / filename
            
            counter = 1
            while filepath.exists():
                filename = f"{safe_title}_{counter}.md"
                filepath = note_folder / filename
                counter += 1
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True, str(filepath)
        except Exception as e:
            return False, str(e)
    
    def read_note(self, note_path: str) -> Tuple[bool, str]:
        """
        读取笔记内容
        
        Args:
            note_path: 笔记路径（相对于vault或绝对路径）
            
        Returns:
            Tuple[bool, str]: (是否成功, 笔记内容或错误信息)
        """
        if self.vault_path is None:
            return False, "vault未初始化"
        
        try:
            note_path = Path(note_path)
            
            if not note_path.is_absolute():
                note_path = self.vault_path / note_path
            
            if not note_path.exists():
                return False, "笔记不存在"
            
            with open(note_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return True, content
        except Exception as e:
            return False, str(e)
    
    def update_note(self, note_path: str, new_content: str) -> bool:
        """
        更新笔记内容
        
        Args:
            note_path: 笔记路径
            new_content: 新内容
            
        Returns:
            bool: 是否更新成功
        """
        success, result = self.read_note(note_path)
        
        if not success:
            return False
        
        try:
            note_path = Path(note_path)
            
            if not note_path.is_absolute():
                note_path = self.vault_path / note_path
            
            with open(note_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True
        except Exception as e:
            print(f"更新笔记失败: {e}")
            return False
    
    def search_notes(self, query: str, 
                   search_type: str = 'content') -> List[Dict[str, Any]]:
        """
        搜索笔记
        
        Args:
            query: 搜索关键词
            search_type: 搜索类型 ('content', 'title', 'tags')
            
        Returns:
            list: 匹配的笔记列表
        """
        if self.vault_path is None:
            return []
        
        results = []
        
        try:
            for md_file in self.vault_path.rglob('*.md'):
                if '.obsidian' in str(md_file):
                    continue
                
                if search_type == 'title':
                    if query.lower() in md_file.stem.lower():
                        results.append({
                            'path': str(md_file.relative_to(self.vault_path)),
                            'title': md_file.stem,
                            'type': 'title_match'
                        })
                else:
                    try:
                        with open(md_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        if query.lower() in content.lower():
                            match_count = content.lower().count(query.lower())
                            
                            results.append({
                                'path': str(md_file.relative_to(self.vault_path)),
                                'title': md_file.stem,
                                'type': 'content_match',
                                'match_count': match_count
                            })
                    except:
                        continue
            
            return results
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
    
    def get_backlinks(self, note_title: str) -> List[Dict[str, str]]:
        """
        获取指向某笔记的反向链接
        
        Args:
            note_title: 笔记标题
            
        Returns:
            list: 反向链接列表
        """
        if self.vault_path is None:
            return []
        
        backlinks = []
        link_pattern = rf'\[\[{note_title}\]\]'
        
        try:
            for md_file in self.vault_path.rglob('*.md'):
                if '.obsidian' in str(md_file):
                    continue
                
                if md_file.stem == note_title:
                    continue
                
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    matches = re.findall(link_pattern, content)
                    
                    if matches:
                        backlinks.append({
                            'source': str(md_file.relative_to(self.vault_path)),
                            'source_title': md_file.stem,
                            'link_count': len(matches)
                        })
                except:
                    continue
            
            return backlinks
        except Exception as e:
            print(f"获取反向链接失败: {e}")
            return []
    
    def build_knowledge_graph_data(self) -> Dict[str, Any]:
        """
        构建知识图谱数据
        
        Returns:
            dict: 知识图谱数据
        """
        if self.vault_path is None:
            return {}
        
        nodes = []
        edges = []
        
        link_pattern = r'\[\[([^\]]+)\]\]'
        
        try:
            for md_file in self.vault_path.rglob('*.md'):
                if '.obsidian' in str(md_file):
                    continue
                
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    file_node = {
                        'id': md_file.stem,
                        'label': md_file.stem,
                        'type': 'note',
                        'path': str(md_file.relative_to(self.vault_path))
                    }
                    nodes.append(file_node)
                    
                    links = re.findall(link_pattern, content)
                    for link_target in links:
                        edges.append({
                            'source': md_file.stem,
                            'target': link_target,
                            'type': 'links_to'
                        })
                        
                        target_exists = any(
                            n['label'] == link_target for n in nodes
                        )
                        if not target_exists:
                            nodes.append({
                                'id': link_target,
                                'label': link_target,
                                'type': 'linked_note',
                                'exists': False
                            })
                
                except:
                    continue
            
            return {
                'nodes': nodes,
                'edges': edges,
                'stats': {
                    'total_nodes': len(nodes),
                    'total_edges': len(edges),
                    'notes_with_links': len(set(e['source'] for e in edges))
                }
            }
        except Exception as e:
            print(f"构建知识图谱失败: {e}")
            return {}
    
    def sync_zotero_annotations(self, annotations: List[Dict[str, Any]],
                               parent_note: str) -> bool:
        """
        同步Zotero批注到Obsidian
        
        Args:
            annotations: 批注列表
            parent_note: 父笔记标题
            
        Returns:
            bool: 是否同步成功
        """
        if self.vault_path is None:
            return False
        
        try:
            annotation_note = f"Annotations - {parent_note}"
            
            content_parts = [
                f"# {parent_note} - 批注",
                "",
                f"**批注数量**: {len(annotations)}",
                "",
                "---",
                ""
            ]
            
            for i, annot in enumerate(annotations, 1):
                annot_type = annot.get('type', 'highlight')
                annot_text = annot.get('text', '')
                annot_page = annot.get('page', '')
                annot_color = annot.get('color', '')
                
                if annot_type == 'highlight':
                    content_parts.append(f"### 批注 {i}")
                    content_parts.append(f"- 页面: {annot_page}")
                    content_parts.append(f"- 颜色: {annot_color}")
                    content_parts.append(f"> {annot_text}")
                    content_parts.append("")
                elif annot_type == 'note':
                    content_parts.append(f"### 笔记 {i}")
                    content_parts.append(f"> {annot_text}")
                    content_parts.append("")
            
            content = '\n'.join(content_parts)
            
            success, _ = self.create_note(
                annotation_note,
                content,
                note_type='annotations',
                folder='Annotations'
            )
            
            return success
        except Exception as e:
            print(f"同步批注失败: {e}")
            return False
    
    def import_markdown_files(self, source_dir: str,
                            target_folder: Optional[str] = None) -> Dict[str, Any]:
        """
        批量导入Markdown文件
        
        Args:
            source_dir: 源目录
            target_folder: 目标文件夹
            
        Returns:
            dict: 导入结果统计
        """
        if self.vault_path is None:
            return {'success': False, 'error': 'vault未初始化'}
        
        source_path = Path(source_dir)
        
        if not source_path.exists():
            return {'success': False, 'error': '源目录不存在'}
        
        imported = []
        failed = []
        
        try:
            for md_file in source_path.rglob('*.md'):
                try:
                    target_folder_path = self.vault_path / (target_folder or 'Imported')
                    target_folder_path.mkdir(parents=True, exist_ok=True)
                    
                    target_file = target_folder_path / md_file.name
                    
                    shutil.copy2(md_file, target_file)
                    imported.append(str(md_file.name))
                except Exception as e:
                    failed.append({'file': str(md_file.name), 'error': str(e)})
            
            return {
                'success': True,
                'imported_count': len(imported),
                'failed_count': len(failed),
                'imported_files': imported,
                'failed_files': failed
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def export_notes_to_json(self, output_path: str) -> bool:
        """
        导出笔记到JSON格式
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            bool: 是否导出成功
        """
        if self.vault_path is None:
            return False
        
        notes_data = []
        
        try:
            for md_file in self.vault_path.rglob('*.md'):
                if '.obsidian' in str(md_file):
                    continue
                
                try:
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    notes_data.append({
                        'title': md_file.stem,
                        'path': str(md_file.relative_to(self.vault_path)),
                        'content': content,
                        'links': re.findall(r'\[\[([^\]]+)\]\]', content)
                    })
                except:
                    continue
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'vault': self.current_vault,
                    'export_date': datetime.now().isoformat(),
                    'notes': notes_data
                }, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"导出失败: {e}")
            return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        filename = filename.strip('. ')
        
        return filename[:200]
    
    def get_vault_info(self) -> Dict[str, Any]:
        """
        获取vault信息
        
        Returns:
            dict: vault信息
        """
        if self.vault_path is None:
            return {'initialized': False}
        
        try:
            note_count = len(list(self.vault_path.rglob('*.md')))
            
            folders = [d.name for d in self.vault_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
            
            return {
                'initialized': True,
                'name': self.current_vault,
                'path': str(self.vault_path),
                'note_count': note_count,
                'folders': folders,
                'settings': self.settings
            }
        except Exception as e:
            return {'initialized': True, 'error': str(e)}


def create_obsidian_integration(vault_path: Optional[str] = None) -> ObsidianIntegration:
    """
    工厂函数：创建Obsidian集成器实例
    
    Args:
        vault_path: vault路径
        
    Returns:
        ObsidianIntegration: 配置好的集成器实例
    """
    return ObsidianIntegration(vault_path=vault_path)
