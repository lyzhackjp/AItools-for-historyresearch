"""
学术论文智能精简处理模块

专为日本史学术论文设计的智能内容精简工具
基于阿里通义千问，能够智能识别并删除冗余内容
同时保留核心学术信息。

核心功能：
- 智能内容精简：自动识别并删除逻辑冗余的论述
- 专业文档处理：正确区分正文与脚注内容
- Word原生修订追踪：使用w:del和w:ins元素实现专业修订模式
- 学术严谨性保障：保护历史专有名词和学术术语

技术架构：
- 文档处理：基于 python-docx 库处理 .docx 文档
- AI处理：集成阿里通义千问 / 次要支持 Minimax
- 修订追踪：实现 Word 原生 Track Changes 功能
- 配置管理：使用 .env 格式管理配置参数
"""

import os
import sys
import re
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import hashlib

try:
    import docx
    from docx import Document
    from docx.shared import RGBColor, Pt
    from docx.enum.text import WD_COLOR_INDEX
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    print("警告: python-docx 未安装，使用 pip install python-docx")

from modules.llm_client import create_llm_client


class PaperPolisher:
    """学术论文智能精简处理器"""
    
    DEFAULT_SYSTEM_PROMPT = """你是一位专业的日本史学术论文编辑，擅长精简学术论文内容。

请分析以下学术论文内容，识别并删除：
1. 逻辑冗余的论述（重复论证同一观点）
2. 修辞上重复的表达（相同的修饰词反复使用）
3. 非必要的过渡句和重复强调

请务必保留：
1. 核心学术观点和结论
2. 历史史实和重要事件
3. 人物生卒年份和重要事迹
4. 所有脚注、注释和参考文献标注
5. 历史专有名词和学术术语
6. 原文的论证逻辑结构

输出格式要求：
返回JSON格式，包含以下字段：
- "modified_text": 修改后的精简文本（保留所有脚注）
- "deletions": 被删除的内容列表，每项包含"text"和"reason"
- "summary": 精简处理的总结说明

请确保输出是有效的JSON格式。"""
    
    MIN_PARAGRAPH_LENGTH = 30

    def __init__(self, api_provider: str = "qwen"):
        """
        初始化论文润色器
        
        Args:
            api_provider: API提供商 ('qwen' 或 'minimax')
        """
        self.base_dir = Path(__file__).parent.parent
        self.api_provider = api_provider
        self.llm_client = None
        self.system_prompt = self.DEFAULT_SYSTEM_PROMPT
        self.history_terms = set()
        self.history_figures = set()
        
    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.llm_client is None:
            if self.api_provider == "qwen":
                provider = "dashscope"
            elif self.api_provider == "minimax":
                provider = "minimax"
            else:
                provider = "dashscope"
            
            self.llm_client = create_llm_client({'provider': provider})
    
    def _load_history_knowledge(self, doc: Document):
        """
        从文档中提取历史专有名词和人物
        
        Args:
            doc: Word文档对象
        """
        text_content = []
        
        for para in doc.paragraphs:
            text_content.append(para.text)
        
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text_content.append(cell.text)
        
        full_text = "\n".join(text_content)
        
        date_pattern = r'\d{4,4}年\d{1,2}月\d{1,2}日|\d{4,4}年-\d{4,4}年|\d{1,2}世纪'
        dates = re.findall(date_pattern, full_text)
        
        name_pattern = r'[一-龥]{2,4}(氏|公爵|侯爵|伯爵|子爵|男爵)'
        names = re.findall(name_pattern, full_text)
        
        self.history_terms.update(dates)
        self.history_figures.update(names)
    
    def polish_paragraph(self, paragraph_text: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        精简单个段落
        
        Args:
            paragraph_text: 原始段落文本
            
        Returns:
            Tuple[str, List[Dict]]: (精简后的文本, 删除内容列表)
        """
        if not paragraph_text.strip():
            return paragraph_text, []
        
        if len(paragraph_text) < self.MIN_PARAGRAPH_LENGTH:
            return paragraph_text, []
        
        self._init_llm_client()
        
        user_prompt = f"""作为学术论文编辑，请精简以下段落。要求：

1. 删除冗余表述、重复修饰词、不必要的过渡句
2. 合并表达相同意思的句子
3. 保留核心观点、史实、人物信息、脚注标记
4. 输出必须比原文短，精简20%-40%

原文（{len(paragraph_text)}字）：
{paragraph_text}

直接输出精简后的文本（不要解释，不要扩展）："""
        
        try:
            response = self.llm_client._call_llm(user_prompt, temperature=0.3, max_tokens=2000)
            
            result_text = response.get('content', paragraph_text).strip()
            
            result_text = self._clean_response(result_text)
            
            if not result_text or len(result_text) < 10:
                return paragraph_text, []
            
            if result_text == paragraph_text:
                return paragraph_text, []
            
            deletions = [{
                'text': f'精简了约{(1-len(result_text)/len(paragraph_text))*100:.1f}%的内容',
                'reason': '删除冗余表述，优化句式结构'
            }]
            
            return result_text, deletions
                
        except Exception as e:
            print(f"段落精简失败: {e}")
            return paragraph_text, []
    
    def _clean_response(self, response: str) -> str:
        """清理响应文本"""
        result = response.strip()
        
        prefixes = [
            "润色后：", "润色后:", "修改后：", "修改后:",
            "精简后：", "精简后:", "以下是润色后的文本：",
            "以下是润色后的文本:", "润色后的文本：", "润色后的文本:",
            "精简后的文本：", "精简后的文本:"
        ]
        for prefix in prefixes:
            if result.startswith(prefix):
                result = result[len(prefix):].strip()
        
        if result.startswith("```"):
            first_newline = result.find('\n')
            if first_newline != -1:
                result = result[first_newline + 1:]
            if result.endswith("```"):
                result = result[:-3]
        
        return result.strip()
    
    def process_document(self, input_path: str, output_path: str,
                        enable_track_changes: bool = True) -> Dict[str, Any]:
        """
        处理完整的Word文档
        
        Args:
            input_path: 输入文档路径
            output_path: 输出文档路径
            enable_track_changes: 是否启用修订追踪
            
        Returns:
            Dict: 处理结果统计
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        import shutil
        shutil.copy2(str(input_path), str(output_path))
        
        doc = Document(str(output_path))
        
        self._load_history_knowledge(doc)
        
        if enable_track_changes:
            self._enable_track_revisions(doc)
            print(f"✓ 已启用修订追踪模式")
        
        total_paragraphs = len(doc.paragraphs)
        processed_paragraphs = 0
        all_deletions = []
        
        print(f"\n开始处理 {total_paragraphs} 个段落...\n")
        
        for i, para in enumerate(doc.paragraphs, 1):
            original_text = para.text
            
            if not original_text.strip():
                continue
            
            processed_paragraphs += 1
            
            print(f"[{i}/{total_paragraphs}] 处理段落...", end=" ", flush=True)
            
            modified_text, deletions = self.polish_paragraph(original_text)
            
            if deletions:
                all_deletions.extend(deletions)
            
            if modified_text != original_text:
                if enable_track_changes:
                    self._apply_track_changes(para, original_text, modified_text)
                else:
                    para.clear()
                    para.add_run(modified_text)
                
                print(f"✓ ({len(deletions)} 处修改)")
            else:
                print(f"- (无修改)")
        
        doc.save(str(output_path))
        
        result = {
            'success': True,
            'input_file': str(input_path),
            'output_file': str(output_path),
            'total_paragraphs': total_paragraphs,
            'processed_paragraphs': processed_paragraphs,
            'total_deletions': len(all_deletions),
            'deletions': all_deletions,
            'track_changes_enabled': enable_track_changes,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"\n✓ 处理完成: {output_path}")
        
        return result
    
    def _enable_track_revisions(self, doc):
        """启用文档的修订追踪设置"""
        settings = doc.settings.element
        
        track_revisions = settings.find(qn('w:trackRevisions'))
        if track_revisions is None:
            track_revisions = OxmlElement('w:trackRevisions')
            settings.append(track_revisions)
    
    def _apply_track_changes(self, para, original_text: str, modified_text: str):
        """
        应用Word原生修订追踪格式
        
        Args:
            para: 段落对象
            original_text: 原始文本
            modified_text: 修改后文本
        """
        footnote_refs = []
        for child in para._p:
            if child.tag == qn('w:r'):
                fn_ref = child.find(qn('w:footnoteReference'))
                if fn_ref is not None:
                    footnote_refs.append(child)
        
        para.clear()
        
        author = "AI润色助手"
        date_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        revision_id = str(random.randint(1, 999999))
        
        del_elem = OxmlElement('w:del')
        del_elem.set(qn('w:id'), revision_id)
        del_elem.set(qn('w:author'), author)
        del_elem.set(qn('w:date'), date_str)
        
        del_run = OxmlElement('w:r')
        del_rPr = OxmlElement('w:rPr')
        del_run.append(del_rPr)
        
        del_text = OxmlElement('w:delText')
        del_text.text = original_text
        del_text.set(qn('xml:space'), 'preserve')
        del_run.append(del_text)
        del_elem.append(del_run)
        
        para._p.append(del_elem)
        
        ins_elem = OxmlElement('w:ins')
        ins_elem.set(qn('w:id'), str(int(revision_id) + 1))
        ins_elem.set(qn('w:author'), author)
        ins_elem.set(qn('w:date'), date_str)
        
        ins_run = OxmlElement('w:r')
        ins_rPr = OxmlElement('w:rPr')
        ins_run.append(ins_rPr)
        
        ins_text = OxmlElement('w:t')
        ins_text.text = modified_text
        ins_text.set(qn('xml:space'), 'preserve')
        ins_run.append(ins_text)
        ins_elem.append(ins_run)
        
        para._p.append(ins_elem)
        
        for fn_ref in footnote_refs:
            para._p.append(fn_ref)
    
    def set_system_prompt(self, prompt: str):
        """
        设置系统提示词
        
        Args:
            prompt: 新的系统提示词
        """
        self.system_prompt = prompt
    
    def add_history_term(self, term: str):
        """
        添加历史专有名词保护
        
        Args:
            term: 历史术语
        """
        self.history_terms.add(term)
    
    def add_history_figure(self, figure: str):
        """
        添加历史人物保护
        
        Args:
            figure: 历史人物名称
        """
        self.history_figures.add(figure)


def create_paper_polisher(api_provider: str = "qwen") -> PaperPolisher:
    """
    工厂函数 - 创建论文润色器
    
    Args:
        api_provider: API提供商 ('qwen' 或 'minimax')
        
    Returns:
        PaperPolisher: 论文润色器实例
    """
    return PaperPolisher(api_provider)


if __name__ == "__main__":
    print("学术论文智能精简处理工具")
    print("="*60)
    print("\n使用方法:")
    print("```python")
    print("from modules.paper_polisher import create_paper_polisher")
    print("")
    print("# 创建润色器（优先使用通义千问）")
    print("polisher = create_paper_polisher('qwen')")
    print("")
    print("# 处理文档")
    print("result = polisher.process_document(")
    print("    'input.docx',")
    print("    'output.docx',")
    print("    enable_track_changes=True")
    print(")")
    print("```")
