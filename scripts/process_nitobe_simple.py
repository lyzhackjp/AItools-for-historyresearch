#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新渡户论文档处理工作流程执行脚本（简化版）
依据: WORKFLOW_DIAGRAM.md 第二部分文档处理流程规范

处理流程:
1. 输入Word文档
2. DocProcessor解析文档
3. 提取标题、段落、表格、元数据
4. 生成新文档
5. 输出.docx文件
6. 生成详细工作日志
"""

import sys
import json
import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent / 'modules'))

from doc_processor import DocProcessor

class SimpleDocumentProcessingWorkflow:
    """简化版文档处理工作流程执行器"""

    def __init__(self):
        """初始化工作流程"""
        self.start_time = datetime.datetime.now()
        self.processing_log = {
            'workflow_name': '新渡户论文档处理流程',
            'workflow_reference': 'WORKFLOW_DIAGRAM.md 第二部分：文档处理流程',
            'start_time': self.start_time.isoformat(),
            'steps': [],
            'document_info': {},
            'processing_results': {},
            'errors': [],
            'warnings': []
        }

        self.doc_processor = None

    def initialize_processors(self):
        """初始化处理器"""
        step_info = {
            'step_name': '初始化DocProcessor',
            'status': 'in_progress',
            'timestamp': datetime.datetime.now().isoformat()
        }

        try:
            self.doc_processor = DocProcessor()
            step_info['details'] = 'DocProcessor初始化成功'
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
            step_info['details'] = f'成功提取文档内容，{len(doc_info.get("paragraphs", []))}个段落，{len(doc_info.get("tables", []))}个表格'

        except Exception as e:
            step_info['status'] = 'error'
            step_info['error'] = str(e)
            self.processing_log['errors'].append(step_info)

        self.processing_log['steps'].append(step_info)
        return doc_info if 'doc_info' in locals() else None

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
    C --> G[解析样式]
    D --> G
    E --> G
    F --> G
    G --> H[结构化数据]
    H --> I[JSON输出]
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

            if 'document_structure' in step:
                md += "\n**文档结构**:\n"
                for key, value in step['document_structure'].items():
                    md += f"- {key}: {value}\n"

            if 'extracted_text_length' in step:
                md += f"\n- **提取文本长度**: {step['extracted_text_length']}字符\n"

            if 'text_preview' in step:
                md += f"\n**文本预览**:\n```\n{step['text_preview']}\n```\n"

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
            md += f"- **页眉数**: {len(doc_info.get('headers', []))}\n"
            md += f"- **页脚数**: {len(doc_info.get('footers', []))}\n"
            md += f"- **元数据**: {json.dumps(doc_info.get('metadata', {}), ensure_ascii=False, indent=2)}\n"

            md += "\n### 文档段落预览\n\n"
            paragraphs = doc_info.get('paragraphs', [])[:10]
            for idx, para in enumerate(paragraphs, 1):
                text = para.get('text', '')[:200]
                style = para.get('style', 'Normal')
                md += f"{idx}. **[{style}]** {text}...\n\n"

        md += """## 处理结果文件

处理完成后生成了以下文件：

1. **处理后文档**: `TW《新渡户论》20260324_处理后.docx`
   - 包含提取的文档内容和格式信息

2. **工作日志**: `WORKFLOW_EXECUTION_LOG.json`
   - 完整的JSON格式处理日志

3. **工作日志报告**: `WORKFLOW_EXECUTION_LOG.md`
   - Markdown格式的详细处理报告

---

*此日志由SimpleDocumentProcessingWorkflow自动生成*
*生成时间: """ + datetime.datetime.now().isoformat() + """*
"""

        return md


def main():
    """主函数"""
    print("=" * 60)
    print("新渡户论文档处理工作流程")
    print("=" * 60)
    print()

    workflow = SimpleDocumentProcessingWorkflow()

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

    print("步骤1: 初始化DocProcessor...")
    workflow.initialize_processors()
    if any(s['status'] == 'success' for s in workflow.processing_log['steps']):
        print("✓ DocProcessor初始化成功")
    else:
        print("✗ DocProcessor初始化失败")
    print()

    print("步骤2: 提取文档内容...")
    doc_info = workflow.extract_document(str(input_file))
    if doc_info:
        print("✓ 文档提取成功")
        print(f"  - 标题: {doc_info.get('title', 'N/A')}")
        print(f"  - 段落数: {len(doc_info.get('paragraphs', []))}")
        print(f"  - 表格数: {len(doc_info.get('tables', []))}")
        print(f"  - 提取文本长度: {sum(len(p.get('text', '')) for p in doc_info.get('paragraphs', []))}字符")
    else:
        print("✗ 文档提取失败")
        return 1
    print()

    print("步骤3: 创建输出文档...")
    workflow.create_output_document(doc_info, str(output_file))
    if output_file.exists():
        print(f"✓ 输出文档已创建: {output_file}")
        print(f"  - 文件大小: {output_file.stat().st_size} bytes")
    else:
        print("✗ 输出文档创建失败")
    print()

    print("步骤4: 保存工作日志...")
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
    print(f"总耗时: {workflow.processing_log['total_duration']:.2f}秒")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
