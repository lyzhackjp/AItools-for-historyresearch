"""
功能改进建议生成器

基于既有研究成果和文献分析，生成模块功能改进建议。
"""

from .prompts import IMPROVEMENT_SYSTEM_PROMPT, IMPROVEMENT_USER_PROMPT


class ImprovementGenerator:
    """功能改进建议生成器"""
    
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
    
    def generate_improvements(
        self,
        module_name: str,
        context: str,
        research_findings: dict = None,
        literature_insights: dict = None
    ) -> dict:
        """
        生成模块功能改进建议
        
        Args:
            module_name: 模块名称
            context: 应用上下文
            research_findings: 研究发现
            literature_insights: 文献洞察
        
        Returns:
            dict: 改进建议
        """
        research_summary = research_findings.get('summary', '') if research_findings else ''
        key_findings = research_findings.get('key_findings', []) if research_findings else []
        trends = research_findings.get('trends', []) if research_findings else []
        
        tech_points = literature_insights.get('technical_points', []) if literature_insights else []
        impl_suggestions = literature_insights.get('implementation_suggestions', []) if literature_insights else []
        
        if self.test_mode:
            return {
                'module_name': module_name,
                'context': context,
                'short_term_improvements': [
                    '优化提示词，增加具体示例',
                    '添加日文历史实体词典',
                    '改进输出格式的稳定性'
                ],
                'medium_term_improvements': [
                    '集成预训练日语NER模型',
                    '实现批量处理和缓存机制',
                    '添加嵌套实体识别支持'
                ],
                'long_term_improvements': [
                    'Fine-tune领域专用模型',
                    '实现主动学习机制',
                    '构建历史实体知识图谱'
                ],
                'code_examples': [],
                'priority': 'high'
            }
        
        prompt = IMPROVEMENT_USER_PROMPT.format(
            module_name=module_name,
            context=context,
            research_summary=research_summary,
            key_findings="\n".join([f"- {f}" for f in key_findings[:5]]) if key_findings else "暂无",
            trends="\n".join([f"- {t}" for t in trends[:3]]) if trends else "暂无",
            technical_points="\n".join([f"- {p}" for p in tech_points[:5]]) if tech_points else "暂无",
            implementation_suggestions="\n".join([f"- {s}" for s in impl_suggestions[:5]]) if impl_suggestions else "暂无"
        )
        
        response = self._call_llm(prompt, system_prompt=IMPROVEMENT_SYSTEM_PROMPT)
        
        return self._parse_improvement_response(response, module_name, context)
    
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
    
    def suggest_prompt_optimization(
        self,
        current_prompt: str,
        task_type: str,
        target_improvement: str = None
    ) -> dict:
        """
        建议提示词优化
        
        Args:
            current_prompt: 当前提示词
            task_type: 任务类型
            target_improvement: 目标改进方向
        
        Returns:
            dict: 优化建议
        """
        prompt = f"""请分析并优化以下{task_type}提示词：

当前提示词：
{current_prompt}

{f'期望改进方向：{target_improvement}' if target_improvement else ''}

请提供：
1. 当前提示词的问题分析
2. 优化后的提示词
3. 优化理由说明"""
        
        if self.test_mode:
            return {
                'task_type': task_type,
                'current_prompt': current_prompt,
                'optimized_prompt': f'[测试模式] 优化后的{task_type}提示词：\n\n1. 明确角色定义\n2. 添加具体示例\n3. 优化输出格式',
                'target_improvement': target_improvement
            }
        
        response = self._call_llm(prompt)
        
        return {
            'task_type': task_type,
            'current_prompt': current_prompt,
            'optimized_prompt': response,
            'target_improvement': target_improvement
        }
    
    def generate_test_cases(
        self,
        module_name: str,
        context: str,
        num_cases: int = 5
    ) -> list:
        """
        生成测试用例
        
        Args:
            module_name: 模块名称
            context: 应用上下文
            num_cases: 生成的测试用例数量
        
        Returns:
            list: 测试用例列表
        """
        if self.test_mode:
            test_cases = []
            for i in range(num_cases):
                test_cases.append(f'测试用例{i+1}：{context}场景下的边界情况测试')
            return test_cases
        
        prompt = f"""为{module_name}模块生成{num_cases}个测试用例。

应用场景：{context}

请生成覆盖不同输入类型和边界情况的测试用例，格式如下：
1. 测试用例描述
2. 输入数据
3. 期望输出
4. 测试重点"""
        
        response = self._call_llm(prompt)
        
        cases = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                case = line.lstrip('-.1234567890 ')
                if case:
                    cases.append(case)
        
        return cases
    
    def _parse_improvement_response(self, response: str, module_name: str, context: str) -> dict:
        """解析改进建议响应"""
        result = {
            'module_name': module_name,
            'context': context,
            'short_term_improvements': [],
            'medium_term_improvements': [],
            'long_term_improvements': [],
            'code_examples': [],
            'priority': 'medium'
        }
        
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            lower_line = line.lower()
            if '短期' in line or 'quick win' in lower_line:
                current_section = 'short_term_improvements'
            elif '中期' in line or 'medium term' in lower_line:
                current_section = 'medium_term_improvements'
            elif '长期' in line or 'long term' in lower_line:
                current_section = 'long_term_improvements'
            elif '代码' in line or 'example' in lower_line or 'code' in lower_line:
                current_section = 'code_examples'
            elif '优先级' in line or 'priority' in lower_line:
                if '高' in line or 'high' in lower_line:
                    result['priority'] = 'high'
                elif '低' in line or 'low' in lower_line:
                    result['priority'] = 'low'
            elif current_section and current_section in result:
                if line.startswith('-') or line.startswith('*') or (line[0].isdigit() and '.' in line[:3]):
                    content = line.lstrip('-*1234567890.、 ')
                    if content:
                        result[current_section].append(content)
        
        return result
