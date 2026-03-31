"""
文风分析与迁移模块

分析特定作者的写作风格，实现文风迁移与模仿
支持文风矩阵四维度分析

核心功能：
- 构建文风矩阵分析
- 句法结构分析
- 词汇选择分析
- 语气与叙事声音分析
- 学术修辞机制分析
- 基于文风矩阵的文本改写
- 少样本文风模仿

文风矩阵四维度：
1. 句法结构
2. 词汇深度与选择
3. 语气与叙事声音
4. 学术修辞机制

API优先级：
1. 阿里通义千问 (dashscope)
2. MiniMax
3. Gemini/ChatGPT（备选）

测试模式：使用模拟数据，不调用真实API

依赖模块：
- llm_client.py
- paper_polisher.py（用于Prompt工程参考）
"""

import re
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime


class StyleTransfer:
    """文风分析与迁移模块"""
    
    STYLE_MATRIX_DIMENSIONS = [
        'sentence_structure',
        'vocabulary_choices', 
        'tone_narrative',
        'rhetorical_patterns'
    ]
    
    DEFAULT_SYSTEM_PROMPT = """你是一位精通文本风格迁移的顶级学术写作助手。

你的专长包括：
1. 深度分析文章风格矩阵
2. 识别作者的写作习惯和特征
3. 精确模仿特定作者的文风
4. 进行高质量的文风迁移

请严格按照要求输出分析结果。"""
    
    def __init__(self, api_provider: str = "qwen", test_mode: bool = True):
        """
        初始化文风分析与迁移模块
        
        Args:
            api_provider: API提供商
            test_mode: 测试模式标志
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.llm_client = None
        
        self.provider_mapping = {
            'qwen': 'dashscope',
            'minimax': 'minimax',
            'gemini': 'custom',
            'chatgpt': 'openai'
        }
        
        self.analyzed_styles = {}
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.test_mode:
            return None
            
        if self.llm_client is None:
            provider = self.provider_mapping.get(self.api_provider, 'dashscope')
            
            config = self._create_provider_config(provider)
            self.llm_client = create_llm_client(config)
    
    def _create_provider_config(self, provider: str) -> Dict[str, Any]:
        """创建provider配置字典"""
        configs = {
            'dashscope': {
                'provider': 'dashscope',
                'model': 'qwen-turbo',
                'api_key': os.getenv('DASHSCOPE_API_KEY'),
                'base_url': 'https://dashscope.aliyuncs.com/api/v1'
            },
            'minimax': {
                'provider': 'minimax',
                'model': 'abab6-chat',
                'api_key': os.getenv('MINIMAX_API_KEY'),
                'base_url': 'https://api.minimax.chat/v1'
            },
            'openai': {
                'provider': 'openai',
                'model': 'gpt-4',
                'api_key': os.getenv('OPENAI_API_KEY'),
                'base_url': None
            }
        }
        
        return configs.get(provider, configs['dashscope'])
    
    def analyze_style_matrix(self, text: str, 
                            author_name: Optional[str] = None) -> Dict[str, Any]:
        """
        构建文风矩阵分析
        
        Args:
            text: 待分析的文本
            author_name: 作者名称（可选）
            
        Returns:
            dict: 文风矩阵分析结果
        """
        if self.test_mode:
            return self._analyze_style_matrix_mock(text, author_name)
        
        self._init_llm_client()
        
        prompt = f"""请分析以下文本的文风矩阵，从四个维度进行深度分析：

【分析维度】
1. 句法结构（Sentence structure）
   - 节奏剖析：长短句交替的起伏节奏
   - 语态频率：主动语态vs被动语态
   - 句式习惯：复杂句式、从句嵌套等

2. 词汇深度与选择（Vocabulary choices）
   - 术语偏好：高频学术术语
   - 词源倾向：古汉语词、日文借词、文言句式
   - 选词特点：书面语vs口语

3. 语气与叙事声音（Tone and narrative voice）
   - 叙事视角：客观抽离vs主观介入
   - 情感色彩：冷峻vs热情
   - 批判性：强烈批判vs温和建议

4. 学术修辞机制（Rhetorical mechanisms）
   - 修辞偏好：比喻、排比、对比等
   - 逻辑关节：过渡词、因果连词
   - 论证模式：归纳vs演绎

{'【目标作者】' + author_name if author_name else '【分析文本】'}
{text[:5000]}

请以JSON格式输出：
{{
    "sentence_structure": {{
        "rhythm_analysis": "节奏分析描述",
        "voice_frequency": {{"active": 百分比, "passive": 百分比}},
        "sentence_patterns": ["句式特征列表"],
        "examples": ["原文例句"]
    }},
    "vocabulary_choices": {{
        "term_preferences": ["高频术语"],
        "etymology_tendency": "词源倾向描述",
        "register": "语域描述",
        "examples": ["原文例句"]
    }},
    "tone_narrative": {{
        "narrative_perspective": "叙事视角描述",
        "emotional_color": "情感色彩描述",
        "critical_stance": "批判立场描述",
        "examples": ["原文例句"]
    }},
    "rhetorical_patterns": {{
        "rhetorical_preferences": ["修辞偏好"],
        "logical_connectors": ["逻辑连接词"],
        "argumentation_mode": "论证模式描述",
        "examples": ["原文例句"]
    }},
    "overall_style_summary": "整体风格画像（100-200字）"
}}"""
        
        response = self._call_llm(prompt)
        
        try:
            analysis = json.loads(response)
            
            if author_name:
                self.analyzed_styles[author_name] = analysis
            
            return analysis
        except json.JSONDecodeError:
            return self._parse_style_matrix_from_text(response)
    
    def extract_sentence_patterns(self, text: str) -> Dict[str, Any]:
        """
        提取句法结构特征
        
        Args:
            text: 待分析的文本
            
        Returns:
            dict: 句法结构特征
        """
        sentences = self._split_sentences(text)
        
        sentence_lengths = [len(s) for s in sentences]
        
        avg_length = sum(sentence_lengths) / len(sentence_lengths) if sentences else 0
        
        active_count = len(re.findall(r'[^\s]+(?:が|は|を|に)[^\s]+(?:が|を|に|で)[^\s]+[^\s]+', text))
        passive_count = len(re.findall(r'[^\s]+(?:れた|られる|される)', text))
        
        total_verbs = active_count + passive_count
        active_ratio = active_count / total_verbs if total_verbs > 0 else 0.5
        passive_ratio = passive_count / total_verbs if total_verbs > 0 else 0
        
        complex_sentences = len(re.findall(r'[,，][^,，]*[,，][^,，]*[,，]', text))
        
        long_sentences = [s for s in sentences if len(s) > 50]
        short_sentences = [s for s in sentences if len(s) <= 20]
        
        return {
            'average_length': avg_length,
            'voice_distribution': {
                'active': active_ratio,
                'passive': passive_ratio
            },
            'complex_sentences_count': complex_sentences,
            'long_sentences_ratio': len(long_sentences) / len(sentences) if sentences else 0,
            'short_sentences_ratio': len(short_sentences) / len(sentences) if sentences else 0,
            'sample_sentences': {
                'long': long_sentences[:3] if long_sentences else [],
                'short': short_sentences[:3] if short_sentences else []
            }
        }
    
    def extract_vocabulary_profile(self, text: str) -> Dict[str, Any]:
        """
        提取词汇选择特征
        
        Args:
            text: 待分析的文本
            
        Returns:
            dict: 词汇选择特征
        """
        words = self._tokenize(text)
        
        word_freq = {}
        for word in words:
            if len(word) > 1:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        top_words = sorted_words[:50]
        
        classical_chinese = len(re.findall(r'[之乎者也焉哉]', text))
        total_chars = len(text)
        classical_ratio = classical_chinese / total_chars if total_chars > 0 else 0
        
        academic_terms = self._identify_academic_terms(text)
        
        informal_words = ['大概', '可能', '好像', '我觉得', '其实']
        informal_count = sum(1 for word in informal_words if word in text)
        
        formal_ratio = 1 - (informal_count / len(words)) if words else 1
        
        return {
            'top_frequency_words': top_words,
            'classical_ratio': classical_ratio,
            'academic_terms': academic_terms,
            'formality_score': formal_ratio,
            'estimated_register': 'formal' if formal_ratio > 0.7 else 'semi-formal' if formal_ratio > 0.4 else 'informal'
        }
    
    def analyze_tone_narrative(self, text: str) -> Dict[str, Any]:
        """
        分析语气与叙事声音
        
        Args:
            text: 待分析的文本
            
        Returns:
            dict: 语气与叙事特征
        """
        subjective_markers = ['我认为', '我觉得', '在我看来', '不言而喻', '毫无疑问']
        objective_markers = ['研究表明', '数据显示', '根据', '客观上', '事实上']
        
        subjective_count = sum(1 for marker in subjective_markers if marker in text)
        objective_count = sum(1 for marker in objective_markers if marker in text)
        
        if subjective_count > objective_count:
            narrative_perspective = 'subjective'
            perspective_description = '以主观视角为主'
        elif objective_count > subjective_count:
            narrative_perspective = 'objective'
            perspective_description = '以客观视角为主'
        else:
            narrative_perspective = 'mixed'
            perspective_description = '主客观结合'
        
        emotional_markers = ['令人', '可惜', '遗憾', '值得', '应该']
        emotional_count = sum(1 for marker in emotional_markers if marker in text)
        
        if emotional_count > 5:
            emotional_color = 'emotional'
        elif emotional_count > 2:
            emotional_color = 'moderate'
        else:
            emotional_color = 'restrained'
        
        critical_markers = ['批判', '反对', '质疑', '错误', '不足', '然而']
        supportive_markers = ['赞同', '肯定', '支持', '正确', '合理']
        
        critical_count = sum(1 for marker in critical_markers if marker in text)
        supportive_count = sum(1 for marker in supportive_markers if marker in text)
        
        if critical_count > supportive_count:
            critical_stance = 'critical'
        elif supportive_count > critical_count:
            critical_stance = 'supportive'
        else:
            critical_stance = 'balanced'
        
        return {
            'narrative_perspective': narrative_perspective,
            'perspective_description': perspective_description,
            'emotional_color': emotional_color,
            'emotional_markers_count': emotional_count,
            'critical_stance': critical_stance,
            'argumentation_balance': critical_count - supportive_count
        }
    
    def analyze_rhetorical_patterns(self, text: str) -> Dict[str, Any]:
        """
        分析学术修辞机制
        
        Args:
            text: 待分析的文本
            
        Returns:
            dict: 修辞模式特征
        """
        metaphor_patterns = [
            r'如同.+一样',
            r'犹如.+一般', 
            r'仿佛.+似的',
            r'像.+那样'
        ]
        
        metaphor_count = 0
        for pattern in metaphor_patterns:
            metaphor_count += len(re.findall(pattern, text))
        
        parallelism_patterns = [
            r'[^，。]+[,，][^，。]+[,，][^，。]+',
            r'不但.+而且.+',
            r'既.+又.+'
        ]
        
        parallelism_count = 0
        for pattern in parallelism_patterns:
            parallelism_count += len(re.findall(pattern, text))
        
        comparison_patterns = [
            r'.+与.+不同',
            r'.+相比',
            r'然而.+则.+',
            r'反观.+'
        ]
        
        comparison_count = 0
        for pattern in comparison_patterns:
            comparison_count += len(re.findall(pattern, text))
        
        logical_connectors = {
            'cause': ['因为', '由于', '所以', '因此'],
            'contrast': ['然而', '但是', '不过', '然而'],
            'addition': ['此外', '并且', '同时', '再者'],
            'conclusion': ['总之', '综上所述', '简言之', '由此可见']
        }
        
        connector_usage = {}
        for category, connectors in logical_connectors.items():
            count = sum(1 for conn in connectors if conn in text)
            connector_usage[category] = count
        
        if metaphor_count > 3:
            rhetorical_preference = 'metaphor-heavy'
        elif parallelism_count > 2:
            rhetorical_preference = 'parallelism-heavy'
        elif comparison_count > 2:
            rhetorical_preference = 'comparison-heavy'
        else:
            rhetorical_preference = 'logical-argumentation'
        
        return {
            'metaphor_count': metaphor_count,
            'parallelism_count': parallelism_count,
            'comparison_count': comparison_count,
            'rhetorical_preference': rhetorical_preference,
            'logical_connectors': connector_usage,
            'argumentation_mode': 'inductive' if connector_usage['cause']['count'] > connector_usage['conclusion']['count'] else 'deductive'
        }
    
    def transfer_style(self, text: str, 
                      style_matrix: Dict[str, Any]) -> str:
        """
        基于文风矩阵进行文本改写
        
        Args:
            text: 待改写的文本
            style_matrix: 目标文风矩阵
            
        Returns:
            str: 改写后的文本
        """
        if self.test_mode:
            return self._transfer_style_mock(text, style_matrix)
        
        self._init_llm_client()
        
        style_description = self._format_style_matrix_for_prompt(style_matrix)
        
        prompt = f"""请将以下文本改写成目标文风。

【待改写文本】
{text}

【目标文风要求】
{style_description}

【输出要求】
直接输出改写后的文本，保持专业度，无需输出任何解释或分析过程。"""
        
        return self._call_llm(prompt)
    
    def few_shot_style_imitation(self, text: str,
                                reference_examples: List[Tuple[str, str]],
                                author_name: Optional[str] = None) -> str:
        """
        少样本文风模仿
        
        Args:
            text: 待模仿的文本
            reference_examples: 参考示例列表 [(原文, 目标风格文)...]
            author_name: 作者名称
            
        Returns:
            str: 模仿目标文风的文本
        """
        if self.test_mode:
            return self._few_shot_mock(text, reference_examples)
        
        self._init_llm_client()
        
        examples_text = "\n\n".join([
            f"【示例 {i+1}】\n原文：{orig}\n目标风格：{target}"
            for i, (orig, target) in enumerate(reference_examples)
        ])
        
        prompt = f"""请参考以下示例，学习并模仿目标文风来改写文本。

{examples_text}

【待改写文本】
{text}

请直接输出改写后的文本，保持专业度，无需输出任何解释。"""
        
        response = self._call_llm(prompt)
        
        if author_name and author_name not in self.analyzed_styles:
            analysis = self.analyze_style_matrix(
                '\n'.join([orig for orig, _ in reference_examples]),
                author_name
            )
        
        return response
    
    def batch_style_analysis(self, documents: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        批量分析多个文档的文风
        
        Args:
            documents: 文档列表，每项包含text和author
            
        Returns:
            list: 分析结果列表
        """
        results = []
        
        for doc in documents:
            text = doc.get('text', '')
            author = doc.get('author')
            
            analysis = self.analyze_style_matrix(text, author)
            
            results.append({
                'author': author,
                'analysis': analysis,
                'text_length': len(text)
            })
        
        return results
    
    def compare_styles(self, style1: Dict[str, Any], 
                      style2: Dict[str, Any],
                      style1_name: str = 'Style 1',
                      style2_name: str = 'Style 2') -> Dict[str, Any]:
        """
        对比两种文风
        
        Args:
            style1: 第一种文风矩阵
            style2: 第二种文风矩阵
            style1_name: 第一种文风名称
            style2_name: 第二种文风名称
            
        Returns:
            dict: 对比分析结果
        """
        comparison = {
            'styles': {
                style1_name: style1,
                style2_name: style2
            },
            'similarities': [],
            'differences': []
        }
        
        if style1.get('overall_style_summary') and style2.get('overall_style_summary'):
            summary1 = style1['overall_style_summary'][:100]
            summary2 = style2['overall_style_summary'][:100]
            
            common_words = set(summary1.split()) & set(summary2.split())
            if len(common_words) > 5:
                comparison['similarities'].append(f"都注重学术性论述")
            
            if summary1 != summary2:
                comparison['differences'].append(f"整体风格定位不同")
        
        return comparison
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM API"""
        try:
            full_prompt = f"{self.DEFAULT_SYSTEM_PROMPT}\n\n{prompt}"
            result = self.llm_client._call_llm(full_prompt, temperature=0.3)
            return result.get('content', '')
        except Exception as e:
            raise RuntimeError(f"LLM API调用失败: {str(e)}")
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        return [s.strip() for s in re.split(r'[。！？；\n]+', text) if s.strip()]
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        return re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
    
    def _identify_academic_terms(self, text: str) -> List[str]:
        """识别学术术语"""
        academic_suffixes = ['论', '主义', '性', '化', '度', '感']
        
        terms = []
        for suffix in academic_suffixes:
            pattern = rf'[\u4e00-\u9fff]{{2,}}{suffix}'
            matches = re.findall(pattern, text)
            terms.extend(matches[:5])
        
        return list(set(terms))[:20]
    
    def _format_style_matrix_for_prompt(self, style_matrix: Dict[str, Any]) -> str:
        """格式化文风矩阵为提示词"""
        lines = []
        
        for dimension, analysis in style_matrix.items():
            if dimension == 'overall_style_summary':
                continue
            
            lines.append(f"\n【{dimension}】")
            
            if isinstance(analysis, dict):
                for key, value in analysis.items():
                    if isinstance(value, list):
                        lines.append(f"- {key}: {', '.join(value[:3])}")
                    else:
                        lines.append(f"- {key}: {value}")
            elif isinstance(analysis, str):
                lines.append(f"- {analysis}")
        
        if 'overall_style_summary' in style_matrix:
            lines.append(f"\n【整体风格】")
            lines.append(style_matrix['overall_style_summary'])
        
        return '\n'.join(lines)
    
    def _parse_style_matrix_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中解析文风矩阵"""
        return {
            'sentence_structure': {'analysis': '基于文本分析得出'},
            'vocabulary_choices': {'analysis': '基于词汇统计得出'},
            'tone_narrative': {'analysis': '基于语气标记得出'},
            'rhetorical_patterns': {'analysis': '基于修辞识别得出'},
            'overall_style_summary': text[:200]
        }
    
    def _analyze_style_matrix_mock(self, text: str, 
                                 author_name: Optional[str]) -> Dict[str, Any]:
        """模拟文风矩阵分析"""
        mock_analysis = {
            'sentence_structure': {
                'rhythm_analysis': '以长句为主，节奏沉稳有力',
                'voice_frequency': {'active': 0.7, 'passive': 0.3},
                'sentence_patterns': [
                    '善用复合从句构建严密论证',
                    '长短句交替形成节奏感',
                    '偏好使用书面语句式'
                ],
                'examples': [
                    '在明治维新之后，日本社会经历了深刻的变革。',
                    '这一现象反映了深层次的文化转型。'
                ]
            },
            'vocabulary_choices': {
                'term_preferences': [
                    '文明', '实学', '独立', '开化', '道理', '西洋'
                ],
                'etymology_tendency': '倾向于使用和制汉语和明治时期的学术用语',
                'register': '正式书面语',
                'examples': [
                    '文明开化',
                    '独立自尊',
                    '实学精神'
                ]
            },
            'tone_narrative': {
                'narrative_perspective': '研究者视角，客观理性',
                'emotional_color': '克制冷静，偶有批判锋芒',
                'critical_stance': '批判性强，尤其对封建残余和虚伪道德',
                'examples': [
                    '必须指出，这种观点存在根本性的误解。',
                    '从历史事实来看，情况恰恰相反。'
                ]
            },
            'rhetorical_patterns': {
                'rhetorical_preferences': [
                    '对比论证',
                    '举例说明',
                    '因果推演'
                ],
                'logical_connectors': [
                    '然而', '因此', '此外', '综上所述'
                ],
                'argumentation_mode': '演绎为主，辅以归纳',
                'examples': [
                    '不仅...而且...',
                    '既...又...'
                ]
            },
            'overall_style_summary': f"""本段文本体现了典型的明治时期学术写作风格：文风严谨而不失锋芒，论述逻辑严密，语言典雅庄重。善用对比手法凸显论点，对封建思想持批判态度，同时积极倡导文明开化之道。整体呈现出启蒙思想家的使命感和社会关怀。"""
        }
        
        if author_name:
            self.analyzed_styles[author_name] = mock_analysis
        
        return mock_analysis
    
    def _transfer_style_mock(self, text: str, 
                            style_matrix: Dict[str, Any]) -> str:
        """模拟文风迁移"""
        summary = style_matrix.get('overall_style_summary', '')
        
        if '明治' in summary or '启蒙' in summary:
            return f"""明治时代之学术，其要义在于严谨与务实并行。今观此文本，当以实学之精神，重构其论述之框架。

夫学问之道，贵在切合实际，不尚空谈。文中所论，虽有一定之理，然未免过于直白，缺乏论证之深度。

若以此法为之，则当：先述其事，后明其理，终指其用。庶几可以成一家之言，而有益于世道人心也。"""
        
        return f"""基于文风分析，对原文进行如下改写：

{text}

（以上为模拟改写结果）"""
    
    def _few_shot_mock(self, text: str,
                      reference_examples: List[Tuple[str, str]]) -> str:
        """模拟少样本学习"""
        return f"""参考{len(reference_examples)}个示例，完成文风模仿：

【待改写文本】
{text}

【改写结果】
经分析参考示例的文风特征，现按照目标风格进行改写：

近代战争不仅是战场上的厮杀，更是交战各方国力及动员能力的较量。在战争爆发初期，政府就巨额军费的筹措，有捐款说、内债说和外债说等主张。最终内债说上升为国家意志。政府脱离和平时期的财政运作模式，在战争期间超常规地动员财政金融机器为战争筹资。

（有学者认为，因财界及民间无私地支援战争，日本才成功地筹集到战争所需经费；此说过分强调感情因素的作用，忽视了政府的财政金融操作才是顺利实现军费筹措的根本。）"""


from modules.llm_client import create_llm_client


def create_style_transfer(api_provider: str = "qwen",
                         test_mode: bool = True) -> StyleTransfer:
    """
    工厂函数：创建文风分析与迁移模块实例
    
    Args:
        api_provider: API提供商
        test_mode: 是否使用测试模式
        
    Returns:
        StyleTransfer: 配置好的模块实例
    """
    return StyleTransfer(api_provider=api_provider, test_mode=test_mode)
