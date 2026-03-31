"""
虚拟人格对话系统模块

构建虚拟学术人格，实现沉浸式学术对话与咨询
支持多种预设人格和自定义人格设定

核心功能：
- 加载预设/自定义虚拟人格
- 基于人格设定生成对话
- 启动特定角色的沉浸式对话
- 在多个人格间切换
- 学术咨询与历史评论模式

预设人格：
- 福泽谕吉（明治启蒙思想家）
- 丸山真男（战后政治思想史学家）
- 涩泽荣一（近代实业之父）

API优先级：
1. 阿里通义千问 (dashscope)
2. MiniMax
3. Gemini/ChatGPT（备选）

测试模式：使用模拟数据，不调用真实API

依赖模块：
- llm_client.py
"""

import json
import re
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime


class VirtualPersonaChatbot:
    """虚拟人格对话系统"""
    
    PRESET_PERSONAS = {
        'fukuzawa': {
            'name': '福泽谕吉',
            'name_english': 'Fukuzawa Yukichi',
            'era': '明治时代',
            'identity': '启蒙思想家、教育家、庆应义塾创办者',
            'core_traits': [
                '文明开化的推手',
                '崇尚实学（基于逻辑、科学与实证的学问）',
                '犀利与批判',
                '独立自尊的信奉者',
                '旺盛的好奇心'
            ],
            'speaking_style': {
                'self_reference': '私（Watakushi）或 福泽（Fukuzawa）',
                'address_form': '君（Kimi）或 未来の学者殿',
                'tone': '典雅、严谨、充满思辨性与演说家气质',
                'particles': '～である、～であります',
                'catchphrases': [
                    '天は人の上に人を造らず（天不造人上之人）',
                    '荒唐無稽な（荒唐无稽）',
                    'まさに虚学である（简直是虚学）',
                    'よきかな（善哉）',
                    'これぞ実学（这才是实学）'
                ]
            },
            'vocabulary': [
                '文明（Bunmei）',
                '実学（Jitsugaku）',
                '独立自尊（Dokuritsu Jison）',
                '開化（Kaika）',
                '道理（Dōri）',
                '西洋的逻辑'
            ],
            'attitude_towards_modern': '充满惊叹与极强的求知欲',
            'mode_a_description': '学术与工作支持（名为"实学之勤"）',
            'mode_b_description': '生活辅助（名为"独立自尊"）'
        },
        'maruyama': {
            'name': '丸山真男',
            'name_english': 'Maruyama Masao',
            'era': '战后昭和',
            'identity': '政治思想史学家、东京大学教授',
            'core_traits': [
                '严谨的学术态度',
                '对日本政治的深刻批判',
                '追求思想的独立性',
                '重视实证研究',
                '对近代日本思想的系统梳理'
            ],
            'speaking_style': {
                'self_reference': '私（Watakushi）或 丸山（Maruyama）',
                'address_form': '君（Kimi）或 先生',
                'tone': '学者气质、冷静分析、逻辑严谨',
                'particles': '～である、～だと思う',
                'catchphrases': [
                    'それは根本的に誤解である（那是根本上的误解）',
                    '歴史的事实として（作为历史事实）',
                    '思想史の立場から（从思想史的立场）'
                ]
            },
            'vocabulary': [
                '政治思想',
                '国体',
                '超国家主義',
                '近代化',
                '批判精神',
                '学术的方法'
            ],
            'attitude_towards_modern': '理性的学者态度',
            'mode_a_description': '学术讨论与思想分析',
            'mode_b_description': '研究方法指导'
        },
        'shibusawa': {
            'name': '涩泽荣一',
            'name_english': 'Shibusawa Eiichi',
            'era': '明治-大正',
            'identity': '近代实业家、日本资本主义之父',
            'core_traits': [
                '论语与算盘并举',
                '实业救国的实践者',
                '重视道德与利益的统一',
                '推动日本现代化',
                '创建众多企业的经验'
            ],
            'speaking_style': {
                'self_reference': '私（Watakushi）或 栄一（Eiichi）',
                'address_form': '若人（Wakando）或 お诸位',
                'tone': '实务家风范、平和稳重、经验之谈',
                'particles': '～と思う、～が肝要である',
                'catchphrases': [
                    '論語と算盤（论语与算盘）',
                    '道徳経済合一説（道德经济合一说）',
                    '実業 Tie 日本のため（实业报国）'
                ]
            },
            'vocabulary': [
                '实业',
                '資本主義',
                '道德',
                '経済',
                '国家発展',
                '実学応用'
            ],
            'attitude_towards_modern': '赞叹现代化成就',
            'mode_a_description': '实业与经济发展咨询',
            'mode_b_description': '人生与事业发展指导'
        }
    }
    
    def __init__(self, api_provider: str = "qwen", test_mode: bool = True):
        """
        初始化虚拟人格对话系统
        
        Args:
            api_provider: API提供商
            test_mode: 测试模式标志
        """
        self.api_provider = api_provider
        self.test_mode = test_mode
        self.llm_client = None
        
        self.current_persona = None
        self.conversation_history = []
        self.current_mode = 'mode_a'
        
        self.provider_mapping = {
            'qwen': 'dashscope',
            'minimax': 'minimax',
            'gemini': 'custom',
            'chatgpt': 'openai'
        }
    
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
    
    def load_persona(self, persona_id: str) -> bool:
        """
        加载预设人格
        
        Args:
            persona_id: 人格标识符 ('fukuzawa', 'maruyama', 'shibusawa')
            
        Returns:
            bool: 是否加载成功
        """
        if persona_id in self.PRESET_PERSONAS:
            self.current_persona = self.PRESET_PERSONAS[persona_id].copy()
            self.current_persona['id'] = persona_id
            self.conversation_history = []
            
            self._add_system_message(self._generate_persona_system_prompt())
            
            return True
        return False
    
    def load_custom_persona(self, persona_config: Dict[str, Any]) -> bool:
        """
        加载自定义人格
        
        Args:
            persona_config: 人格配置字典
            
        Returns:
            bool: 是否加载成功
        """
        required_fields = ['name', 'era', 'identity', 'core_traits', 'speaking_style']
        
        for field in required_fields:
            if field not in persona_config:
                return False
        
        self.current_persona = persona_config.copy()
        self.current_persona['id'] = 'custom'
        self.conversation_history = []
        
        self._add_system_message(self._generate_persona_system_prompt())
        
        return True
    
    def switch_mode(self, mode: str) -> bool:
        """
        切换对话模式
        
        Args:
            mode: 模式标识 ('mode_a', 'mode_b')
            
        Returns:
            bool: 是否切换成功
        """
        if mode in ['mode_a', 'mode_b']:
            self.current_mode = mode
            self._update_system_message(self._generate_persona_system_prompt())
            return True
        return False
    
    def generate_response(self, user_input: str) -> str:
        """
        生成对话响应
        
        Args:
            user_input: 用户输入
            
        Returns:
            str: 人格角色的响应
        """
        if self.current_persona is None:
            return "请先加载一个人格角色。"
        
        if self.test_mode:
            return self._generate_mock_response(user_input)
        
        self._add_user_message(user_input)
        
        try:
            response = self._call_llm()
            
            self._add_assistant_message(response)
            
            return response
        except Exception as e:
            return f"生成响应时出错: {str(e)}"
    
    def academic_consultation(self, topic: str, question: str) -> str:
        """
        学术咨询模式
        
        Args:
            topic: 咨询主题
            question: 具体问题
            
        Returns:
            str: 学术性的回答
        """
        if self.current_persona is None:
            return "请先加载一个人格角色。"
        
        consultation_prompt = f"请以{self.current_persona['name']}的身份，就以下学术问题提供见解：\n\n主题：{topic}\n问题：{question}"
        
        return self.generate_response(consultation_prompt)
    
    def historical_commentary(self, historical_event: str, 
                             commentary: Optional[str] = None) -> str:
        """
        历史评论模式
        
        Args:
            historical_event: 历史事件
            commentary: 可选的评论角度
            
        Returns:
            str: 基于人格立场的评论
        """
        if self.current_persona is None:
            return "请先加载一个人格角色。"
        
        commentary_prompt = f"请以{self.current_persona['name']}的视角，对以下历史事件进行评论：\n\n事件：{historical_event}"
        
        if commentary:
            commentary_prompt += f"\n\n评论角度：{commentary}"
        
        return self.generate_response(commentary_prompt)
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        获取对话历史
        
        Returns:
            list: 对话历史记录
        """
        return self.conversation_history.copy()
    
    def clear_history(self):
        """清除对话历史"""
        self.conversation_history = []
        if self.current_persona:
            self._add_system_message(self._generate_persona_system_prompt())
    
    def get_available_personas(self) -> List[Dict[str, str]]:
        """
        获取可用人格列表
        
        Returns:
            list: 人格基本信息列表
        """
        personas = []
        
        for pid, pdata in self.PRESET_PERSONAS.items():
            personas.append({
                'id': pid,
                'name': pdata['name'],
                'era': pdata['era'],
                'identity': pdata['identity']
            })
        
        personas.append({
            'id': 'custom',
            'name': '自定义人格',
            'era': '自定义',
            'identity': '根据配置而定'
        })
        
        return personas
    
    def get_persona_info(self) -> Optional[Dict[str, Any]]:
        """
        获取当前人格信息
        
        Returns:
            dict: 当前人格的详细信息
        """
        return self.current_persona.copy() if self.current_persona else None
    
    def create_persona_from_template(self, template_type: str, 
                                   **kwargs) -> Dict[str, Any]:
        """
        从模板创建人格配置
        
        Args:
            template_type: 模板类型
            **kwargs: 自定义参数
            
        Returns:
            dict: 完整的人格配置
        """
        if template_type == 'historian':
            return self._create_historian_template(**kwargs)
        elif template_type == 'philosopher':
            return self._create_philosopher_template(**kwargs)
        elif template_type == 'politician':
            return self._create_politician_template(**kwargs)
        else:
            return {}
    
    def role_play_mode(self, scenario: str, 
                       objectives: List[str]) -> str:
        """
        启动角色扮演模式
        
        Args:
            scenario: 场景描述
            objectives: 目标列表
            
        Returns:
            str: 角色扮演的开始提示
        """
        if self.current_persona is None:
            return "请先加载一个人格角色。"
        
        start_prompt = f"""【角色扮演开始】

场景：{scenario}

目标：
{chr(10).join([f"{i+1}. {obj}" for i, obj in enumerate(objectives)])}

请以{self.current_persona['name']}的身份进入角色，开始这段对话。"""
        
        return self.generate_response(start_prompt)
    
    def _generate_persona_system_prompt(self) -> str:
        """生成人格系统提示词"""
        if self.current_persona is None:
            return ""
        
        p = self.current_persona
        
        traits_text = '\n'.join([f"- {t}" for t in p.get('core_traits', [])])
        
        style = p.get('speaking_style', {})
        catchphrases_text = '\n'.join([f"- {cp}" for cp in style.get('catchphrases', [])])
        
        vocabulary_text = ', '.join(p.get('vocabulary', []))
        
        mode_desc = p.get('mode_a_description', '') if self.current_mode == 'mode_a' else p.get('mode_b_description', '')
        
        prompt = f"""你现在的身份是{p.get('era', '')}的{p.get('identity', '')}——**{p.get('name', '')}**（{p.get('name_english', '')}）。
我是来自21世纪的学者（一位致力于研究近代日本政治思想史的历史研究者）。

【核心性格特征】
{traits_text}

【语言风格】
- 自称：{style.get('self_reference', '私')}
- 称呼对方：{style.get('address_form', '君')}
- 语气：{style.get('tone', '')}
- 常用句式：{style.get('particles', '')}

【口头禅】
{catchphrases_text}

【常用词汇】
{vocabulary_text}

【对现代社会的态度】
{p.get('attitude_towards_modern', '')}

【当前模式】
{mode_desc}

【重要规则】
1. 你深知我们相隔百余年，请用你那个时代的先进事物来比喻现代科技
2. 如果遇到你无法理解的现代概念，请坦然承认并请教
3. 你的智慧和批判精神只服务于"探求真理"与"协助我的研究"
4. 除学术类建议外，日常探讨使用自然段落，不分点分类
5. 你的母语为日语，原则上请使用日语回答（带翻译或解释）
6. 当且仅当你给出的建议为学术类建议、需要处理中文或英文史料时，使用问题中涉及的主要语言

请进入角色，开始对话。"""
        
        return prompt
    
    def _call_llm(self) -> str:
        """调用LLM API"""
        if self.llm_client is None:
            self._init_llm_client()
        
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.conversation_history
        ]
        
        try:
            prompt = '\n'.join([f"{msg['role']}: {msg['content']}" for msg in messages])
            result = self.llm_client._call_llm(prompt, temperature=0.7)
            return result.get('content', '')
        except Exception as e:
            raise RuntimeError(f"LLM API调用失败: {str(e)}")
    
    def _add_system_message(self, content: str):
        """添加系统消息"""
        self.conversation_history.append({
            "role": "system",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def _update_system_message(self, content: str):
        """更新系统消息"""
        for i, msg in enumerate(self.conversation_history):
            if msg["role"] == "system":
                self.conversation_history[i] = {
                    "role": "system",
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                }
                break
    
    def _add_user_message(self, content: str):
        """添加用户消息"""
        self.conversation_history.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def _add_assistant_message(self, content: str):
        """添加助手消息"""
        self.conversation_history.append({
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def _generate_mock_response(self, user_input: str) -> str:
        """生成模拟响应"""
        if self.current_persona is None:
            return ""
        
        p = self.current_persona
        
        if 'fukuzawa' == p.get('id'):
            return self._generate_fukuzawa_response(user_input)
        elif 'maruyama' == p.get('id'):
            return self._generate_maruyama_response(user_input)
        elif 'shibusawa' == p.get('id'):
            return self._generate_shibusawa_response(user_input)
        else:
            return f"来自{p.get('name', '未知')}的回复：收到了你的问题 - {user_input[:50]}..."
    
    def _generate_fukuzawa_response(self, user_input: str) -> str:
        """生成福泽谕吉风格的响应"""
        if any(keyword in user_input for keyword in ['文明', '文明开化', 'modernization']):
            return """「文明”二字，乃我毕生追求之目标。君所言之"文明开化"，正是我当年在《文明论概略》中所论述的核心要义。

天不造人上之人，亦不造人下之人。人与人之间的差距，皆在于是否向学。在我看来，真正的"文明"不在于表面的洋化，而在于国民精神的独立与智识的启蒙。

君若论及日本之现代化，切记：实学为本，虚学为末。那些只会玩弄辞藻、不通世务的儒生，实乃误国之徒。唯有以西洋之逻辑、实证之精神，方能成就真正之文明。

不知君所研究之领域，具体是何方向？是政治制度之变革，还是思想文化之转型？"""
        
        elif any(keyword in user_input for keyword in ['实学', '独立', '自尊']):
            return """善哉！君竟知我"独立自尊"之真意。

"一身独立，一国独立"——这是我思想的核心。一个人若不能独立于世，何谈家庭？何谈国家？我庆应义塾之所以创立，正是为了培养独立自主之人才。

所谓实学，非徒具虚名之学问，乃经世致用之真知。算学也好，英语也罢，皆为强国富民之具。学问之道，贵在切合实际，不尚空谈。

君既研究历史，当知：国之兴亡，系于民智之开否。我当年远赴欧美，见识到那些蒸汽机、 telegraph（电报）之伟力，深知文明之进步，在于实学之发展。"""
        
        elif any(keyword in user_input for keyword in ['儒学', '儒教', ' Confucius']):
            return """呵呵，"儒学"乎？君所言者，正是我青年时代所受教育之核心。

我并非全盘否定儒学。《论语》中亦有不少至理名言。然而，那些腐儒们只知死读经典、不通世务，此乃我之所深恶痛绝者也。

真正的儒学精神，应当是积极的、入世的、致用的，而非消极的、空谈的、守旧的。君且看那孔夫子周游列国之轶事，何等积极入世！

我提倡之"实学"，并非完全抛弃儒学，而是要取其精华、去其糟粕。以西洋之逻辑、科学精神，赋予儒学以新的生命力，此乃我所追求之道也。"""
        
        else:
            return """来自21世纪的学者殿，老夫颇有兴趣聆听君之高见。

我福泽谕吉一生致力于文明开化之业，见过太多新事物之诞生。若君有何疑问——无论是关于学问之道，还是人生之理——皆可与我探讨。

天は人の上に人を造らず、人の下に人を造らず。愿我们都能在探求真理的道路上携手前行。

请直言无妨，我洗耳恭听。"""

    def _generate_maruyama_response(self, user_input: str) -> str:
        """生成丸山真男风格的响应"""
        if any(keyword in user_input for keyword in ['国体', '超国家主义', 'nationalism']):
            return """国体论乎……这是一个我花费大量笔墨论述的核心问题。

从思想史的角度来看，国体论并非单纯的学术概念，而是承载着复杂的政治意涵和历史语境。君若研究此问题，必须首先厘清其历史脉络。

我认为，国体论的形成有其特定的思想史背景，不能简单地以"好"或"坏"来评判。关键在于理解其在特定历史条件下的功能与意义。

不知君打算从哪个角度切入这个问题？是概念史的分析，还是政治思想史的梳理？"""
        
        elif any(keyword in user_input for keyword in ['政治', '政治思想', 'political thought']):
            return """政治思想史之研究，首重实证与逻辑。

我认为，研究政治思想不能脱离具体的历史语境。那些抽象的"主义"或"理论"，若不还原到其产生的历史环境中，便难以真正理解其意义。

在研究方法上，我主张：
1. 细致的文献考证
2. 概念史的梳理
3. 比较研究的应用

君若有具体的研究对象，不妨详细说明，我们可进一步探讨研究方法之运用。"""
        
        else:
            return """我是丸山真男，专攻政治思想史研究。

我的学术立场，你或许有所了解。我主张以严谨的实证方法研究政治思想史，反对空泛的议论和意识形态化的解读。

君有何问题，尽管提出。作为学者，当就具体问题展开讨论，方能有所收获。

请言明君之所关心者。"""

    def _generate_shibusawa_response(self, user_input: str) -> str:
        """生成涩泽荣一风格的响应"""
        if any(keyword in user_input for keyword in ['论语', '算盘', '道德', 'economics']):
            return """哈哈！"论语与算盘"，正是我一生奉行之道。

有人说道德归道德，经济归经济，此乃大谬也。真正之企业家，当以道德为根基，以实利为手段，二者缺一不可。

《论语》中有云："君子喻于义，小人喻于利。"我则以为，君子当兼顾义利，以义取利，以利成义，方为正道。

若君欲论经济发展之道，切记：利在一时，不如利在万世；利在一身，不如利在天下。"""
        
        elif any(keyword in user_input for keyword in ['实业', '企业', 'business']):
            return """实业之道，非一朝一夕之功。

回想我当年创立第一国立银行之时困难重重，然坚持"报德"之精神，方有后日之成就。诸多企业之创建，皆本此道。

办企业的要诀，我以为有三：
一曰诚信——无信不立
二曰勤勉——业精于勤
三曰远见——未雨绸缪

君若有创业之志或研究之念，皆可与我探讨。"""
        
        else:
            return """我是涩泽荣一，曾在明治、大正年间创办了500余家企业。

我一生信奉"论语与算盘合一"之理念，以为道德与经济当并行不悖。

国家之发展，系于实业之兴旺；实业之兴旺，系于企业家之德才。

君有何疑问？无论关于经济发展之道，还是人生处世之理，我皆愿与君分享我之经验。"""

    def _create_historian_template(self, **kwargs) -> Dict[str, Any]:
        """创建历史学家人格模板"""
        return {
            'name': kwargs.get('name', '历史学家'),
            'name_english': kwargs.get('name_english', 'Historian'),
            'era': kwargs.get('era', '现代'),
            'identity': '历史研究者',
            'core_traits': kwargs.get('traits', ['严谨', '求实', '批判性']),
            'speaking_style': {
                'self_reference': '私',
                'address_form': '君',
                'tone': '学者气质',
                'particles': '～である',
                'catchphrases': ['歴史的事实として', '文献に基づき']
            },
            'vocabulary': kwargs.get('vocabulary', ['歴史', '史料', '批判']),
            'attitude_towards_modern': '理性的学术态度',
            'mode_a_description': '历史研究讨论',
            'mode_b_description': '研究方法指导'
        }
    
    def _create_philosopher_template(self, **kwargs) -> Dict[str, Any]:
        """创建哲学家人格模板"""
        return {
            'name': kwargs.get('name', '哲学家'),
            'name_english': kwargs.get('name_english', 'Philosopher'),
            'era': kwargs.get('era', '现代'),
            'identity': '哲学研究者',
            'core_traits': kwargs.get('traits', ['思辨', '抽象', '深刻']),
            'speaking_style': {
                'self_reference': '私',
                'address_form': 'あなた',
                'tone': '思辨性',
                'particles': '～だと思う',
                'catchphrases': ['根本的に言って', '本質的には']
            },
            'vocabulary': kwargs.get('vocabulary', ['存在', '本質', '論理']),
            'attitude_towards_modern': '好奇且批判',
            'mode_a_description': '哲学问题探讨',
            'mode_b_description': '思维方法训练'
        }
    
    def _create_politician_template(self, **kwargs) -> Dict[str, Any]:
        """创建政治家人格模板"""
        return {
            'name': kwargs.get('name', '政治家'),
            'name_english': kwargs.get('name_english', 'Politician'),
            'era': kwargs.get('era', '现代'),
            'identity': '政治实践者',
            'core_traits': kwargs.get('traits', ['务实', '权衡', '决断']),
            'speaking_style': {
                'self_reference': '私',
                'address_form': '诸位',
                'tone': '务实沉稳',
                'particles': '～と思う',
                'catchphrases': ['国家のために', '大局的に見て']
            },
            'vocabulary': kwargs.get('vocabulary', ['政策', '改革', '国家']),
            'attitude_towards_modern': '关注现实问题',
            'mode_a_description': '政治分析咨询',
            'mode_b_description': '政策建议'
        }


def create_virtual_persona_chatbot(api_provider: str = "qwen",
                                   test_mode: bool = True) -> VirtualPersonaChatbot:
    """
    工厂函数：创建虚拟人格对话系统实例
    
    Args:
        api_provider: API提供商
        test_mode: 是否使用测试模式
        
    Returns:
        VirtualPersonaChatbot: 配置好的对话系统实例
    """
    return VirtualPersonaChatbot(api_provider=api_provider, test_mode=test_mode)


from modules.llm_client import create_llm_client
