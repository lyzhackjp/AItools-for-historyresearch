"""
历史实体词典版本管理器

提供词典的版本管理、加载、更新和备份功能。

功能特性：
- 版本管理：追踪词典的变更历史
- 自动备份：保存词典的历史版本
- 增量更新：支持增量添加新实体
- 版本回滚：支持回滚到历史版本
- 统计报告：提供词典统计信息

使用示例：
```python
from data.dictionaries.historical_entities_manager import DictionaryManager

manager = DictionaryManager()
manager.load_dictionary()

# 获取统计信息
stats = manager.get_statistics()
print(f"总实体数: {stats['total_entities']}")

# 添加新实体
manager.add_entity('person', ' новый人物', '新人物说明')

# 保存更改
manager.save()

# 备份当前版本
manager.backup()
```

作者：AI Assistant
日期：2026-03-29
版本：1.0
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any


class DictionaryManager:
    """历史实体词典管理器"""
    
    DEFAULT_DICTIONARY_PATH = Path(__file__).parent / 'historical_entities.json'
    BACKUP_DIR = Path(__file__).parent / 'backups'
    
    def __init__(self, dictionary_path: Optional[str] = None):
        """
        初始化词典管理器
        
        Args:
            dictionary_path: 词典文件路径，默认为historical_entities.json
        """
        self.dictionary_path = Path(dictionary_path) if dictionary_path else self.DEFAULT_DICTIONARY_PATH
        self.dictionary = {}
        self.metadata = {
            'version': '1.0',
            'last_updated': None,
            'last_modified_by': None
        }
        
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    def load_dictionary(self) -> Dict[str, Any]:
        """
        加载词典
        
        Returns:
            Dict[str, Any]: 词典内容
        """
        if not self.dictionary_path.exists():
            print(f"词典文件不存在: {self.dictionary_path}")
            return self.dictionary
        
        try:
            with open(self.dictionary_path, 'r', encoding='utf-8') as f:
                self.dictionary = json.load(f)
            
            self.metadata = self.dictionary.get('_metadata', {
                'version': '1.0',
                'last_updated': datetime.now().isoformat()
            })
            
            return self.dictionary
        except Exception as e:
            print(f"加载词典失败: {e}")
            return {}
    
    def save(self, dictionary: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存词典
        
        Args:
            dictionary: 要保存的词典内容
            
        Returns:
            bool: 保存是否成功
        """
        if dictionary:
            self.dictionary = dictionary
        
        self.metadata['last_updated'] = datetime.now().isoformat()
        self.dictionary['_metadata'] = self.metadata
        
        try:
            with open(self.dictionary_path, 'w', encoding='utf-8') as f:
                json.dump(self.dictionary, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存词典失败: {e}")
            return False
    
    def backup(self) -> Optional[str]:
        """
        备份当前词典版本
        
        Returns:
            Optional[str]: 备份文件路径
        """
        if not self.dictionary:
            self.load_dictionary()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.BACKUP_DIR / f"historical_entities_{timestamp}.json"
        
        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(self.dictionary, f, ensure_ascii=False, indent=2)
            return str(backup_path)
        except Exception as e:
            print(f"备份失败: {e}")
            return None
    
    def restore(self, backup_path: str) -> bool:
        """
        从备份恢复词典
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            bool: 恢复是否成功
        """
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            print(f"备份文件不存在: {backup_path}")
            return False
        
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                self.dictionary = json.load(f)
            
            self.save()
            return True
        except Exception as e:
            print(f"恢复失败: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取词典统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        if not self.dictionary:
            self.load_dictionary()
        
        categories = self.dictionary.get('categories', {})
        
        stats = {
            'total_entities': 0,
            'categories': {},
            'metadata': self.metadata
        }
        
        for category, data in categories.items():
            if isinstance(data, dict):
                entities = data.get('entities', [])
            elif isinstance(data, list):
                entities = data
            else:
                entities = []
            
            stats['categories'][category] = len(entities)
            stats['total_entities'] += len(entities)
        
        return stats
    
    def add_entity(self, category: str, entity: str, description: str = '') -> bool:
        """
        添加新实体
        
        Args:
            category: 实体类别
            entity: 实体名称
            description: 实体描述
            
        Returns:
            bool: 添加是否成功
        """
        if not self.dictionary:
            self.load_dictionary()
        
        if 'categories' not in self.dictionary:
            self.dictionary['categories'] = {}
        
        if category not in self.dictionary['categories']:
            self.dictionary['categories'][category] = {
                'description': '',
                'entities': []
            }
        
        categories_data = self.dictionary['categories'][category]
        
        if isinstance(categories_data, dict):
            if 'entities' not in categories_data:
                categories_data['entities'] = []
            
            if entity not in categories_data['entities']:
                categories_data['entities'].append(entity)
        elif isinstance(categories_data, list):
            if entity not in categories_data:
                categories_data.append(entity)
        
        return self.save()
    
    def remove_entity(self, category: str, entity: str) -> bool:
        """
        移除实体
        
        Args:
            category: 实体类别
            entity: 实体名称
            
        Returns:
            bool: 移除是否成功
        """
        if not self.dictionary:
            self.load_dictionary()
        
        categories = self.dictionary.get('categories', {})
        
        if category not in categories:
            return False
        
        categories_data = categories[category]
        
        if isinstance(categories_data, dict):
            entities = categories_data.get('entities', [])
            if entity in entities:
                entities.remove(entity)
        elif isinstance(categories_data, list):
            if entity in categories_data:
                categories_data.remove(entity)
        
        return self.save()
    
    def search_entity(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索实体
        
        Args:
            query: 搜索关键词
            
        Returns:
            List[Dict[str, Any]]: 搜索结果
        """
        if not self.dictionary:
            self.load_dictionary()
        
        results = []
        categories = self.dictionary.get('categories', {})
        
        for category, data in categories.items():
            if isinstance(data, dict):
                entities = data.get('entities', [])
            elif isinstance(data, list):
                entities = data
            else:
                entities = []
            
            for entity in entities:
                if query.lower() in entity.lower():
                    results.append({
                        'entity': entity,
                        'category': category
                    })
        
        return results
    
    def export_to_csv(self, output_path: str) -> bool:
        """
        导出词典为CSV格式
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            bool: 导出是否成功
        """
        if not self.dictionary:
            self.load_dictionary()
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('类别,实体\n')
                
                categories = self.dictionary.get('categories', {})
                for category, data in categories.items():
                    if isinstance(data, dict):
                        entities = data.get('entities', [])
                    elif isinstance(data, list):
                        entities = data
                    else:
                        entities = []
                    
                    for entity in entities:
                        f.write(f'{category},{entity}\n')
            
            return True
        except Exception as e:
            print(f"导出失败: {e}")
            return False
    
    def get_backup_list(self) -> List[Dict[str, Any]]:
        """
        获取备份文件列表
        
        Returns:
            List[Dict[str, Any]]: 备份文件列表
        """
        backups = []
        
        for backup_file in self.BACKUP_DIR.glob('historical_entities_*.json'):
            stat = backup_file.stat()
            backups.append({
                'path': str(backup_file),
                'name': backup_file.name,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        backups.sort(key=lambda x: x['modified'], reverse=True)
        return backups


if __name__ == '__main__':
    print("历史实体词典管理器测试")
    print("=" * 60)
    
    manager = DictionaryManager()
    
    print("\n1. 加载词典:")
    manager.load_dictionary()
    stats = manager.get_statistics()
    print(f"   总实体数: {stats['total_entities']}")
    print(f"   类别分布: {stats['categories']}")
    
    print("\n2. 搜索实体:")
    results = manager.search_entity('伊藤')
    print(f"   找到 {len(results)} 个相关实体:")
    for result in results[:5]:
        print(f"   - {result['entity']} ({result['category']})")
    
    print("\n3. 备份词典:")
    backup_path = manager.backup()
    if backup_path:
        print(f"   备份成功: {backup_path}")
    
    print("\n4. 备份列表:")
    backups = manager.get_backup_list()
    print(f"   共有 {len(backups)} 个备份文件")
    
    print("\n5. 导出CSV:")
    csv_path = manager.dictionary_path.parent / 'historical_entities.csv'
    if manager.export_to_csv(str(csv_path)):
        print(f"   导出成功: {csv_path}")
    
    print("\n测试完成！")
