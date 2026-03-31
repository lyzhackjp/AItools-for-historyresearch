"""
统一任务管理器

提供用户友好的接口来管理和执行各种任务
支持API和脚本两种执行模式的切换

核心功能：
- 统一的任务管理入口
- 模式切换（API/脚本）
- 任务预设配置
- 批量任务处理
- 结果导出

使用方法：
    from modules.task_manager import TaskManager
    
    # 创建任务管理器
    manager = TaskManager()
    
    # 设置执行模式
    manager.set_mode('api')  # 或 'script'
    
    # 执行任务
    result = manager.ner("伊藤博文是明治维新的重要人物...")
    
    # 使用自定义提示词
    result = manager.execute_with_prompt(
        task_type='ner',
        prompt="请识别以下文本中的所有历史人物：{text}",
        text="..."
    )
"""

import os
import json
from typing import Optional, Dict, List, Any, Union
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field

from modules.secure_api_key_manager import get_secure_key_manager, SecureAPIKeyManager
from modules.unified_task_executor import UnifiedTaskExecutor, TaskConfig, TaskResult, TaskType
from modules.module_adapters import (
    NERAdapter, AcademicNoteAdapter, PaperPolishAdapter,
    CitationAdapter, OCRAdapter, SummaryAdapter,
    StyleTransferAdapter, VirtualPersonaAdapter, EntityDisambiguationAdapter,
    create_adapter
)


@dataclass
class TaskPreset:
    """任务预设配置"""
    name: str
    task_type: str
    provider: str = "qwen"
    model: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 2000
    custom_prompt: Optional[str] = None
    description: str = ""


class TaskManager:
    """统一任务管理器"""
    
    DEFAULT_PRESETS = {
        'ner_quick': TaskPreset(
            name='ner_quick',
            task_type='ner',
            provider='qwen',
            temperature=0.1,
            max_tokens=1000,
            description='快速命名实体识别'
        ),
        'ner_detailed': TaskPreset(
            name='ner_detailed',
            task_type='ner',
            provider='qwen',
            temperature=0.1,
            max_tokens=2000,
            description='详细命名实体识别，包含上下文分析'
        ),
        'note_standard': TaskPreset(
            name='note_standard',
            task_type='academic_note',
            provider='qwen',
            temperature=0.3,
            max_tokens=3000,
            description='标准学术笔记生成'
        ),
        'polish_conservative': TaskPreset(
            name='polish_conservative',
            task_type='paper_polish',
            provider='qwen',
            temperature=0.2,
            max_tokens=4000,
            description='保守润色，保留原文风格'
        ),
        'polish_aggressive': TaskPreset(
            name='polish_aggressive',
            task_type='paper_polish',
            provider='qwen',
            temperature=0.5,
            max_tokens=4000,
            description='积极润色，大幅优化表达'
        ),
        'summary_short': TaskPreset(
            name='summary_short',
            task_type='text_summary',
            provider='qwen',
            temperature=0.3,
            max_tokens=500,
            description='简短摘要'
        ),
        'summary_detailed': TaskPreset(
            name='summary_detailed',
            task_type='text_summary',
            provider='qwen',
            temperature=0.3,
            max_tokens=1500,
            description='详细摘要'
        ),
        'ocr_correct': TaskPreset(
            name='ocr_correct',
            task_type='ocr_correction',
            provider='qwen',
            temperature=0.1,
            max_tokens=4000,
            description='OCR文本校正'
        ),
        'citation_gb': TaskPreset(
            name='citation_gb',
            task_type='citation_normalize',
            provider='qwen',
            temperature=0.1,
            max_tokens=1000,
            description='GB/T 7714引用格式'
        ),
    }
    
    def __init__(self, 
                 mode: str = "api",
                 provider: str = "qwen"):
        """
        初始化任务管理器
        
        Args:
            mode: 执行模式 ('api' 或 'script')
            provider: 默认API提供商
        """
        self._mode = mode
        self._provider = provider
        self.key_manager = get_secure_key_manager()
        self.executor = UnifiedTaskExecutor()
        self.executor.set_mode(mode)
        self.executor.set_provider(provider)
        
        self._adapters: Dict[str, Any] = {}
        self._presets: Dict[str, TaskPreset] = self.DEFAULT_PRESETS.copy()
        self._task_history: List[Dict[str, Any]] = []
        
        self._init_adapters()
    
    def _init_adapters(self):
        """初始化所有适配器"""
        self._adapters = {
            'ner': NERAdapter(mode=self._mode, provider=self._provider),
            'academic_note': AcademicNoteAdapter(mode=self._mode, provider=self._provider),
            'paper_polish': PaperPolishAdapter(mode=self._mode, provider=self._provider),
            'citation': CitationAdapter(mode=self._mode, provider=self._provider),
            'ocr': OCRAdapter(mode=self._mode, provider=self._provider),
            'summary': SummaryAdapter(mode=self._mode, provider=self._provider),
            'style_transfer': StyleTransferAdapter(mode=self._mode, provider=self._provider),
            'virtual_persona': VirtualPersonaAdapter(mode=self._mode, provider=self._provider),
            'entity_disambiguation': EntityDisambiguationAdapter(mode=self._mode, provider=self._provider),
        }
    
    @property
    def mode(self) -> str:
        """获取当前执行模式"""
        return self._mode
    
    def set_mode(self, mode: str):
        """
        设置执行模式
        
        Args:
            mode: 'api' 或 'script'
        """
        self._mode = mode
        self.executor.set_mode(mode)
        for adapter in self._adapters.values():
            adapter.set_mode(mode)
    
    @property
    def provider(self) -> str:
        """获取当前API提供商"""
        return self._provider
    
    def set_provider(self, provider: str):
        """
        设置API提供商
        
        Args:
            provider: 提供商名称 ('qwen', 'minimax', 'openai'等)
        """
        self._provider = provider
        self.executor.set_provider(provider)
        for adapter in self._adapters.values():
            adapter.set_provider(provider)
    
    def get_available_providers(self) -> List[str]:
        """获取可用的API提供商列表"""
        return ['qwen', 'minimax', 'openai', 'deepseek', 'zhipu', 'volcano']
    
    def get_available_tasks(self) -> List[str]:
        """获取可用的任务类型列表"""
        return list(self._adapters.keys())
    
    def get_presets(self) -> Dict[str, TaskPreset]:
        """获取所有预设配置"""
        return self._presets
    
    def add_preset(self, preset: TaskPreset):
        """添加预设配置"""
        self._presets[preset.name] = preset
    
    def remove_preset(self, name: str):
        """移除预设配置"""
        if name in self._presets and name not in self.DEFAULT_PRESETS:
            del self._presets[name]
    
    def _record_task(self, task_type: str, success: bool, execution_time: float):
        """记录任务执行"""
        self._task_history.append({
            'task_type': task_type,
            'mode': self._mode,
            'provider': self._provider,
            'success': success,
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat()
        })
    
    def ner(self, 
            text: str,
            categories: Optional[List[str]] = None,
            preset: Optional[str] = None,
            **kwargs) -> Dict[str, Any]:
        """
        命名实体识别
        
        Args:
            text: 待识别文本
            categories: 实体类型列表
            preset: 预设名称
            **kwargs: 其他参数
            
        Returns:
            识别结果
        """
        adapter = self._adapters['ner']
        
        if preset and preset in self._presets:
            preset_config = self._presets[preset]
            kwargs.update({
                'temperature': preset_config.temperature,
                'max_tokens': preset_config.max_tokens
            })
        
        result = adapter.recognize(text, categories, **kwargs)
        
        if 'execution_time' in result.get('metadata', {}):
            self._record_task('ner', result['success'], result['metadata']['execution_time'])
        
        return result
    
    def academic_note(self,
                     text: str,
                     source: str = "未知来源",
                     preset: Optional[str] = None,
                     **kwargs) -> Dict[str, Any]:
        """
        生成学术笔记
        
        Args:
            text: 源文本
            source: 来源信息
            preset: 预设名称
            **kwargs: 其他参数
            
        Returns:
            笔记内容
        """
        adapter = self._adapters['academic_note']
        
        if preset and preset in self._presets:
            preset_config = self._presets[preset]
            kwargs.update({
                'temperature': preset_config.temperature,
                'max_tokens': preset_config.max_tokens
            })
        
        result = adapter.generate(text, source, **kwargs)
        
        if 'execution_time' in result.get('metadata', {}):
            self._record_task('academic_note', result['success'], result['metadata']['execution_time'])
        
        return result
    
    def paper_polish(self,
                    text: str,
                    language: str = "zh",
                    preset: Optional[str] = None,
                    **kwargs) -> Dict[str, Any]:
        """
        论文润色
        
        Args:
            text: 待润色文本
            language: 语言
            preset: 预设名称
            **kwargs: 其他参数
            
        Returns:
            润色结果
        """
        adapter = self._adapters['paper_polish']
        
        if preset and preset in self._presets:
            preset_config = self._presets[preset]
            kwargs.update({
                'temperature': preset_config.temperature,
                'max_tokens': preset_config.max_tokens
            })
        
        result = adapter.polish(text, language, **kwargs)
        
        if 'execution_time' in result.get('metadata', {}):
            self._record_task('paper_polish', result['success'], result['metadata']['execution_time'])
        
        return result
    
    def citation_normalize(self,
                          citation: str,
                          target_style: str = "gb7714",
                          **kwargs) -> Dict[str, Any]:
        """
        引用规范化
        
        Args:
            citation: 引用文本
            target_style: 目标格式
            **kwargs: 其他参数
            
        Returns:
            规范化结果
        """
        adapter = self._adapters['citation']
        result = adapter.normalize(citation, target_style, **kwargs)
        
        if 'execution_time' in result.get('metadata', {}):
            self._record_task('citation_normalize', result['success'], result['metadata']['execution_time'])
        
        return result
    
    def ocr_correct(self,
                   text: str,
                   language: str = "zh",
                   preset: Optional[str] = None,
                   **kwargs) -> Dict[str, Any]:
        """
        OCR校正
        
        Args:
            text: OCR识别文本
            language: 语言
            preset: 预设名称
            **kwargs: 其他参数
            
        Returns:
            校正结果
        """
        adapter = self._adapters['ocr']
        
        if preset and preset in self._presets:
            preset_config = self._presets[preset]
            kwargs.update({
                'temperature': preset_config.temperature,
                'max_tokens': preset_config.max_tokens
            })
        
        result = adapter.correct(text, language, **kwargs)
        
        if 'execution_time' in result.get('metadata', {}):
            self._record_task('ocr_correction', result['success'], result['metadata']['execution_time'])
        
        return result
    
    def summarize(self,
                 text: str,
                 max_length: int = 200,
                 preset: Optional[str] = None,
                 **kwargs) -> Dict[str, Any]:
        """
        文本摘要
        
        Args:
            text: 源文本
            max_length: 最大长度
            preset: 预设名称
            **kwargs: 其他参数
            
        Returns:
            摘要结果
        """
        adapter = self._adapters['summary']
        
        if preset and preset in self._presets:
            preset_config = self._presets[preset]
            kwargs.update({
                'temperature': preset_config.temperature,
                'max_tokens': preset_config.max_tokens
            })
        
        result = adapter.summarize(text, max_length, **kwargs)
        
        if 'execution_time' in result.get('metadata', {}):
            self._record_task('text_summary', result['success'], result['metadata']['execution_time'])
        
        return result
    
    def style_transfer(self,
                      text: str,
                      target_style: str,
                      **kwargs) -> Dict[str, Any]:
        """
        文风迁移
        
        Args:
            text: 原文本
            target_style: 目标文风
            **kwargs: 其他参数
            
        Returns:
            迁移结果
        """
        adapter = self._adapters['style_transfer']
        result = adapter.transfer_style(text, target_style, **kwargs)
        
        if 'execution_time' in result.get('metadata', {}):
            self._record_task('style_transfer', result['success'], result['metadata']['execution_time'])
        
        return result
    
    def virtual_persona_chat(self,
                            message: str,
                            persona: str,
                            history: Optional[List[Dict[str, str]]] = None,
                            **kwargs) -> Dict[str, Any]:
        """
        虚拟人格对话
        
        Args:
            message: 用户消息
            persona: 人格设定
            history: 对话历史
            **kwargs: 其他参数
            
        Returns:
            对话结果
        """
        adapter = self._adapters['virtual_persona']
        result = adapter.chat(message, persona, history, **kwargs)
        
        if 'execution_time' in result.get('metadata', {}):
            self._record_task('virtual_persona', result['success'], result['metadata']['execution_time'])
        
        return result
    
    def entity_disambiguation(self,
                             entity: str,
                             context: str,
                             candidates: Optional[List[str]] = None,
                             **kwargs) -> Dict[str, Any]:
        """
        实体消歧
        
        Args:
            entity: 待消歧实体
            context: 上下文
            candidates: 候选实体列表
            **kwargs: 其他参数
            
        Returns:
            消歧结果
        """
        adapter = self._adapters['entity_disambiguation']
        result = adapter.disambiguate(entity, context, candidates, **kwargs)
        
        if 'execution_time' in result.get('metadata', {}):
            self._record_task('entity_disambiguation', result['success'], result['metadata']['execution_time'])
        
        return result
    
    def execute_with_prompt(self,
                           task_type: str,
                           prompt: str,
                           **kwargs) -> Dict[str, Any]:
        """
        使用自定义提示词执行任务
        
        Args:
            task_type: 任务类型
            prompt: 自定义提示词模板（使用{text}作为文本占位符）
            **kwargs: 任务参数
            
        Returns:
            执行结果
        """
        result = self.executor.execute_with_prompt(task_type, prompt, **kwargs)
        
        self._record_task(task_type, result.success, result.execution_time)
        
        return {
            'success': result.success,
            'data': result.data,
            'mode': result.mode,
            'error': result.error,
            'execution_time': result.execution_time
        }
    
    def batch_execute(self,
                     task_type: str,
                     inputs: List[Dict[str, Any]],
                     preset: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        批量执行任务
        
        Args:
            task_type: 任务类型
            inputs: 输入数据列表
            preset: 预设名称
            
        Returns:
            结果列表
        """
        results = []
        
        for input_data in inputs:
            method = getattr(self, task_type, None)
            if method and callable(method):
                if preset:
                    input_data['preset'] = preset
                result = method(**input_data)
            else:
                result = self.execute_with_prompt(task_type, "{text}", **input_data)
            
            results.append(result)
        
        return results
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取任务执行历史"""
        return self._task_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取执行统计"""
        if not self._task_history:
            return {
                'total_tasks': 0,
                'success_rate': 0,
                'average_time': 0,
                'mode': self._mode,
                'provider': self._provider
            }
        
        total = len(self._task_history)
        success_count = sum(1 for h in self._task_history if h['success'])
        total_time = sum(h['execution_time'] for h in self._task_history)
        
        task_counts = {}
        for h in self._task_history:
            task_type = h['task_type']
            task_counts[task_type] = task_counts.get(task_type, 0) + 1
        
        return {
            'total_tasks': total,
            'success_rate': success_count / total,
            'average_time': total_time / total,
            'task_distribution': task_counts,
            'mode': self._mode,
            'provider': self._provider
        }
    
    def export_results(self,
                      results: List[Dict[str, Any]],
                      output_path: str,
                      format: str = "json") -> bool:
        """
        导出结果
        
        Args:
            results: 结果列表
            output_path: 输出路径
            format: 输出格式 ('json', 'csv', 'txt')
            
        Returns:
            是否成功
        """
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == 'json':
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
            
            elif format == 'csv':
                import csv
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['task_type', 'success', 'mode', 'execution_time'])
                    for r in results:
                        writer.writerow([
                            r.get('task_type', ''),
                            r.get('success', ''),
                            r.get('mode', ''),
                            r.get('execution_time', '')
                        ])
            
            elif format == 'txt':
                with open(path, 'w', encoding='utf-8') as f:
                    for i, r in enumerate(results, 1):
                        f.write(f"=== 结果 {i} ===\n")
                        f.write(f"成功: {r.get('success')}\n")
                        f.write(f"模式: {r.get('mode')}\n")
                        if r.get('data'):
                            f.write(f"数据: {json.dumps(r['data'], ensure_ascii=False)}\n")
                        f.write("\n")
            
            return True
        
        except Exception as e:
            print(f"导出失败: {e}")
            return False
    
    def get_api_key_status(self) -> Dict[str, Any]:
        """获取API密钥状态"""
        return self.key_manager.get_status_report()


def get_task_manager() -> TaskManager:
    """获取任务管理器单例"""
    return TaskManager()


if __name__ == '__main__':
    print("=" * 60)
    print("统一任务管理器")
    print("=" * 60)
    
    manager = TaskManager(mode='script')
    
    print(f"\n当前模式: {manager.mode}")
    print(f"当前提供商: {manager.provider}")
    print(f"可用任务: {manager.get_available_tasks()}")
    print(f"可用预设: {list(manager.get_presets().keys())}")
    
    print("\n" + "=" * 60)
    print("测试NER任务（脚本模式）")
    print("=" * 60)
    
    result = manager.ner("伊藤博文出生于1841年，是明治维新的重要人物。")
    print(f"成功: {result.get('success')}")
    if result.get('success'):
        print(f"实体: {result['data'].get('entities', [])}")
    
    print("\n" + "=" * 60)
    print("测试摘要任务（脚本模式）")
    print("=" * 60)
    
    result = manager.summarize("这是一段很长的文本，用于测试摘要功能。" * 10)
    print(f"成功: {result.get('success')}")
    if result.get('success'):
        print(f"摘要: {result['data'].get('summary', '')[:100]}...")
    
    print("\n" + "=" * 60)
    print("执行统计")
    print("=" * 60)
    
    stats = manager.get_statistics()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 60)
    print("切换到API模式")
    print("=" * 60)
    
    manager.set_mode('api')
    print(f"当前模式: {manager.mode}")
