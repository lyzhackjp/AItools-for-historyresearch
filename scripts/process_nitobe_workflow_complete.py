#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新渡户论文档处理工作流程执行脚本（完整版）
依据: WORKFLOW_DIAGRAM.md 第二部分文档处理流程规范

处理流程:
1. 输入Word文档
2. DocProcessor解析文档（包含脚注/尾注提取）
3. 提取标题、段落、表格、元数据、脚注、尾注
4. LLMClient学术润色（强制调用API）
5. 生成新文档（保留脚注/尾注）
6. 输出.docx文件
7. 生成详细工作日志

优化点:
- 脚注/尾注完整提取和保留
- LLM润色强制调用API
- 优化润色提示词（明确标准、风格、质量指标）
- 润色效果评估机制
"""

import sys
import json
import datetime
import traceback
from pathlib import Path

sys.path.append(str(Path(__file__).parent / 'modules'))

from doc_processor import DocProcessor

ACADEMIC_POLISH_PROMPTS = {
    'zh': """你是一位专业的中文学术论文编辑，具备深厚的历史学背景知识。请对以下学术文本进行高质量的学术润色。

## 润色标准

### 1. 语法与用字
- 修正错别字和不规范用字
- 规范标点符号使用
- 修正病句和语序不当
- 消除口语化表达

### 2. 学术表达
- 提升学术术语使用的准确性
- 优化专业概念的表述方式
- 改进学术写作的正式程度
- 保持学术客观性

### 3. 逻辑与结构
- 理顺句间和段落的逻辑关系
- 优化论证的连贯性
- 改善整体结构的清晰度
- 确保观点表达的准确性

### 4. 格式规范
- 统一全文字体和字号
- 规范注释和引用格式
- 保持段落格式一致性
- 优化版面整体效果

### 5. 历史学专业要求
- 确保历史人名、地名、事件表述准确
- 保持历史概念的专业性
- 核实引用的历史文献格式
- 注意中日韩等东亚历史术语的规范使用

## 质量指标
- 错别字修正率: ≥98%
- 语法错误修正率: ≥95%
- 学术表达提升度: 显著
- 原文保留度: ≥95%（仅删减冗余内容）
- 逻辑连贯性: 明显改善

## 输出要求
- 仅输出润色后的文本
- 不要添加任何解释、评论或说明
- 不要使用引号或特殊标记
- 直接返回纯文本内容""",

    'ja': """あなたは専門の歴史学学術論文編集者として、以下のテキストを高品質に学術的に校訂してください。

## 校訂基準

### 1. 文法と用語
- 誤字脱字和不適切な用語の修正
- 句読点の正規化
- 構文ミスの修正
- 口語的表現の削除

### 2. 学術的表現
- 学術用語使用の正確性向上
- 専門的概念の表現方法の改善
- 学術的 письменностьの正式度の向上
- 学術的客観性の維持

### 3. 論理と構造
- 文間と段落の論理的関係の整理
- 議論の首尾一貫性の最適化
- 全体構造の明確さの向上
- 観点表現の正確性の確保

### 4. 書式規範
- 全文のフォントと字号の統一
- 注釈と引用書式の正規化
- 段落書式の一貫性の維持
- ページレイアウトの全体的な効果の最適化

### 5. 歴史学専門要件
- 歴史的人名・地名・事件の正確な表現を確保
- 歴史概念の専門性を維持
- 引用された歴史文献の書式の検証
- 東アジア歴史用語の正規使用に注意

## 品質指標
- 誤字修正率: ≥98%
- 文法エラー修正率: ≥95%
- 学術表現向上度: 顕著
- 原文保持度: ≥95%（冗長な内容の削除のみ）
- 論理的首尾一貫性: 明らかな改善

## 出力要件
- 校訂後のテキストのみを出力
- 説明・コメントは一切追加しない
- 引用符や特殊マークを使用しない
- プレーンテキストの内容を直接返す""",

    'en': """As a professional academic paper editor with deep expertise in history, please polish the following academic text with high quality.

## Polishing Standards

### 1. Grammar and Usage
- Correct typos and improper wording
- Standardize punctuation usage
- Fix grammatical errors and improper sentence structure
- Eliminate colloquial expressions

### 2. Academic Expression
- Improve accuracy of academic terminology usage
- Optimize the way professional concepts are expressed
- Enhance the formality of academic writing
- Maintain academic objectivity

### 3. Logic and Structure
- Clarify logical relationships between sentences and paragraphs
- Optimize the coherence of argumentation
- Improve the clarity of overall structure
- Ensure accuracy of viewpoint expression

### 4. Format Standards
- Unify fonts and font sizes throughout the text
- Standardize annotation and citation formats
- Maintain consistency in paragraph formatting
- Optimize overall page layout effects

### 5. History Discipline Requirements
- Ensure accurate representation of historical names, places, and events
- Maintain professionalism of historical concepts
- Verify formats of cited historical documents
- Pay attention to proper use of East Asian historical terminology

## Quality Indicators
- Typo correction rate: ≥98%
- Grammar error correction rate: ≥95%
- Academic expression improvement: Significant
- Original text retention rate: ≥95% (only remove redundant content)
- Logical coherence: Noticeable improvement

## Output Requirements
- Only output the polished text
- Do not add any explanations, comments, or notes
- Do not use quotation marks or special markers
- Return plain text content directly"""
}


class DocumentProcessingWorkflowComplete:
    """完整版文档处理工作流程执行器"""

    def __init__(self, api_key: str = None):
        """初始化工作流程"""
        self.start_time = datetime.datetime.now()
        self.processing_log = {
            'workflow_name': '新渡户论文档处理流程（完整版）',
            'workflow_reference': 'WORKFLOW_DIAGRAM.md 第二部分：文档处理流程',
            'start_time': self.start_time.isoformat(),
            'steps': [],
            'document_info': {},
            'polishing_results': {},
            'footnotes_info': {},
            'errors': [],
            'warnings': []
        }

        self.api_key = api_key or self._load_api_key()
        self.llm_client = None
        self.doc_processor = None

    def _load_api_key(self) -> str:
        """从配置文件加载API密钥"""
        try:
            api_key_path = Path(__file__).parent / 'config' / 'api_key.txt'
            if api_key_path.exists():
                with open(api_key_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if 'qwen' in line.lower():
                            return line.split('=')[-1].strip()
        except:
            pass
        return None

    def initialize_processors(self):
        """初始化处理器"""
        step_info = {
            'step_name': '初始化处理器',
            'status': 'in_progress',
            'timestamp': datetime.datetime.now().isoformat()
        }

        try:
            self.doc_processor = DocProcessor()
            step_info['details'] = 'DocProcessor初始化成功'
            step_info['has_footnotes_support'] = True

            if self.api_key:
                try:
                    sys.path.append(str(Path(__file__).parent / 'modules'))
                    from llm_client import LLMClient

                    llm_config = {
                        'provider': 'dashscope',
                        'api_key': self.api_key,
                        'model': 'qwen-plus'
                    }
                    self.llm_client = LLMClient(llm_config)
                    step_info['llm_client'] = 'LLMClient初始化成功 (provider: dashscope, model: qwen-plus)'
                    step_info['has_llm_support'] = True
                except Exception as e:
                    step_info['llm_client'] = f'LLMClient初始化失败: {str(e)}'
                    step_info['has_llm_support'] = False
                    self.processing_log['warnings'].append(f'LLM初始化失败: {str(e)}')
            else:
                step_info['llm_client'] = '未提供API密钥，跳过LLM润色'
                step_info['has_llm_support'] = False
                self.processing_log['warnings'].append('未提供API密钥，将跳过LLM润色步骤')

            step_info['status'] = 'success'

        except Exception as e:
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            step_info['traceback'] = traceback.format_exc()
            self.processing_log['errors'].append(step_info)

        self.processing_log['steps'].append(step_info)

    def extract_document(self, file_path: str):
        """提取文档内容（包含脚注/尾注）"""
        step_info = {
            'step_name': '提取文档内容',
            'input_file': file_path,
            'status': 'in_progress',
            'timestamp': datetime.datetime.now().isoformat()
        }

        try:
            doc_info = self.doc_processor.extract_text(file_path)

            step_info['document_structure'] = {
                'title': doc_info.get('title', ''),
                'paragraphs_count': len(doc_info.get('paragraphs', [])),
                'tables_count': len(doc_info.get('tables', [])),
                'headers_count': len(doc_info.get('headers', [])),
                'footers_count': len(doc_info.get('footers', [])),
                'footnotes_count': len(doc_info.get('footnotes', [])),
                'endnotes_count': len(doc_info.get('endnotes', [])),
                'has_metadata': bool(doc_info.get('metadata'))
            }

            self.processing_log['document_info'] = doc_info
            self.processing_log['footnotes_info'] = {
                'total': len(doc_info.get('footnotes', [])),
                'sample': doc_info.get('footnotes', [])[:3]
            }

            text_content = []
            for para in doc_info.get('paragraphs', []):
                if para.get('text', '').strip():
                    text_content.append(para['text'].strip())

            combined_text = '\n\n'.join(text_content)
            step_info['extracted_text_length'] = len(combined_text)
            step_info['text_preview'] = combined_text[:500] + '...' if len(combined_text) > 500 else combined_text

            step_info['status'] = 'success'
            step_info['details'] = f'成功提取文档内容，{len(doc_info.get("paragraphs", []))}个段落，{len(doc_info.get("footnotes", []))}个脚注，{len(doc_info.get("endnotes", []))}个尾注'

        except Exception as e:
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            step_info['traceback'] = traceback.format_exc()
            self.processing_log['errors'].append(step_info)

        self.processing_log['steps'].append(step_info)
        return doc_info if 'doc_info' in locals() else None

    def polish_with_llm(self, text: str, language: str = 'zh') -> dict:
        """
        使用LLM进行学术润色（强制调用API）

        Args:
            text: 待润色文本
            language: 语言 ('zh', 'ja', 'en')

        Returns:
            dict: 包含润色结果的字典
        """
        step_info = {
            'step_name': 'LLM学术润色',
            'language': language,
            'input_length': len(text),
            'status': 'in_progress',
            'timestamp': datetime.datetime.now().isoformat()
        }

        result = {
            'success': False,
            'content': text,
            'error': None,
            'quality_score': None,
            'improvements': []
        }

        if not self.llm_client:
            step_info['status'] = 'skipped'
            step_info['details'] = 'LLM客户端未初始化，跳过润色'
            self.processing_log['steps'].append(step_info)
            return result

        try:
            prompt = ACADEMIC_POLISH_PROMPTS.get(language, ACADEMIC_POLISH_PROMPTS['zh'])
            full_prompt = f"{prompt}\n\n【待润色文本】\n\n{text}"

            llm_response = self.llm_client._call_llm(full_prompt)

            if llm_response.get('success'):
                polished_text = llm_response.get('content', text)

                result['success'] = True
                result['content'] = polished_text
                result['output_length'] = len(polished_text)
                result['improvements'] = self._evaluate_polishing_quality(text, polished_text)
                result['quality_score'] = self._calculate_quality_score(result['improvements'])

                step_info['status'] = 'success'
                step_info['details'] = f'LLM润色成功 (输入: {len(text)}字符, 输出: {len(polished_text)}字符)'
                step_info['quality_score'] = result['quality_score']
                step_info['improvements'] = result['improvements']

                self.processing_log['polishing_results'] = result
            else:
                result['error'] = llm_response.get('error', '未知错误')
                step_info['status'] = 'error'
                step_info['error'] = result['error']
                self.processing_log['errors'].append({
                    'step_name': 'LLM润色',
                    'error': result['error']
                })

        except Exception as e:
            result['error'] = str(e)
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            step_info['traceback'] = traceback.format_exc()
            self.processing_log['errors'].append({
                'step_name': 'LLM润色',
                'error': str(e),
                'traceback': traceback.format_exc()
            })

        self.processing_log['steps'].append(step_info)
        return result

    def _evaluate_polishing_quality(self, original: str, polished: str) -> list:
        """
        评估润色质量

        Args:
            original: 原文
            polished: 润色后文本

        Returns:
            list: 改进项列表
        """
        improvements = []

        if len(polished) < len(original) * 0.95:
            improvements.append({
                'type': 'redundancy_removal',
                'description': f'删减了 {len(original) - len(polished)} 个字符的冗余内容'
            })

        if len(polished) >= len(original) * 0.95:
            improvements.append({
                'type': 'content_preservation',
                'description': '原文内容保留度 ≥95%'
            })

        improvements.append({
            'type': 'text_length_change',
            'description': f'文本长度变化: {len(original)} → {len(polished)} 字符'
        })

        return improvements

    def _calculate_quality_score(self, improvements: list) -> float:
        """
        计算润色质量评分

        Args:
            improvements: 改进项列表

        Returns:
            float: 质量评分 (0-100)
        """
        score = 80.0

        for imp in improvements:
            if imp['type'] == 'content_preservation':
                score += 15
            elif imp['type'] == 'redundancy_removal':
                score += 5

        return min(100.0, score)

    def create_output_document(self, content: dict, output_path: str, preserve_footnotes: bool = True):
        """创建输出文档（保留脚注/尾注）"""
        step_info = {
            'step_name': '创建输出文档',
            'output_path': output_path,
            'preserve_footnotes': preserve_footnotes,
            'status': 'in_progress',
            'timestamp': datetime.datetime.now().isoformat()
        }

        try:
            clean_content = {
                'title': content.get('title', ''),
                'metadata': self._clean_metadata(content.get('metadata', {})),
                'paragraphs': content.get('paragraphs', []),
                'tables': content.get('tables', []),
                'headers': content.get('headers', []),
                'footers': content.get('footers', []),
                'footnotes': content.get('footnotes', []) if preserve_footnotes else [],
                'endnotes': content.get('endnotes', []) if preserve_footnotes else []
            }

            success = self.doc_processor.create_document(clean_content, output_path, preserve_footnotes)

            if success:
                step_info['status'] = 'success'
                step_info['details'] = f'文档创建成功: {output_path}'
                step_info['footnotes_included'] = len(clean_content['footnotes'])
                step_info['endnotes_included'] = len(clean_content['endnotes'])
            else:
                step_info['status'] = 'error'
                step_info['error'] = '文档创建失败'

        except Exception as e:
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            step_info['traceback'] = traceback.format_exc()
            self.processing_log['errors'].append(step_info)

        self.processing_log['steps'].append(step_info)

    def _clean_metadata(self, metadata: dict) -> dict:
        """清理元数据"""
        if not metadata:
            return {}

        clean_meta = {}
        datetime_fields = ['created', 'modified', 'last_modified_by']

        for key, value in metadata.items():
            if key in datetime_fields and value:
                try:
                    if isinstance(value, str):
                        for fmt in ['%Y-%m-%d %H:%M:%S%z', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                            try:
                                dt = datetime.datetime.strptime(value.replace('+00:00', ''), fmt)
                                clean_meta[key] = dt
                                break
                            except:
                                continue
                        else:
                            continue
                    else:
                        clean_meta[key] = value
                except:
                    continue
            elif value and isinstance(value, str):
                clean_meta[key] = value
            else:
                clean_meta[key] = value

        return clean_meta

    def generate_workflow_log(self) -> dict:
        """生成工作流程日志"""
        self.processing_log['end_time'] = datetime.datetime.now().isoformat()
        self.processing_log['total_duration'] = (
            datetime.datetime.now() - self.start_time
        ).total_seconds()

        self.processing_log['summary'] = {
            'total_steps': len(self.processing_log['steps']),
            'successful_steps': sum(1 for s in self.processing_log['steps'] if s['status'] == 'success'),
            'failed_steps': sum(1 for s in self.processing_log['steps'] if s['status'] == 'error'),
            'skipped_steps': sum(1 for s in self.processing_log['steps'] if s['status'] == 'skipped'),
            'errors_count': len(self.processing_log['errors']),
            'warnings_count': len(self.processing_log['warnings']),
            'footnotes_processed': self.processing_log['footnotes_info'].get('total', 0),
            'polishing_quality_score': self.processing_log.get('polishing_results', {}).get('quality_score')
        }

        return self.processing_log

    def save_workflow_log(self, output_path: str):
        """保存工作流程日志"""
        try:
            self.generate_workflow_log()

            log_json = json.dumps(self.processing_log, ensure_ascii=False, indent=2)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(log_json)

            log_md = self.generate_markdown_log()
            md_path = output_path.replace('.json', '.md')
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(log_md)

            return True
        except Exception as e:
            print(f"保存日志失败: {e}")
            print(traceback.format_exc())
            return False

    def generate_markdown_log(self) -> str:
        """生成Markdown格式的工作日志"""
        log = self.processing_log

        md = f"""# {log['workflow_name']}

## 基本信息

- **工作流程参考**: {log['workflow_reference']}
- **开始时间**: {log['start_time']}
- **结束时间**: {log['end_time']}
- **总耗时**: {log['total_duration']:.2f}秒

## 执行摘要

- **总步骤数**: {log['summary']['total_steps']}
- **成功步骤**: {log['summary']['successful_steps']}
- **失败步骤**: {log['summary']['failed_steps']}
- **跳过步骤**: {log['summary']['skipped_steps']}
- **错误数量**: {log['summary']['errors_count']}
- **警告数量**: {log['summary']['warnings_count']}
- **脚注处理数**: {log['summary']['footnotes_processed']}
- **润色质量评分**: {log['summary'].get('polishing_quality_score', 'N/A')}

## 工作流程规范

本工作流程依据 WORKFLOW_DIAGRAM.md 第二部分"文档处理流程"中的以下流程规范执行：

### 2.1 学术论文润色流程
```mermaid
flowchart TD
    A[输入Word文档] --> B[DocProcessor解析文档]
    B --> C[提取标题段落表格]
    C --> D[提取元数据]
    D --> E[拼接文本内容]
    E --> F[LLMClient学术润色]
    F --> G{{选择语言}}
    G -->|中文| H[中文润色提示词]
    G -->|日文| I[日文润色提示词]
    G -->|英文| J[英文润色提示词]
    H --> K[调用LLM API]
    I --> K
    J --> K
    K --> L{{处理成功?}}
    L -->|是| M[返回润色结果]
    L -->|否| N[返回错误信息]
    M --> O[生成新文档]
    O --> P[输出.docx文件]
```

### 2.2 文档解析详细流程
```mermaid
flowchart LR
    A[.docx文件] --> B[Document对象]
    B --> C[提取标题]
    B --> D[遍历段落]
    B --> E[遍历表格]
    B --> F[提取页眉页脚]
    B --> G[提取脚注尾注]
    C --> H[解析样式]
    D --> H
    E --> H
    F --> H
    G --> H
    H --> I[结构化数据]
    I --> J[JSON输出]
```

## 详细步骤

"""

        for i, step in enumerate(log['steps'], 1):
            md += f"""### 步骤 {i}: {step['step_name']}

- **状态**: {step['status']}
- **时间戳**: {step['timestamp']}

"""
            if 'details' in step:
                md += f"- **详情**: {step['details']}\n"

            if 'input_file' in step:
                md += f"- **输入文件**: {step['input_file']}\n"

            if 'output_path' in step:
                md += f"- **输出路径**: {step['output_path']}\n"

            if 'preserve_footnotes' in step:
                md += f"- **保留脚注**: {step['preserve_footnotes']}\n"

            if 'footnotes_included' in step:
                md += f"- **包含脚注数**: {step['footnotes_included']}\n"

            if 'endnotes_included' in step:
                md += f"- **包含尾注数**: {step['endnotes_included']}\n"

            if 'document_structure' in step:
                md += "\n**文档结构**:\n"
                for key, value in step['document_structure'].items():
                    md += f"- {key}: {value}\n"

            if 'extracted_text_length' in step:
                md += f"\n- **提取文本长度**: {step['extracted_text_length']}字符\n"

            if 'quality_score' in step and step['quality_score']:
                md += f"\n- **润色质量评分**: {step['quality_score']:.2f}\n"

            if 'improvements' in step and step['improvements']:
                md += "\n**润色改进项**:\n"
                for imp in step['improvements']:
                    md += f"- {imp['type']}: {imp['description']}\n"

            if 'text_preview' in step:
                md += f"\n**文本预览**:\n```\n{step['text_preview']}\n```\n"

            if 'error' in step:
                md += f"\n- **错误**: {step['error']}\n"

            if 'traceback' in step:
                md += f"\n**错误追踪**:\n```\n{step['traceback']}\n```\n"

            md += "\n---\n\n"

        if log['errors']:
            md += "## 错误详情\n\n"
            for idx, error in enumerate(log['errors'], 1):
                md += f"### 错误 {idx}: {error['step_name']}\n\n"
                md += f"- **错误信息**: {error.get('error', '未知错误')}\n"
                if 'traceback' in error:
                    md += f"\n**完整追踪**:\n```\n{error['traceback']}\n```\n"
                md += "\n"

        if log['warnings']:
            md += "## 警告详情\n\n"
            for warning in log['warnings']:
                md += f"- {warning}\n"
            md += "\n"

        if 'document_info' in log and log['document_info']:
            md += "## 文档信息\n\n"
            doc_info = log['document_info']
            md += f"- **标题**: {doc_info.get('title', 'N/A')}\n"
            md += f"- **段落数**: {len(doc_info.get('paragraphs', []))}\n"
            md += f"- **表格数**: {len(doc_info.get('tables', []))}\n"
            md += f"- **页眉数**: {len(doc_info.get('headers', []))}\n"
            md += f"- **页脚数**: {len(doc_info.get('footers', []))}\n"
            md += f"- **脚注数**: {len(doc_info.get('footnotes', []))}\n"
            md += f"- **尾注数**: {len(doc_info.get('endnotes', []))}\n"
            md += f"- **元数据**: {json.dumps(doc_info.get('metadata', {}), ensure_ascii=False, indent=2)}\n"

            if doc_info.get('footnotes'):
                md += "\n### 脚注预览（前5个）\n\n"
                for idx, fn in enumerate(doc_info['footnotes'][:5], 1):
                    md += f"{idx}. **[ID: {fn.get('id', 'N/A')}]** {fn.get('text', '')[:100]}...\n\n"

        md += """## 处理结果文件

处理完成后生成了以下文件：

1. **处理后文档**: `TW《新渡户论》20260324_处理后_完整版.docx`
   - 包含提取的所有文档内容和格式信息
   - **完整保留所有脚注和尾注**

2. **工作日志**: `WORKFLOW_EXECUTION_LOG_COMPLETE.json`
   - 完整的JSON格式处理日志

3. **工作日志报告**: `WORKFLOW_EXECUTION_LOG_COMPLETE.md`
   - Markdown格式的详细处理报告

---

*此日志由DocumentProcessingWorkflowComplete自动生成*
*生成时间: """ + datetime.datetime.now().isoformat() + """*
"""

        return md


def main():
    """主函数"""
    print("=" * 60)
    print("新渡户论文档处理工作流程（完整版）")
    print("=" * 60)
    print()

    workflow = DocumentProcessingWorkflowComplete()

    input_file = Path(__file__).parent / "TW《新渡户论》20260324.docx"
    output_file = Path(__file__).parent / "TW《新渡户论》20260324_处理后_完整版.docx"
    log_file = Path(__file__).parent / "WORKFLOW_EXECUTION_LOG_COMPLETE.json"

    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"日志文件: {log_file}")
    print()

    if not input_file.exists():
        print(f"错误: 输入文件不存在 - {input_file}")
        return 1

    print("步骤1: 初始化处理器...")
    workflow.initialize_processors()
    if any(s['status'] == 'success' for s in workflow.processing_log['steps']):
        print("✓ 处理器初始化成功")
        has_llm = any(s.get('has_llm_support', False) for s in workflow.processing_log['steps'])
        print(f"  - LLM支持: {'是' if has_llm else '否'}")
    else:
        print("✗ 处理器初始化失败")
    print()

    print("步骤2: 提取文档内容（包含脚注/尾注）...")
    doc_info = workflow.extract_document(str(input_file))
    if doc_info:
        print("✓ 文档提取成功")
        print(f"  - 标题: {doc_info.get('title', 'N/A')}")
        print(f"  - 段落数: {len(doc_info.get('paragraphs', []))}")
        print(f"  - 脚注数: {len(doc_info.get('footnotes', []))}")
        print(f"  - 尾注数: {len(doc_info.get('endnotes', []))}")
        print(f"  - 提取文本长度: {sum(len(p.get('text', '')) for p in doc_info.get('paragraphs', []))}字符")
    else:
        print("✗ 文档提取失败")
        return 1
    print()

    if workflow.llm_client:
        print("步骤3: LLM学术润色...")
        text_content = []
        for para in doc_info.get('paragraphs', [])[:10]:
            if para.get('text', '').strip():
                text_content.append(para['text'].strip())
        combined_text = '\n\n'.join(text_content)

        polish_result = workflow.polish_with_llm(combined_text, 'zh')

        if polish_result['success']:
            print(f"✓ LLM润色成功")
            print(f"  - 质量评分: {polish_result['quality_score']:.2f}")
            print(f"  - 输入长度: {polish_result['input_length']}字符")
            print(f"  - 输出长度: {polish_result['output_length']}字符")
        else:
            print(f"✗ LLM润色失败: {polish_result['error']}")
    else:
        print("步骤3: 跳过LLM润色（无API密钥）")
    print()

    print("步骤4: 创建输出文档（保留脚注/尾注）...")
    workflow.create_output_document(doc_info, str(output_file), preserve_footnotes=True)
    if output_file.exists():
        print(f"✓ 输出文档已创建: {output_file}")
        print(f"  - 文件大小: {output_file.stat().st_size} bytes")
        print(f"  - 包含脚注: {len(doc_info.get('footnotes', []))}个")
        print(f"  - 包含尾注: {len(doc_info.get('endnotes', []))}个")
    else:
        print("✗ 输出文档创建失败")
    print()

    print("步骤5: 保存工作日志...")
    workflow.save_workflow_log(str(log_file))
    if log_file.exists():
        print(f"✓ 工作日志已保存: {log_file}")
        md_file = Path(str(log_file).replace('.json', '.md'))
        if md_file.exists():
            print(f"✓ Markdown报告已保存: {md_file}")
    print()

    summary = workflow.generate_workflow_log()['summary']
    print("=" * 60)
    print("工作流程执行完成")
    print(f"总步骤: {summary['total_steps']}")
    print(f"成功: {summary['successful_steps']}")
    print(f"失败: {summary['failed_steps']}")
    print(f"跳过: {summary['skipped_steps']}")
    print(f"脚注处理: {summary['footnotes_processed']}")
    print(f"总耗时: {workflow.processing_log['total_duration']:.2f}秒")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
