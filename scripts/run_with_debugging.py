#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学术论文润色增强工作流程 - 调试版本

此脚本负责加载配置并执行增强版论文润色工作流程
包含详细的调试信息和错误处理
"""

import sys
import os
import json
import traceback
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'modules'))

def load_api_key_from_config():
    """从配置文件加载API密钥"""
    config_file = project_root / 'config' / 'api_key.txt'
    
    if not config_file.exists():
        print(f"警告: 配置文件不存在: {config_file}")
        return None
    
    api_keys = {}
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    key_name, key_value = line.split('=', 1)
                    api_keys[key_name.strip()] = key_value.strip()
    except Exception as e:
        print(f"读取API密钥文件失败: {e}")
        return None
    
    if 'qwen3.5-plus' in api_keys:
        return api_keys['qwen3.5-plus']
    elif 'Minimax2.7' in api_keys:
        return api_keys['Minimax2.7']
    else:
        return None

def set_api_key_env():
    """设置API密钥环境变量"""
    api_key = load_api_key_from_config()
    
    if api_key:
        os.environ['DASHSCOPE_API_KEY'] = api_key
        print(f"✓ API密钥已加载 (长度: {len(api_key)}字符)")
        return True
    else:
        print("✗ 无法加载API密钥")
        return False

def main():
    """主函数"""
    print("=" * 70)
    print("学术论文智能润色增强工作流程 v2.0 (调试版)")
    print("=" * 70)
    
    if not set_api_key_env():
        print("\n错误: 无法加载API密钥，请检查配置文件")
        return
    
    from modules.doc_processor import DocProcessor
    from enhanced_paper_polishing_workflow import (
        DocumentSegmenter,
        EnhancedPaperPolishingWorkflow,
        ProcessingStatus
    )
    from modules.llm_client import create_llm_client
    
    input_file = project_root / "TW《新渡户论》20260324.docx"
    output_file = project_root / "TW《新渡户论》20260324_polished.docx"
    
    print(f"\n输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print("-" * 70)
    
    if not input_file.exists():
        print(f"\n错误: 输入文件不存在: {input_file}")
        return
    
    print("\n第1步: 初始化组件...")
    try:
        doc_processor = DocProcessor()
        segmenter = DocumentSegmenter()
        
        print("✓ 组件初始化成功")
    except Exception as e:
        print(f"✗ 组件初始化失败: {e}")
        traceback.print_exc()
        return
    
    print("\n第2步: 提取文档内容...")
    try:
        doc_info = doc_processor.extract_text(str(input_file))
        paragraphs = doc_info.get('paragraphs', [])
        footnotes = doc_info.get('footnotes', [])
        
        print(f"✓ 文档提取成功")
        print(f"   段落数: {len(paragraphs)}")
        print(f"   脚注数: {len(footnotes)}")
    except Exception as e:
        print(f"✗ 文档提取失败: {e}")
        traceback.print_exc()
        return
    
    print("\n第3步: 分段文档...")
    try:
        sections = segmenter.segment_document(paragraphs, footnotes)
        
        print(f"✓ 文档分段成功")
        print(f"   分段数: {len(sections)}")
        
        for idx, section in enumerate(sections):
            print(f"   分段 {idx + 1}: {section.section_type.value} - {section.word_count}字")
    except Exception as e:
        print(f"✗ 文档分段失败: {e}")
        traceback.print_exc()
        return
    
    print("\n第4步: 初始化LLM客户端...")
    try:
        llm_config = {
            'provider': 'dashscope',
            'api_key': os.getenv('DASHSCOPE_API_KEY'),
            'model': 'qwen-plus'
        }
        llm_client = create_llm_client(llm_config)
        print("✓ LLM客户端初始化成功")
    except Exception as e:
        print(f"✗ LLM客户端初始化失败: {e}")
        traceback.print_exc()
        return
    
    print("\n第5步: 处理文档章节...")
    print("-" * 70)
    
    workflow = EnhancedPaperPolishingWorkflow(
        api_provider="dashscope",
        model="qwen-plus"
    )
    workflow.llm_client = llm_client
    workflow.doc_processor = doc_processor
    workflow.segmenter = segmenter
    
    processed_sections = []
    total_quality_score = 0
    quality_threshold = 75.0
    max_retry = 2
    
    for idx, section in enumerate(sections):
        print(f"\n处理分段 {idx + 1}/{len(sections)}...")
        print(f"  类型: {section.section_type.value}")
        print(f"  标题: {section.title[:60]}...")
        print(f"  字数: {section.word_count}")
        
        retry_count = 0
        section_result = None
        
        while retry_count <= max_retry:
            try:
                print(f"\n  调用LLM API (尝试 {retry_count + 1}/{max_retry + 1})...")
                
                from enhanced_paper_polishing_workflow import PolishingQualityChecker
                quality_checker = PolishingQualityChecker(llm_client)
                
                polished_content = workflow._call_polishing_api(section)
                print(f"  ✓ LLM调用成功")
                print(f"  润色后字数: {len(polished_content)}")
                
                quality_result = quality_checker.check_quality(
                    section.content,
                    polished_content,
                    section.section_type
                )
                
                print(f"  质量评分: {quality_result.score:.2f}")
                print(f"  状态: {quality_result.status.value}")
                
                section_result = {
                    'status': quality_result.status.value,
                    'section': section.to_dict(),
                    'polished_content': polished_content,
                    'quality_score': quality_result.score,
                    'quality_issues': quality_result.issues,
                    'quality_suggestions': quality_result.suggestions,
                    'retry_count': retry_count
                }
                
                if quality_result.score < quality_threshold and retry_count < max_retry:
                    print(f"  质量未达标 (要求: {quality_threshold})，尝试优化...")
                    retry_count += 1
                    retry_result = workflow._handle_quality_issue(section, section_result)
                    if retry_result:
                        section_result = retry_result
                        print(f"  ✓ 优化完成，新评分: {section_result['quality_score']:.2f}")
                    continue
                
                break
                
            except Exception as e:
                print(f"  ✗ 处理失败: {e}")
                if retry_count >= max_retry:
                    section_result = {
                        'status': 'failed',
                        'section': section.to_dict(),
                        'polished_content': section.content,
                        'quality_score': 0,
                        'quality_issues': [str(e)],
                        'quality_suggestions': [],
                        'retry_count': retry_count
                    }
                else:
                    retry_count += 1
                    print(f"  重试中...")
        
        if section_result:
            processed_sections.append(section_result)
            total_quality_score += section_result['quality_score']
            
            print(f"\n  ✓ 分段 {idx + 1} 处理完成")
    
    print("\n第6步: 生成输出文档...")
    try:
        workflow._step4_generate_output(processed_sections, str(output_file))
        print(f"✓ 输出文档生成成功: {output_file}")
    except Exception as e:
        print(f"✗ 输出文档生成失败: {e}")
        traceback.print_exc()
        return
    
    print("\n" + "=" * 70)
    print("处理结果摘要")
    print("=" * 70)
    print(f"状态: completed")
    print(f"处理章节数: {len(processed_sections)}")
    print(f"总质量评分: {total_quality_score / len(processed_sections):.2f}")
    print(f"\n✓✓✓ 处理完成！")
    print(f"输出文件: {output_file}")
    
    return {
        'status': 'completed',
        'sections_processed': len(processed_sections),
        'total_quality_score': total_quality_score / len(processed_sections),
        'output_path': str(output_file)
    }

if __name__ == "__main__":
    main()
