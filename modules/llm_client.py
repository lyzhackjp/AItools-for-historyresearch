import os
import json
import time
import requests
from typing import Optional, Dict, Any
from openai import OpenAI
from anthropic import Anthropic


class LLMClient:
    """大语言模型API调用接口 - 支持多种LLM服务商，包括国内模型"""

    SUPPORTED_PROVIDERS = [
        'openai', 'anthropic', 'dashscope', 'minimax', 'zhipu', 
        'volcano', 'deepseek', 'ollama', 'custom'
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化LLM客户端

        Args:
            config: 配置字典，包含provider、api_key、model等参数
        """
        self.config = config or {}
        self.provider = self.config.get('provider', 'openai')
        self.model = self.config.get('model', self._get_default_model())
        self.api_key = self._get_api_key()
        self.base_url = self.config.get('base_url') or self._get_base_url()
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 1)

        self._init_client()

    def _get_default_model(self) -> str:
        """获取各provider的默认模型"""
        defaults = {
            'openai': 'gpt-4',
            'anthropic': 'claude-3-sonnet-20240229',
            'dashscope': 'qwen-turbo',
            'minimax': 'abab6-chat',
            'zhipu': 'glm-4',
            'volcano': ' volcengine-m2',
            'deepseek': 'deepseek-chat',
            'ollama': 'llama2'
        }
        return defaults.get(self.provider, 'gpt-4')

    def _get_api_key(self) -> Optional[str]:
        """获取API密钥"""
        if self.config.get('api_key'):
            return self.config['api_key']

        env_vars = {
            'openai': 'OPENAI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'dashscope': 'DASHSCOPE_API_KEY',
            'minimax': 'MINIMAX_API_KEY',
            'zhipu': 'ZHIPU_API_KEY',
            'volcano': 'VOLCANO_API_KEY',
            'deepseek': 'DEEPSEEK_API_KEY',
            'ollama': None
        }

        env_var = env_vars.get(self.provider)
        return os.getenv(env_var) if env_var else None

    def _get_base_url(self) -> Optional[str]:
        """获取API基础URL"""
        base_urls = {
            'ollama': 'http://localhost:11434',
            'deepseek': 'https://api.deepseek.com',
            'zhipu': 'https://open.bigmodel.cn/api/paas/v4'
        }
        return self.config.get('base_url') or base_urls.get(self.provider)

    def _init_client(self):
        """根据provider初始化对应的客户端"""
        if self.provider == 'openai':
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        elif self.provider == 'anthropic':
            self.client = Anthropic(
                api_key=self.api_key
            )
        elif self.provider == 'ollama':
            self.client = OpenAI(
                api_key='ollama',
                base_url=f"{self.base_url}/v1"
            )
        elif self.provider == 'minimax':
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        elif self.provider in ['deepseek', 'zhipu']:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

    def academic_polish(self, text: str, language: str = 'zh') -> Dict[str, Any]:
        """
        学术性润色接口

        Args:
            text: 待处理的文本
            language: 目标语言 ('zh': 中文, 'ja': 日文, 'en': 英文)

        Returns:
            dict: 包含处理结果的字典
        """
        language_prompts = {
            'zh': '你是一位专业的中国历史学学术论文编辑，请对以下文本进行学术性润色，'
                  '修正语法错误，提升学术表达规范度，删除冗余内容，保持原意。'
                  '仅输出润色后的文本，不要添加任何解释或评论。',
            'ja': 'あなたは専門の歴史学学術論文編集者として、以下のテキストを学術的に校訂し、'
                  '文法エラーを修正し、学術表現の規範性を高め、冗長な内容を削除し、'
                  '元の意味を保つてください。校訂後のテキストのみを出力し、説明やコメントは追加しないでください。',
            'en': 'As a professional academic paper editor specializing in history, '
                  'please polish the following text for academic quality, correct grammatical errors, '
                  'improve academic expression standards, remove redundant content, and maintain the original meaning. '
                  'Only output the polished text without any explanations or comments.'
        }

        prompt = language_prompts.get(language, language_prompts['zh'])

        return self._call_llm(f"{prompt}\n\n{text}")

    def remove_redundancy(self, text: str) -> str:
        """
        冗余内容删减接口

        Args:
            text: 待处理的文本

        Returns:
            str: 删除冗余后的文本
        """
        prompt = """你是一位专业的学术编辑，请删除以下文本中的冗余内容，包括：
1. 重复的表达
2. 无意义的填充词
3. 过度解释的语句
4. 与主题无关的内容

仅输出处理后的文本，不要添加任何解释。"""

        result = self._call_llm(f"{prompt}\n\n{text}")
        return result.get('content', text)

    def ocr_correction(self, ocr_text: str, language: str = 'zh') -> str:
        """
        OCR结果校正接口

        Args:
            ocr_text: OCR识别后的文本
            language: 文本语言

        Returns:
            str: 校正后的文本
        """
        prompt_map = {
            'zh': '你是一位专业的中文OCR结果校正专家，请修正以下OCR识别文本中的错误，'
                  '包括但不限于：错别字、漏字、多余字符、格式错误等。'
                  '保持原文的结构和格式，仅输出校正后的文本。',
            'ja': 'あなたは專業的な日本語OCR結果校正專門家です。以下のOCR認識テキストのエラーを修正してください。'
                  '誤字、脱字、余分な文字、フォーマットエラーなどを含みます。'
                  '原文の構造とフォーマットを維持し、校正後のテキストのみを出力してください。',
            'en': 'You are a professional English OCR result correction expert. '
                  'Please correct errors in the following OCR recognized text, '
                  'including but not limited to: typos, missing characters, extra characters, formatting errors, etc. '
                  'Maintain the original structure and format, and only output the corrected text.'
        }

        prompt = prompt_map.get(language, prompt_map['zh'])

        result = self._call_llm(f"{prompt}\n\n{ocr_text}")
        return result.get('content', ocr_text)

    def text_to_structure(self, text: str, structure_type: str = 'general') -> Dict[str, Any]:
        """
        文本结构化接口

        Args:
            text: 待结构化的文本
            structure_type: 结构化类型 ('general', 'table', 'key_value', 'timeline')

        Returns:
            dict: 结构化后的数据
        """
        structure_prompts = {
            'general': '请将以下文本转换为JSON格式的结构化数据，保持原文的层次结构。',
            'table': '请从以下文本中提取表格数据，输出为JSON数组格式。',
            'key_value': '请从以下文本中提取键值对数据，输出为JSON对象格式。',
            'timeline': '请从以下文本中提取时间线信息，输出为JSON数组格式，每个元素包含时间和事件描述。'
        }

        prompt = structure_prompts.get(structure_type, structure_prompts['general'])

        result = self._call_llm(f"{prompt}\n\n{text}")
        return {
            'structured_data': result.get('content', ''),
            'format': structure_type
        }

    def _call_llm(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        通用LLM调用接口（带重试机制）

        Args:
            prompt: 提示词
            **kwargs: 其他参数如temperature、max_tokens等

        Returns:
            dict: 包含响应内容的字典
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                if self.provider == 'openai':
                    return self._call_openai(prompt, **kwargs)
                elif self.provider == 'anthropic':
                    return self._call_anthropic(prompt, **kwargs)
                elif self.provider == 'dashscope':
                    return self._call_dashscope(prompt, **kwargs)
                elif self.provider == 'minimax':
                    return self._call_minimax(prompt, **kwargs)
                elif self.provider == 'zhipu':
                    return self._call_zhipu(prompt, **kwargs)
                elif self.provider == 'volcano':
                    return self._call_volcano(prompt, **kwargs)
                elif self.provider == 'deepseek':
                    return self._call_deepseek(prompt, **kwargs)
                elif self.provider == 'ollama':
                    return self._call_ollama(prompt, **kwargs)
                else:
                    return self._call_openai(prompt, **kwargs)

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue

        return {
            'error': str(last_error),
            'content': ''
        }

    def _call_openai(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """调用OpenAI API"""
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 4000)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )

        return {
            'content': response.choices[0].message.content,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        }

    def _call_anthropic(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """调用Anthropic API"""
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 4000)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            'content': response.content[0].text,
            'usage': {
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens
            }
        }

    def _call_dashscope(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        调用阿里云通义千问API (DashScope)

        文档: https://help.aliyun.com/zh/dashscope/
        """
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'model': self.model,
            'input': {
                'prompt': prompt
            },
            'parameters': {
                'temperature': kwargs.get('temperature', 0.7),
                'max_tokens': kwargs.get('max_tokens', 2000)
            }
        }

        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()

        result = response.json()

        return {
            'content': result['output']['text'],
            'usage': result.get('usage', {})
        }

    def _call_minimax(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        调用MiniMax API

        文档: https://www.minimaxi.com/document
        """
        import os
        
        url = "https://api.minimax.chat/v1/text/chatcompletion_pro"

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        group_id = os.getenv('MINIMAX_GROUP_ID', '')

        data = {
            'model': self.model,
            'messages': [{"role": "user", "content": prompt}],
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 2000)
        }
        
        if group_id:
            data['group_id'] = group_id

        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()

        result = response.json()
        
        if result.get('choices') and len(result['choices']) > 0:
            content = result['choices'][0]['messages'][0]['text']
        elif result.get('reply'):
            content = result['reply']
        else:
            content = str(result)

        return {
            'content': content,
            'usage': result.get('usage', {})
        }

    def _call_zhipu(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        调用智谱AI API (GLM)

        文档: https://open.bigmodel.cn/dev/api
        """
        url = f"{self.base_url}/chat/completions"

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'model': self.model,
            'messages': [{"role": "user", "content": prompt}],
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 2000)
        }

        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()

        result = response.json()

        return {
            'content': result['choices'][0]['message']['content'],
            'usage': result.get('usage', {})
        }

    def _call_volcano(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        调用火山引擎API (Volcano Ark)

        文档: https://www.volcengine.com/docs/82379/1263482
        """
        url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        data = {
            'model': self.model,
            'messages': [{"role": "user", "content": prompt}],
            'temperature': kwargs.get('temperature', 0.7),
            'max_tokens': kwargs.get('max_tokens', 2000)
        }

        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()

        result = response.json()

        return {
            'content': result['choices'][0]['message']['content'],
            'usage': result.get('usage', {})
        }

    def _call_deepseek(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        调用DeepSeek API

        文档: https://platform.deepseek.com/docs
        """
        temperature = kwargs.get('temperature', 0.7)
        max_tokens = kwargs.get('max_tokens', 4000)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )

        return {
            'content': response.choices[0].message.content,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        }

    def _call_ollama(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        调用Ollama本地API

        文档: https://github.com/ollama/ollama/blob/main/docs/api.md
        """
        url = f"{self.base_url}/api/chat"

        data = {
            'model': self.model,
            'messages': [{"role": "user", "content": prompt}],
            'stream': False
        }

        response = requests.post(url, json=data, timeout=120)
        response.raise_for_status()

        result = response.json()

        return {
            'content': result['message']['content'],
            'usage': result.get('usage', {})
        }

    def set_model(self, model: str):
        """设置模型"""
        self.model = model

    def set_provider(self, provider: str):
        """设置提供商"""
        if provider in self.SUPPORTED_PROVIDERS:
            self.provider = provider
            self.model = self._get_default_model()
            self.api_key = self._get_api_key()
            self.base_url = self._get_base_url()
            self._init_client()

    def get_provider_info(self) -> Dict[str, Any]:
        """获取当前provider信息"""
        return {
            'provider': self.provider,
            'model': self.model,
            'has_api_key': bool(self.api_key),
            'base_url': self.base_url
        }


def create_llm_client(config: Optional[Dict[str, Any]] = None) -> LLMClient:
    """
    工厂函数 - 创建LLM客户端实例

    Args:
        config: 配置字典

    Returns:
        LLMClient: LLM客户端实例
    """
    return LLMClient(config)
