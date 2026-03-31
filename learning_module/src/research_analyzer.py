"""
学术资源检索与分析模块

提供学术资源的自动检索和信息提取功能。
"""

from .prompts import RESEARCH_SYSTEM_PROMPT, RESEARCH_USER_PROMPT


class ResearchAnalyzer:
    """学术资源检索分析器"""
    
    def __init__(self, api_provider='qwen', test_mode=False):
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.client = None
        if not test_mode:
            self._init_client()
    
    def _init_client(self):
        """初始化API客户端"""
        try:
            from modules.llm_client import LLMClient
            provider_map = {
                'qwen': 'dashscope',
                'openai': 'openai',
                'zhipu': 'zhipu',
                'deepseek': 'deepseek',
                'ollama': 'ollama'
            }
            provider = provider_map.get(self.api_provider, 'dashscope')
            config = {'provider': provider}
            self.client = LLMClient(config)
        except ImportError:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from modules.llm_client import LLMClient
            provider_map = {
                'qwen': 'dashscope',
                'openai': 'openai',
                'zhipu': 'zhipu',
                'deepseek': 'deepseek',
                'ollama': 'ollama'
            }
            provider = provider_map.get(self.api_provider, 'dashscope')
            config = {'provider': provider}
            self.client = LLMClient(config)
    
    def search_research(self, topic: str, focus_areas: list = None) -> dict:
        """
        检索学术研究资源
        
        Args:
            topic: 研究主题
            focus_areas: 重点关注领域列表
        
        Returns:
            dict: 检索结果，包含摘要、关键发现等
        """
        if focus_areas is None:
            focus_areas = [
                "技术原理与实现方法",
                "最新研究进展",
                "实际应用案例"
            ]
        
        if self.test_mode:
            return {
                'summary': f'关于{topic}的研究摘要（测试模式）',
                'key_findings': [
                    '关键发现1：深度学习方法在该领域表现优异',
                    '关键发现2：预训练模型显著提升性能',
                    '关键发现3：多语言支持是重要研究方向'
                ],
                'methods': [
                    'BERT-based方法',
                    'Transformer架构',
                    '迁移学习'
                ],
                'applications': [
                    '历史文献处理',
                    '学术文献分析',
                    '多语言NER'
                ],
                'trends': [
                    '大语言模型应用',
                    '少样本学习',
                    '跨语言迁移'
                ]
            }
        
        prompt = RESEARCH_USER_PROMPT.format(
            topic=topic,
            focus_areas="\n".join([f"- {area}" for area in focus_areas])
        )
        
        response = self._call_llm(prompt, system_prompt=RESEARCH_SYSTEM_PROMPT)
        
        return self._parse_research_response(response)
    
    def _call_llm(self, prompt: str, system_prompt: str = None) -> str:
        """调用LLM的统一接口"""
        try:
            if hasattr(self.client, '_call_llm'):
                result = self.client._call_llm(prompt)
                return result.get('content', '')
            elif hasattr(self.client, 'client'):
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\n{prompt}"
                else:
                    full_prompt = prompt
                result = self.client.client.chat.completions.create(
                    model=self.client.model,
                    messages=[{"role": "user", "content": full_prompt}]
                )
                return result.choices[0].message.content
            else:
                result = self.client.chat.completions.create(
                    model=self.client.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                return result.choices[0].message.content
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return ''
    
    def _parse_research_response(self, response: str) -> dict:
        """解析研究响应"""
        result = {
            'summary': '',
            'key_findings': [],
            'methods': [],
            'applications': [],
            'trends': []
        }
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            lower_line = line.lower()
            if '摘要' in line or '总结' in line or lower_line.startswith('##'):
                current_section = 'summary'
            elif '关键发现' in line or '主要发现' in line:
                current_section = 'key_findings'
            elif '方法' in line:
                current_section = 'methods'
            elif '应用' in line:
                current_section = 'applications'
            elif '趋势' in line or '发展方向' in line:
                current_section = 'trends'
            elif line.startswith('-') or line.startswith('*') or line[0].isdigit():
                if current_section and current_section in result:
                    content = line.lstrip('-*1234567890.、 ')
                    if content:
                        result[current_section].append(content)
            elif current_section == 'summary':
                result['summary'] += line + ' '
        
        result['summary'] = result['summary'].strip()
        
        return result
    
    def get_research_summary(self, topic: str) -> str:
        """
        获取研究主题的简要总结
        
        Args:
            topic: 研究主题
        
        Returns:
            str: 研究总结文本
        """
        result = self.search_research(topic)
        return result.get('summary', '未找到相关研究信息')
