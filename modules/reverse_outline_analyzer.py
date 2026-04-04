"""
逆向大纲审视器模块

用于分析论文草稿的逻辑链、各部分比重等，实现逆向审视
是学术写作辅助的核心工具之一

核心功能：
- 篇幅分析：各部分字数统计、比例失衡检测
- 逻辑链分析：论点提取、逻辑关系识别、断层检测
- 注意力集中度分析：核心论点识别、偏离检测
- 修订建议生成：综合分析结果生成改进建议

使用方法：
    from modules.reverse_outline_analyzer import ReverseOutlineAnalyzer
    
    analyzer = ReverseOutlineAnalyzer()
    result = analyzer.analyze(paper_text)
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import Counter

try:
    from prompts.prompt_loader import PromptLoader, PromptTemplate
    PROMPT_LOADER_AVAILABLE = True
except ImportError:
    PROMPT_LOADER_AVAILABLE = False

try:
    from modules.llm_client import create_llm_client
    LLM_CLIENT_AVAILABLE = True
except ImportError:
    LLM_CLIENT_AVAILABLE = False


class ReverseOutlineAnalyzer:
    """逆向大纲审视器"""
    
    SECTION_PATTERNS = {
        'abstract': r'(摘要|Abstract)',
        'introduction': r'(序章|导论|Introduction|前言)',
        'literature_review': r'(文献综述|研究回顾|Literature Review)',
        'methodology': r'(研究方法|Methodology|方法)',
        'analysis': r'(分析|Analysis|正文)',
        'results': r'(结果|Results|发现)',
        'discussion': r'(讨论|Discussion)',
        'conclusion': r'(结论|Conclusion|结语)',
        'references': r'(参考文献|References)',
        'acknowledgments': r'(致谢|Acknowledgments)'
    }
    
    def __init__(self, api_provider: str = "qwen", test_mode: bool = True):
        """
        初始化逆向大纲审视器
        
        Args:
            api_provider: API提供商
            test_mode: 测试模式标志
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self._prompt_loader = None
        self._prompt_template = None
        self.llm_client = None
        
        self.provider_mapping = {
            'qwen': 'dashscope',
            'minimax': 'minimax',
            'gemini': 'custom',
            'chatgpt': 'openai'
        }
    
    def _get_prompt_loader(self):
        """获取提示词加载器"""
        if self._prompt_loader is None and PROMPT_LOADER_AVAILABLE:
            self._prompt_loader = PromptLoader()
        return self._prompt_loader
    
    def _get_prompt_template(self):
        """获取提示词模板"""
        if self._prompt_template is None:
            loader = self._get_prompt_loader()
            self._prompt_template = PromptTemplate(loader) if loader else None
        return self._prompt_template
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        loader = self._get_prompt_loader()
        if loader:
            try:
                return loader.load_prompt('reverse_outline_analyzer', 'ROA_G001')
            except Exception:
                pass
        return self.DEFAULT_SYSTEM_PROMPT
    
    def DEFAULT_SYSTEM_PROMPT(self):
        """默认系统提示词"""
        return """你是一位资深的学术论文审稿专家，擅长分析论文的结构、逻辑和论证质量。

你的专长包括：
1. 识别论文的核心论点和支持论点
2. 分析论文各部分的篇幅分布
3. 检测逻辑断层和论证漏洞
4. 评估论述的集中度和连贯性
5. 提供具体的修订建议

请严格按照JSON格式输出分析结果。"""
    
    def analyze(self, paper_text: str, use_llm: bool = True) -> Dict[str, Any]:
        """
        全面分析论文草稿
        
        Args:
            paper_text: 论文文本
            use_llm: 是否使用LLM进行深度分析
            
        Returns:
            Dict: 包含篇幅分析、逻辑分析、修订建议等
        """
        if not paper_text or len(paper_text.strip()) < 100:
            return {
                'success': False,
                'error': '文本过短，无法分析'
            }
        
        outline = self.extract_outline(paper_text)
        
        imbalance_issues = self.detect_imbalance(outline)
        
        logic_gaps = self.check_logic_gaps(outline, use_llm=use_llm)
        
        revision_suggestions = self.suggest_revisions(
            outline, imbalance_issues, logic_gaps, use_llm=use_llm
        )
        
        return {
            'success': True,
            'outline': outline,
            'imbalance_issues': imbalance_issues,
            'logic_gaps': logic_gaps,
            'revision_suggestions': revision_suggestions,
            'summary': self._generate_summary(outline, imbalance_issues, logic_gaps)
        }
    
    def extract_outline(self, paper_text: str) -> Dict[str, Any]:
        """
        提取论文大纲
        
        Args:
            paper_text: 论文文本
            
        Returns:
            Dict: 包含各章节信息的大纲
        """
        sections = self._identify_sections(paper_text)
        
        outline = {
            'total_length': len(paper_text),
            'sections': [],
            'unstructured_content': []
        }
        
        for section_name, content in sections.items():
            section_info = {
                'name': section_name,
                'content': content,
                'length': len(content),
                'percentage': 0.0,
                'paragraphs': self._split_paragraphs(content),
                'word_count': len(content.replace(' ', ''))
            }
            outline['sections'].append(section_info)
        
        outline['unstructured_content'] = self._find_unstructured_content(paper_text, sections)
        
        total_length = sum(s['length'] for s in outline['sections'])
        for section in outline['sections']:
            if total_length > 0:
                section['percentage'] = round(section['length'] / total_length * 100, 2)
        
        return outline
    
    def detect_imbalance(self, outline: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        检测篇幅失衡问题
        
        Args:
            outline: 论文大纲数据
            
        Returns:
            List[Dict]: 失衡问题列表
        """
        issues = []
        
        total_length = outline.get('total_length', 0)
        if total_length < 1000:
            issues.append({
                'type': 'length_warning',
                'severity': 'high',
                'message': '论文总长度不足，建议至少5000字',
                'suggestion': '补充研究内容或论证细节'
            })
        
        sections = outline.get('sections', [])
        if len(sections) == 0:
            return [{
                'type': 'structure_error',
                'severity': 'high',
                'message': '无法识别论文结构',
                'suggestion': '检查论文格式是否规范'
            }]
        
        section_lengths = [s['length'] for s in sections]
        avg_length = sum(section_lengths) / len(section_lengths) if section_lengths else 0
        
        for section in sections:
            section_name = section['name']
            section_length = section['length']
            percentage = section['percentage']
            
            if percentage < 5:
                issues.append({
                    'type': 'section_too_short',
                    'severity': 'medium',
                    'section': section_name,
                    'message': f'章节"{section_name}"篇幅过短（{percentage:.1f}%）',
                    'suggestion': f'考虑补充{self._estimate_missing_length(percentage, total_length)}字'
                })
            
            elif percentage > 50:
                issues.append({
                    'type': 'section_too_long',
                    'severity': 'medium',
                    'section': section_name,
                    'message': f'章节"{section_name}"篇幅过长（{percentage:.1f}%）',
                    'suggestion': '考虑拆分或精简该章节'
                })
            
            elif section_length > avg_length * 2:
                issues.append({
                    'type': 'section_disproportionate',
                    'severity': 'low',
                    'section': section_name,
                    'message': f'章节"{section_name}"与整体不成比例',
                    'suggestion': '检查该章节内容是否过于冗余'
                })
        
        unstructured_pct = len(outline.get('unstructured_content', '')) / total_length * 100 if total_length > 0 else 0
        if unstructured_pct > 20:
            issues.append({
                'type': 'too_much_unstructured',
                'severity': 'high',
                'message': f'未分类内容过多（{unstructured_pct:.1f}%）',
                'suggestion': '规范论文结构，明确各章节标题'
            })
        
        return issues
    
    def check_logic_gaps(self, outline: Dict[str, Any], use_llm: bool = True) -> List[Dict[str, Any]]:
        """
        检测逻辑断层
        
        Args:
            outline: 论文大纲数据
            use_llm: 是否使用LLM分析
            
        Returns:
            List[Dict]: 逻辑问题列表
        """
        gaps = []
        
        sections = outline.get('sections', [])
        section_names = [s['name'] for s in sections]
        
        has_intro = any('intro' in name.lower() for name in section_names)
        has_conclusion = any('conclusion' in name.lower() for name in section_names)
        has_method = any('method' in name.lower() for name in section_names)
        has_analysis = any('analysis' in name.lower() for name in section_names)
        
        if not has_intro:
            gaps.append({
                'type': 'missing_section',
                'severity': 'high',
                'message': '缺少引言/序章部分',
                'suggestion': '添加研究背景、问题意识等引入内容'
            })
        
        if not has_conclusion:
            gaps.append({
                'type': 'missing_section',
                'severity': 'medium',
                'message': '缺少结论部分',
                'suggestion': '添加研究总结、贡献说明等'
            })
        
        if not has_method and has_analysis:
            gaps.append({
                'type': 'logic_disconnect',
                'severity': 'high',
                'message': '有分析但缺少方法论部分',
                'suggestion': '明确研究方法，增加方法论说明'
            })
        
        if use_llm and LLM_CLIENT_AVAILABLE:
            llm_gaps = self._llm_analyze_logic(outline)
            gaps.extend(llm_gaps)
        
        gaps.extend(self._heuristic_logic_check(outline))
        
        return gaps
    
    def suggest_revisions(self, outline: Dict, imbalance_issues: List, 
                        logic_gaps: List, use_llm: bool = True) -> List[str]:
        """
        生成修订建议
        
        Args:
            outline: 论文大纲
            imbalance_issues: 篇幅失衡问题
            logic_gaps: 逻辑断层
            use_llm: 是否使用LLM
            
        Returns:
            List[str]: 修订建议列表
        """
        suggestions = []
        
        for issue in imbalance_issues:
            if 'suggestion' in issue:
                suggestions.append(f"【篇幅问题】{issue['suggestion']}")
        
        for gap in logic_gaps:
            if 'suggestion' in gap:
                suggestions.append(f"【逻辑问题】{gap['suggestion']}")
        
        if use_llm and LLM_CLIENT_AVAILABLE:
            llm_suggestions = self._llm_generate_suggestions(outline)
            suggestions.extend(llm_suggestions)
        
        if len(suggestions) == 0:
            suggestions.append('论文结构基本合理，无需重大修改')
        
        return suggestions
    
    def _identify_sections(self, paper_text: str) -> Dict[str, str]:
        """识别论文各章节"""
        sections = {}
        
        section_positions = []
        for pattern_name, pattern in self.SECTION_PATTERNS.items():
            for match in re.finditer(pattern, paper_text, re.IGNORECASE):
                section_positions.append({
                    'name': pattern_name,
                    'position': match.start()
                })
        
        section_positions.sort(key=lambda x: x['position'])
        
        for i, section in enumerate(section_positions):
            start_pos = section['position']
            end_pos = section_positions[i + 1]['position'] if i + 1 < len(section_positions) else len(paper_text)
            
            section_content = paper_text[start_pos:end_pos].strip()
            sections[section['name']] = section_content
        
        return sections
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """将文本分割成段落"""
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text)]
        return [p for p in paragraphs if len(p) > 50]
    
    def _find_unstructured_content(self, paper_text: str, 
                                  sections: Dict[str, str]) -> str:
        """查找未分类内容"""
        total_section_length = sum(len(content) for content in sections.values())
        
        if total_section_length < len(paper_text) * 0.8:
            return paper_text[total_section_length:]
        
        return ""
    
    def _estimate_missing_length(self, current_percentage: float, 
                                total_length: int) -> int:
        """估算建议补充的字数"""
        target_percentage = 10.0
        if current_percentage < target_percentage:
            missing = (target_percentage - current_percentage) / 100 * total_length
            return max(int(missing), 500)
        return 0
    
    def _heuristic_logic_check(self, outline: Dict) -> List[Dict]:
        """基于启发式的逻辑检查"""
        gaps = []
        
        sections = outline.get('sections', [])
        
        paragraph_counts = [len(s['paragraphs']) for s in sections if s['paragraphs']]
        if paragraph_counts:
            avg_paragraphs = sum(paragraph_counts) / len(paragraph_counts)
            
            for section in sections:
                if len(section['paragraphs']) < avg_paragraphs * 0.3 and section['length'] > 500:
                    gaps.append({
                        'type': 'paragraph_density_low',
                        'severity': 'low',
                        'section': section['name'],
                        'message': f'章节"{section["name"]}"段落过少',
                        'suggestion': '该章节可能需要更多论述支撑'
                    })
        
        return gaps
    
    def _llm_analyze_logic(self, outline: Dict) -> List[Dict]:
        """使用LLM分析逻辑问题"""
        try:
            self._init_llm_client()
            
            system_prompt = self._load_system_prompt()
            
            outline_summary = self._format_outline_for_llm(outline)
            
            user_prompt = f"""请分析以下论文大纲的逻辑问题：

{outline_summary}

请识别：
1. 论证链是否完整
2. 各部分衔接是否顺畅
3. 是否有遗漏的重要论证环节

请以JSON格式输出发现的逻辑问题列表。"""
            
            response = self._call_llm(system_prompt, user_prompt)
            
            return self._parse_llm_logic_response(response)
            
        except Exception as e:
            print(f"LLM逻辑分析失败: {e}")
            return []
    
    def _llm_generate_suggestions(self, outline: Dict) -> List[str]:
        """使用LLM生成修订建议"""
        try:
            self._init_llm_client()
            
            outline_summary = self._format_outline_for_llm(outline)
            
            user_prompt = f"""基于以下论文大纲，请提供具体的修订建议：

{outline_summary}

请以JSON数组格式输出修订建议列表，每条建议不超过50字。"""
            
            response = self._call_llm("", user_prompt)
            
            return self._parse_llm_suggestions(response)
            
        except Exception as e:
            print(f"LLM建议生成失败: {e}")
            return []
    
    def _format_outline_for_llm(self, outline: Dict) -> str:
        """格式化大纲供LLM分析"""
        lines = [f"论文总长度: {outline['total_length']}字符"]
        lines.append("\n章节结构:")
        
        for section in outline.get('sections', []):
            lines.append(f"\n- {section['name']}")
            lines.append(f"  长度: {section['length']}字符 ({section['percentage']}%)")
            lines.append(f"  段落数: {len(section['paragraphs'])}")
        
        return "\n".join(lines)
    
    def _parse_llm_logic_response(self, response: str) -> List[Dict]:
        """解析LLM逻辑分析响应"""
        try:
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0]
            
            data = json.loads(response.strip())
            
            if isinstance(data, list):
                return [{
                    'type': 'llm_analysis',
                    'severity': item.get('severity', 'medium'),
                    'message': item.get('message', ''),
                    'suggestion': item.get('suggestion', '')
                } for item in data]
            
            return []
            
        except Exception:
            return []
    
    def _parse_llm_suggestions(self, response: str) -> List[str]:
        """解析LLM修订建议"""
        try:
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0]
            
            data = json.loads(response.strip())
            
            if isinstance(data, list):
                return [str(item) for item in data]
            
            return []
            
        except Exception:
            return []
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.llm_client is None and not self.test_mode:
            provider = self.provider_mapping.get(self.api_provider, 'dashscope')
            config = {
                'provider': provider,
                'model': 'qwen-turbo'
            }
            self.llm_client = create_llm_client(config)
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用LLM"""
        if self.test_mode or self.llm_client is None:
            return self._generate_mock_response(user_prompt)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        
        # Use _call_llm instead of .chat() to match our LLMClient interface
        combined_prompt = (system_prompt + "\n\n" + user_prompt) if system_prompt else user_prompt
        result = self.llm_client._call_llm(combined_prompt, temperature=0.3)
        return result.get('content', '') if isinstance(result, dict) else (result or '')
    
    def _generate_mock_response(self, prompt: str) -> str:
        """生成模拟响应（测试模式）"""
        if '逻辑问题' in prompt:
            return json.dumps([
                {
                    'severity': 'medium',
                    'message': '论证深度有待加强',
                    'suggestion': '建议补充更多史料支撑'
                }
            ])
        elif '修订建议' in prompt:
            return json.dumps([
                '优化章节篇幅分配',
                '加强论证逻辑连贯性',
                '补充研究背景说明'
            ])
        
        return '{}'
    
    def _generate_summary(self, outline: Dict, imbalance_issues: List, 
                        logic_gaps: List) -> str:
        """生成分析总结"""
        total_issues = len(imbalance_issues) + len(logic_gaps)
        
        if total_issues == 0:
            return "论文结构良好，各部分比例合理，逻辑连贯。"
        
        high_severity = sum(1 for issue in imbalance_issues + logic_gaps 
                          if issue.get('severity') == 'high')
        
        if high_severity > 0:
            return f"发现{total_issues}个问题，其中{high_severity}个高优先级问题需要关注。"
        
        return f"发现{total_issues}个问题，建议进行相应修订。"
