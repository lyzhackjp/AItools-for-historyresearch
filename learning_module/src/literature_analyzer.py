"""
文献分析模块

提供研究文献的分析和技术要点提取功能。
"""

from .prompts import LITERATURE_SYSTEM_PROMPT, LITERATURE_USER_PROMPT


class LiteratureAnalyzer:
    """文献分析器"""
    
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
    
    def analyze_literature(self, summary: str, key_findings: list = None) -> dict:
        """
        分析文献内容
        
        Args:
            summary: 文献摘要
            key_findings: 关键发现列表
        
        Returns:
            dict: 分析结果，包含技术要点、实现建议等
        """
        if key_findings is None:
            key_findings = []
        
        if self.test_mode:
            return {
                'technical_points': [
                    'BERT预训练模型',
                    '上下文语境分析',
                    '序列标注方法'
                ],
                'implementation_suggestions': [
                    '使用预训练模型fine-tuning',
                    '添加领域特定词典',
                    '优化提示词设计'
                ],
                'best_practices': [
                    '充分的训练数据',
                    '合理的超参数调优',
                    '多轮迭代优化'
                ],
                'limitations': [
                    '计算资源需求高',
                    '标注数据获取困难',
                    '领域适配需要专业知识'
                ]
            }
        
        findings_text = "\n".join([f"- {f}" for f in key_findings]) if key_findings else "暂无关键发现"
        
        prompt = LITERATURE_USER_PROMPT.format(
            summary=summary,
            key_findings=findings_text
        )
        
        response = self._call_llm(prompt, system_prompt=LITERATURE_SYSTEM_PROMPT)
        
        return self._parse_literature_response(response)
    
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
    
    def extract_technical_points(self, text: str) -> list:
        """
        从文本中提取技术要点
        
        Args:
            text: 输入文本
        
        Returns:
            list: 技术要点列表
        """
        prompt = f"""从以下文本中提取关键的技术要点：

{text}

请列出所有重要的技术概念、方法或实现细节。"""
        
        if self.test_mode:
            return [
                '技术要点1：深度学习方法',
                '技术要点2：预训练模型',
                '技术要点3：迁移学习'
            ]
        
        response = self._call_llm(prompt)
        
        points = []
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith('-') or line.startswith('*') or line[0].isdigit():
                point = line.lstrip('-*1234567890.、 ')
                if point:
                    points.append(point)
        
        return points
    
    def compare_methods(self, method1: str, method2: str) -> dict:
        """
        比较两种技术方法的优劣
        
        Args:
            method1: 方法1描述
            method2: 方法2描述
        
        Returns:
            dict: 比较结果
        """
        if self.test_mode:
            return {
                'comparison': '[测试模式] 方法比较结果：\n\n方法1: 准确性高但需要大量标注数据\n方法2: 效率高但准确性较低\n\n建议: 根据实际场景选择或组合使用',
                'method1': method1,
                'method2': method2
            }
        
        prompt = f"""请比较以下两种技术方法的优劣：

方法1：{method1}

方法2：{method2}

请从准确性、效率、适用场景、实现复杂度等维度进行分析。"""
        
        response = self._call_llm(prompt)
        
        return {
            'comparison': response,
            'method1': method1,
            'method2': method2
        }
    
    def _parse_literature_response(self, response: str) -> dict:
        """解析文献分析响应"""
        result = {
            'technical_points': [],
            'implementation_suggestions': [],
            'best_practices': [],
            'limitations': []
        }
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            lower_line = line.lower()
            if '技术要点' in line or '核心概念' in line:
                current_section = 'technical_points'
            elif '实现建议' in line or '实施建议' in line:
                current_section = 'implementation_suggestions'
            elif '最佳实践' in line or '推荐做法' in line:
                current_section = 'best_practices'
            elif '局限性' in line or '不足' in line:
                current_section = 'limitations'
            elif line.startswith('-') or line.startswith('*') or (line[0].isdigit() and '.' in line[:3]):
                if current_section and current_section in result:
                    content = line.lstrip('-*1234567890.、 ')
                    if content:
                        result[current_section].append(content)
        
        return result
