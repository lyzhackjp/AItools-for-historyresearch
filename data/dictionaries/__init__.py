"""
历史实体词典包

提供历史实体词典的加载、管理和版本控制功能。

主要模块：
- historical_entities.json: 主词典文件
- historical_entities_manager.py: 词典管理器
- __init__.py: 包初始化文件

使用示例：
```python
from data.dictionaries import DictionaryManager

manager = DictionaryManager()
manager.load_dictionary()

stats = manager.get_statistics()
print(f"总实体数: {stats['total_entities']}")
```

作者：AI Assistant
日期：2026-03-29
版本：1.0
"""

from .historical_entities_manager import DictionaryManager

__version__ = '1.0'
__all__ = ['DictionaryManager']
