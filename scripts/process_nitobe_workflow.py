#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新渡户论文档处理工作流程执行脚本
依据: WORKFLOW_DIAGRAM.md 第二部分文档处理流程规范

处理流程:
1. 输入Word文档
2. DocProcessor解析文档
3. 提取标题、段落、表格、元数据
4. 拼接文本内容
5. LLMClient学术润色
6. 生成新文档
7. 输出.docx文件
"""

import sys
import os
import json
import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent / 'modules'))

from doc_processor import DocProcessor
from llm_client import LLMClient

class DocumentProcessingWorkflow:
    """文档处理工作流程执行器"""

    def __init__(self):
        """初始化工作流程"""
        self.start_time = datetime.datetime.now()
        self.processing_log = {
            'workflow_name': '新渡户论文档处理流程',
            'start_time': self.start_time.isoformat(),
            'steps': [],
            'document_info': {},
            'processing_results': {},
            'errors': [],
            'warnings': []
        }

        self.api_key = None
        self.llm_client = None
        self.doc_processor = None

    def load_api_key(self):
        """加载API密钥"""
        step_info = {
            'step_name': '加载API密钥',
            'status': 'in_progress',
            'timestamp': datetime.datetime.now().isoformat()
        }

        try:
            api_key_path = Path(__file__).parent / 'config' / 'api_key.txt'
            if api_key_path.exists():
                with open(api_key_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines:
                        if 'qwen' in line.lower():
                            self.api_key = line.split('=')[-1].strip()
                            step_info['details'] = f'成功加载通义千问API密钥 (key: {self.api_key[:10]}...)'
                            step_info['status'] = 'success'
                            break
            else:
                step_info['status'] = 'error'
                step_info['error'] = f'API密钥文件不存在: {api_key_path}'
                self.processing_log['errors'].append(step_info)

        except Exception as e:
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            self.processing_log['errors'].append(step_info)

        self.processing_log['steps'].append(step_info)
        return self.api_key is not None

    def initialize_processors(self):
        """初始化处理器"""
        step_info = {
            'step_name': '初始化处理器',
            'status': 'in_progress',
            'timestamp': datetime.datetime.now().isoformat()
        }

        try:
            self.doc_processor = DocProcessor()
            step_info['doc_processor'] = 'DocProcessor初始化成功'

            if self.api_key:
                llm_config = {
                    'provider': 'dashscope',
                    'api_key': self.api_key,
                    'model': 'qwen-plus'
                }
                self.llm_client = LLMClient(llm_config)
                step_info['llm_client'] = 'LLMClient初始化成功 (provider: dashscope, model: qwen-plus)'
            else:
                step_info['llm_client'] = 'LLMClient未初始化 (无API密钥)'
                self.processing_log['warnings'].append('未提供API密钥，将跳过LLM润色步骤')

            step_info['status'] = 'success'

        except Exception as e:
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            self.processing_log['errors'].append(step_info)

        self.processing_log['steps'].append(step_info)

    def extract_document(self, file_path: str):
        """提取文档内容"""
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
                'has_metadata': bool(doc_info.get('metadata'))
            }

            self.processing_log['document_info'] = doc_info

            text_content = []
            for para in doc_info.get('paragraphs', []):
                if para.get('text', '').strip():
                    text_content.append(para['text'].strip())

            combined_text = '\n\n'.join(text_content)
            step_info['extracted_text_length'] = len(combined_text)
            step_info['text_preview'] = combined_text[:500] + '...' if len(combined_text) > 500 else combined_text

            step_info['status'] = 'success'

        except Exception as e:
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            self.processing_log['errors'].append(step_info)

        self.processing_log['steps'].append(step_info)
        return doc_info if 'doc_info' in locals() else None

    def polish_with_llm(self, text: str, language: str = 'zh'):
        """使用LLM进行学术润色"""
        if not self.llm_client:
            return None, 'skipped'

        step_info = {
            'step_name': 'LLM学术润色',
            'language': language,
            'input_length': len(text),
            'status': 'in_progress',
            'timestamp': datetime.datetime.now().isoformat()
        }

        try:
            result = self.llm_client.academic_polish(text, language)

            if result.get('success'):
                polished_text = result.get('content', text)
                step_info['output_length'] = len(polished_text)
                step_info['llm_response'] = result
                step_info['status'] = 'success'
                step_info['details'] = 'LLM润色成功'

                return polished_text, 'success'
            else:
                step_info['status'] = 'error'
                step_info['error'] = result.get('error', '未知错误')
                return None, 'error'

        except Exception as e:
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            self.processing_log['errors'].append(step_info)
            return None, 'error'

        self.processing_log['steps'].append(step_info)

    def create_output_document(self, content: dict, output_path: str):
        """创建输出文档"""
        step_info = {
            'step_name': '创建输出文档',
            'output_path': output_path,
            'status': 'in_progress',
            'timestamp': datetime.datetime.now().isoformat()
        }

        try:
            success = self.doc_processor.create_document(content, output_path)

            if success:
                step_info['status'] = 'success'
                step_info['details'] = f'文档创建成功: {output_path}'
            else:
                step_info['status'] = 'error'
                step_info['error'] = '文档创建失败'

        except Exception as e:
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            self.processing_log['errors'].append(step_info)

        self.processing_log['steps'].append(step_info)

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
            'warnings_count': len(self.processing_log['warnings'])
        }

        return self.processing_log

    def save_workflow_log(self, output_path: str):
        """保存工作流程日志"""
        try:
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
            return False

    def generate_markdown_log(self) -> str:
        """生成Markdown格式的工作日志"""
        log = self.processing_log

        md = f"""# {log['workflow_name']}

## 基本信息

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

## 详细步骤

"""

        for i, step in enumerate(log['steps'], 1):
            md += f"""### 步骤 {i}: {step['step_name']}

- **状态**: {step['status']}
- **时间戳**: {step['timestamp']}

"""
            if 'details' in step:
                md += f"- **详情**: {step['details']}\n"

            if 'document_structure' in step:
                md += "\n**文档结构**:\n"
                for key, value in step['document_structure'].items():
                    md += f"- {key}: {value}\n"

            if 'extracted_text_length' in step:
                md += f"\n- **提取文本长度**: {step['extracted_text_length']}字符\n"

            if 'error' in step:
                md += f"\n- **错误**: {step['error']}\n"

            md += "\n---\n\n"

        if log['errors']:
            md += "## 错误详情\n\n"
            for error in log['errors']:
                md += f"- **{error['step_name']}**: {error.get('error', '未知错误')}\n"
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
            md += f"- **元数据**: {json.dumps(doc_info.get('metadata', {}), ensure_ascii=False)}\n"

        md += "\n---\n\n*此日志由DocumentProcessingWorkflow自动生成*\n"

        return md


def main():
    """主函数"""
    print("=" * 60)
    print("新渡户论文档处理工作流程")
    print("=" * 60)
    print()

    workflow = DocumentProcessingWorkflow()

    input_file = Path(__file__).parent / "TW《新渡户论》20260324.docx"
    output_file = Path(__file__).parent / "TW《新渡户论》20260324_处理后.docx"
    log_file = Path(__file__).parent / "WORKFLOW_EXECUTION_LOG.json"

    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print(f"日志文件: {log_file}")
    print()

    if not input_file.exists():
        print(f"错误: 输入文件不存在 - {input_file}")
        return 1

    print("步骤1: 加载API密钥...")
    if workflow.load_api_key():
        print("✓ API密钥加载成功")
    else:
        print("✗ API密钥加载失败")
    print()

    print("步骤2: 初始化处理器...")
    workflow.initialize_processors()
    print("✓ 处理器初始化完成")
    print()

    print("步骤3: 提取文档内容...")
    doc_info = workflow.extract_document(str(input_file))
    if doc_info:
        print(f"✓ 文档提取成功")
        print(f"  - 标题: {doc_info.get('title', 'N/A')}")
        print(f"  - 段落数: {len(doc_info.get('paragraphs', []))}")
        print(f"  - 表格数: {len(doc_info.get('tables', []))}")
    else:
        print("✗ 文档提取失败")
    print()

    if workflow.llm_client:
        print("步骤4: LLM学术润色...")
        text_content = []
        for para in doc_info.get('paragraphs', []):
            if para.get('text', '').strip():
                text_content.append(para['text'].strip())
        combined_text = '\n\n'.join(text_content)

        polished_text, status = workflow.polish_with_llm(combined_text[:5000], 'zh')

        if status == 'success':
            print(f"✓ LLM润色成功 (输出长度: {len(polished_text)}字符)")
        else:
            print(f"✗ LLM润色失败或跳过")
    else:
        print("步骤4: 跳过LLM润色 (无API密钥)")
    print()

    print("步骤5: 创建输出文档...")
    workflow.create_output_document(doc_info, str(output_file))
    print(f"✓ 输出文档已创建: {output_file}")
    print()

    print("步骤6: 保存工作日志...")
    workflow.save_workflow_log(str(log_file))
    print(f"✓ 工作日志已保存: {log_file}")
    print()

    summary = workflow.generate_workflow_log()['summary']
    print("=" * 60)
    print("工作流程执行完成")
    print(f"总步骤: {summary['total_steps']}")
    print(f"成功: {summary['successful_steps']}")
    print(f"失败: {summary['failed_steps']}")
    print(f"跳过: {summary['skipped_steps']}")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
