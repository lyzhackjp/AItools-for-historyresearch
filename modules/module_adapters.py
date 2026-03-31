"""
模块适配器

为现有模块提供统一的适配器接口，支持API和脚本两种执行模式。
所有适配器都通过SecureAPIKeyManager获取密钥，确保密钥安全。

使用方法：
    from modules.module_adapters import (
        NERAdapter, AcademicNoteAdapter, PaperPolishAdapter,
        CitationAdapter, OCRAdapter, SummaryAdapter
    )
    
    # 创建适配器
    ner = NERAdapter(mode='api')
    
    # 执行任务
    result = ner.recognize("伊藤博文是明治维新的重要人物...")
    
    # 切换模式
    ner.set_mode('script')
    result = ner.recognize("伊藤博文是明治维新的重要人物...")
"""

from typing import Optional, Dict, List, Any, Union
from pathlib import Path
from datetime import datetime

from modules.secure_api_key_manager import get_secure_key_manager, SecureAPIKeyManager
from modules.unified_task_executor import (
    UnifiedTaskExecutor, TaskConfig, TaskResult, TaskType, ExecutionMode
)


class BaseAdapter:
    """适配器基类"""
    
    def __init__(self, 
                 mode: str = "api",
                 provider: str = "qwen",
                 model: Optional[str] = None):
        """
        初始化适配器
        
        Args:
            mode: 执行模式 ('api' 或 'script')
            provider: API提供商
            model: 模型名称
        """
        self.executor = UnifiedTaskExecutor()
        self.executor.set_mode(mode)
        self.executor.set_provider(provider)
        self.provider = provider
        self.model = model
        self.key_manager = get_secure_key_manager()
    
    def set_mode(self, mode: str):
        """设置执行模式"""
        self.executor.set_mode(mode)
    
    def get_mode(self) -> str:
        """获取当前执行模式"""
        return self.executor.get_mode()
    
    def set_provider(self, provider: str):
        """设置API提供商"""
        self.provider = provider
        self.executor.set_provider(provider)
    
    def set_model(self, model: str):
        """设置模型"""
        self.model = model
    
    def _create_config(self, **kwargs) -> TaskConfig:
        """创建任务配置"""
        return TaskConfig(
            task_type=self._get_task_type(),
            provider=self.provider,
            model=self.model or kwargs.get('model'),
            temperature=kwargs.get('temperature', 0.3),
            max_tokens=kwargs.get('max_tokens', 2000),
            custom_prompt=kwargs.get('custom_prompt')
        )
    
    def _get_task_type(self) -> TaskType:
        """获取任务类型（子类实现）"""
        raise NotImplementedError
    
    def _handle_result(self, result: TaskResult) -> Dict[str, Any]:
        """处理执行结果"""
        if not result.success:
            return {
                'success': False,
                'error': result.error,
                'mode': result.mode
            }
        
        return {
            'success': True,
            'data': result.data,
            'mode': result.mode,
            'execution_time': result.execution_time,
            'metadata': result.metadata
        }


class NERAdapter(BaseAdapter):
    """命名实体识别适配器"""
    
    def _get_task_type(self) -> TaskType:
        return TaskType.NER
    
    def recognize(self, 
                  text: str,
                  categories: Optional[List[str]] = None,
                  **kwargs) -> Dict[str, Any]:
        """
        识别文本中的命名实体
        
        Args:
            text: 待识别的文本
            categories: 要识别的实体类型列表
            **kwargs: 其他参数
            
        Returns:
            识别结果字典
        """
        config = self._create_config(**kwargs)
        
        result = self.executor.execute(
            TaskType.NER,
            config=config,
            text=text,
            categories=categories
        )
        
        return self._handle_result(result)
    
    def recognize_from_file(self, 
                           file_path: str,
                           categories: Optional[List[str]] = None,
                           **kwargs) -> Dict[str, Any]:
        """从文件读取文本并识别实体"""
        path = Path(file_path)
        if not path.exists():
            return {'success': False, 'error': f'文件不存在: {file_path}'}
        
        text = path.read_text(encoding='utf-8')
        return self.recognize(text, categories, **kwargs)


class AcademicNoteAdapter(BaseAdapter):
    """学术笔记生成适配器"""
    
    def _get_task_type(self) -> TaskType:
        return TaskType.ACADEMIC_NOTE
    
    def generate(self,
                text: str,
                source: str = "未知来源",
                **kwargs) -> Dict[str, Any]:
        """
        生成学术笔记
        
        Args:
            text: 源文本
            source: 来源信息
            **kwargs: 其他参数
            
        Returns:
            笔记内容字典
        """
        config = self._create_config(**kwargs)
        
        result = self.executor.execute(
            TaskType.ACADEMIC_NOTE,
            config=config,
            text=text,
            source=source
        )
        
        return self._handle_result(result)
    
    def generate_from_file(self,
                          file_path: str,
                          source: Optional[str] = None,
                          **kwargs) -> Dict[str, Any]:
        """从文件生成笔记"""
        path = Path(file_path)
        if not path.exists():
            return {'success': False, 'error': f'文件不存在: {file_path}'}
        
        text = path.read_text(encoding='utf-8')
        source = source or path.name
        return self.generate(text, source, **kwargs)
    
    def save_note(self, 
                  note_content: str,
                  output_path: str,
                  title: Optional[str] = None) -> Dict[str, Any]:
        """保存笔记到文件"""
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(note_content, encoding='utf-8')
            return {
                'success': True,
                'path': str(path),
                'message': f'笔记已保存到 {path}'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class PaperPolishAdapter(BaseAdapter):
    """论文润色适配器"""
    
    def _get_task_type(self) -> TaskType:
        return TaskType.PAPER_POLISH
    
    def polish(self,
              text: str,
              language: str = "zh",
              **kwargs) -> Dict[str, Any]:
        """
        润色文本
        
        Args:
            text: 待润色文本
            language: 语言
            **kwargs: 其他参数
            
        Returns:
            润色结果字典
        """
        config = self._create_config(**kwargs)
        
        result = self.executor.execute(
            TaskType.PAPER_POLISH,
            config=config,
            text=text,
            language=language
        )
        
        return self._handle_result(result)
    
    def polish_paragraphs(self,
                         paragraphs: List[str],
                         language: str = "zh",
                         **kwargs) -> List[Dict[str, Any]]:
        """批量润色段落"""
        results = []
        for para in paragraphs:
            result = self.polish(para, language, **kwargs)
            results.append(result)
        return results


class CitationAdapter(BaseAdapter):
    """引用规范化适配器"""
    
    def _get_task_type(self) -> TaskType:
        return TaskType.CITATION_NORMALIZE
    
    def normalize(self,
                 citation: str,
                 target_style: str = "gb7714",
                 **kwargs) -> Dict[str, Any]:
        """
        规范化引用
        
        Args:
            citation: 引用文本
            target_style: 目标格式
            **kwargs: 其他参数
            
        Returns:
            规范化结果字典
        """
        config = self._create_config(**kwargs)
        
        result = self.executor.execute(
            TaskType.CITATION_NORMALIZE,
            config=config,
            citation=citation,
            target_style=target_style
        )
        
        return self._handle_result(result)
    
    def normalize_batch(self,
                       citations: List[str],
                       target_style: str = "gb7714",
                       **kwargs) -> List[Dict[str, Any]]:
        """批量规范化引用"""
        results = []
        for citation in citations:
            result = self.normalize(citation, target_style, **kwargs)
            results.append(result)
        return results


class OCRAdapter(BaseAdapter):
    """OCR校正适配器"""
    
    def _get_task_type(self) -> TaskType:
        return TaskType.OCR_CORRECTION
    
    def correct(self,
               text: str,
               language: str = "zh",
               **kwargs) -> Dict[str, Any]:
        """
        校正OCR文本
        
        Args:
            text: OCR识别文本
            language: 语言
            **kwargs: 其他参数
            
        Returns:
            校正结果字典
        """
        config = self._create_config(**kwargs)
        
        result = self.executor.execute(
            TaskType.OCR_CORRECTION,
            config=config,
            text=text,
            language=language
        )
        
        return self._handle_result(result)
    
    def correct_file(self,
                    file_path: str,
                    language: str = "zh",
                    output_path: Optional[str] = None,
                    **kwargs) -> Dict[str, Any]:
        """校正文件中的OCR文本"""
        path = Path(file_path)
        if not path.exists():
            return {'success': False, 'error': f'文件不存在: {file_path}'}
        
        text = path.read_text(encoding='utf-8')
        result = self.correct(text, language, **kwargs)
        
        if result['success'] and output_path:
            corrected_text = result['data'].get('corrected_text', text)
            Path(output_path).write_text(corrected_text, encoding='utf-8')
            result['output_path'] = output_path
        
        return result


class SummaryAdapter(BaseAdapter):
    """文本摘要适配器"""
    
    def _get_task_type(self) -> TaskType:
        return TaskType.TEXT_SUMMARY
    
    def summarize(self,
                 text: str,
                 max_length: int = 200,
                 **kwargs) -> Dict[str, Any]:
        """
        生成文本摘要
        
        Args:
            text: 源文本
            max_length: 最大长度
            **kwargs: 其他参数
            
        Returns:
            摘要结果字典
        """
        config = self._create_config(**kwargs)
        
        result = self.executor.execute(
            TaskType.TEXT_SUMMARY,
            config=config,
            text=text,
            max_length=max_length
        )
        
        return self._handle_result(result)


class StyleTransferAdapter(BaseAdapter):
    """文风迁移适配器"""
    
    API_PROMPT = """请分析以下文本的文风特征，并按照指定的文风进行改写。

【原文】
{text}

【目标文风】
{target_style}

【输出格式】
请以JSON格式输出：
{{
    "style_analysis": {{
        "sentence_structure": "句法结构分析",
        "vocabulary": "词汇特点",
        "tone": "语气特点"
    }},
    "rewritten_text": "改写后的文本"
}}
"""
    
    def analyze_style(self,
                     text: str,
                     **kwargs) -> Dict[str, Any]:
        """分析文本风格"""
        custom_prompt = """请分析以下文本的文风特征。

【文本】
{text}

【输出格式】
请以JSON格式输出文风分析结果，包含：
- sentence_structure: 句法结构特点
- vocabulary: 词汇选择特点
- tone: 语气与叙事声音
- rhetorical_patterns: 修辞手法
"""
        
        config = self._create_config(custom_prompt=custom_prompt, **kwargs)
        
        result = self.executor.execute_with_prompt(
            'text_summary',
            custom_prompt=custom_prompt,
            text=text
        )
        
        return self._handle_result(result)
    
    def transfer_style(self,
                      text: str,
                      target_style: str,
                      **kwargs) -> Dict[str, Any]:
        """
        文风迁移
        
        Args:
            text: 原文本
            target_style: 目标文风描述
            **kwargs: 其他参数
            
        Returns:
            迁移结果字典
        """
        custom_prompt = self.API_PROMPT.format(
            text=text,
            target_style=target_style
        )
        
        config = self._create_config(custom_prompt=custom_prompt, **kwargs)
        
        result = self.executor.execute_with_prompt(
            'paper_polish',
            custom_prompt=custom_prompt,
            text=text
        )
        
        return self._handle_result(result)


class VirtualPersonaAdapter(BaseAdapter):
    """虚拟人格对话适配器"""
    
    def chat(self,
            message: str,
            persona: str,
            history: Optional[List[Dict[str, str]]] = None,
            **kwargs) -> Dict[str, Any]:
        """
        与虚拟人格对话
        
        Args:
            message: 用户消息
            persona: 人格设定
            history: 对话历史
            **kwargs: 其他参数
            
        Returns:
            对话结果字典
        """
        history_text = ""
        if history:
            for h in history:
                history_text += f"用户: {h.get('user', '')}\n"
                history_text += f"助手: {h.get('assistant', '')}\n"
        
        custom_prompt = f"""你现在扮演以下角色：

【人格设定】
{persona}

【对话历史】
{history_text}

【用户消息】
{message}

请以该角色的身份回复用户消息。直接输出回复内容，不要添加任何解释。"""
        
        result = self.executor.execute_with_prompt(
            'text_summary',
            custom_prompt=custom_prompt,
            text=message
        )
        
        return self._handle_result(result)


class EntityDisambiguationAdapter(BaseAdapter):
    """实体消歧适配器"""
    
    def disambiguate(self,
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
            消歧结果字典
        """
        candidates_text = "、".join(candidates) if candidates else "无预设候选"
        
        custom_prompt = f"""请根据上下文对实体进行消歧。

【实体】
{entity}

【上下文】
{context}

【候选实体】
{candidates_text}

【输出格式】
请以JSON格式输出：
{{
    "resolved_entity": "消歧后的实体",
    "confidence": 0.95,
    "explanation": "消歧依据说明"
}}
"""
        
        result = self.executor.execute_with_prompt(
            'ner',
            custom_prompt=custom_prompt,
            text=context
        )
        
        return self._handle_result(result)


def create_adapter(adapter_type: str, 
                   mode: str = "api",
                   provider: str = "qwen",
                   **kwargs) -> BaseAdapter:
    """
    工厂函数：创建适配器
    
    Args:
        adapter_type: 适配器类型
        mode: 执行模式
        provider: API提供商
        **kwargs: 其他参数
        
    Returns:
        适配器实例
    """
    adapters = {
        'ner': NERAdapter,
        'academic_note': AcademicNoteAdapter,
        'paper_polish': PaperPolishAdapter,
        'citation': CitationAdapter,
        'ocr': OCRAdapter,
        'summary': SummaryAdapter,
        'style_transfer': StyleTransferAdapter,
        'virtual_persona': VirtualPersonaAdapter,
        'entity_disambiguation': EntityDisambiguationAdapter
    }
    
    adapter_class = adapters.get(adapter_type.lower())
    if adapter_class is None:
        raise ValueError(f"未知的适配器类型: {adapter_type}")
    
    return adapter_class(mode=mode, provider=provider, **kwargs)


if __name__ == '__main__':
    print("=" * 60)
    print("模块适配器测试")
    print("=" * 60)
    
    print("\n1. 测试NER适配器（脚本模式）")
    ner = NERAdapter(mode='script')
    result = ner.recognize("伊藤博文出生于1841年，是明治维新的重要人物，曾任日本首相。")
    print(f"模式: {result.get('mode')}")
    print(f"成功: {result.get('success')}")
    if result.get('success'):
        print(f"实体: {result['data'].get('entities', [])}")
    
    print("\n2. 测试摘要适配器（脚本模式）")
    summary = SummaryAdapter(mode='script')
    result = summary.summarize("这是一段很长的文本。" * 20, max_length=100)
    print(f"模式: {result.get('mode')}")
    print(f"成功: {result.get('success')}")
    if result.get('success'):
        print(f"摘要: {result['data'].get('summary', '')[:100]}...")
    
    print("\n3. 测试OCR校正适配器（脚本模式）")
    ocr = OCRAdapter(mode='script')
    result = ocr.correct("这是一个测试日文本，包含一些常见OCR错误。")
    print(f"模式: {result.get('mode')}")
    print(f"成功: {result.get('success')}")
    
    print("\n4. 测试模式切换")
    adapter = create_adapter('ner', mode='script')
    print(f"当前模式: {adapter.get_mode()}")
    adapter.set_mode('api')
    print(f"切换后模式: {adapter.get_mode()}")
