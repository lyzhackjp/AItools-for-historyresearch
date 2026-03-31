"""
史料发言识别与年代提取模块 - 测试脚本

测试场景：
1. 第一次测试：使用已有OCR结果（JSON格式）
2. 第二次测试：从PDF从头执行完整流程

使用方法：
python test_historical_speech_extractor.py --test 1  # 使用已有OCR结果
python test_historical_speech_extractor.py --test 2  # 从PDF从头处理
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.historical_speech_extractor import (
    HistoricalSpeechExtractor, 
    create_speech_extractor
)


def test_with_existing_ocr():
    """第一次测试：使用已有OCR结果"""
    print("\n" + "=" * 60)
    print("第一次测试：使用已有OCR结果")
    print("=" * 60)
    
    ocr_json_path = project_root / "data" / "output" / "ocr_results" / "final" / "llm_ocr_result_20260330_194807.json"
    ocr_csv_path = project_root / "data" / "output" / "ocr_results" / "final" / "llm_ocr_result_20260330_194807.csv"
    ocr_txt_path = project_root / "data" / "output" / "ocr_results" / "final" / "llm_ocr_result_20260330_194807.txt"
    
    if ocr_json_path.exists():
        print(f"\n[选择数据源] JSON格式: {ocr_json_path}")
        ocr_path = ocr_json_path
    elif ocr_csv_path.exists():
        print(f"\n[选择数据源] CSV格式: {ocr_csv_path}")
        ocr_path = ocr_csv_path
    elif ocr_txt_path.exists():
        print(f"\n[选择数据源] TXT格式: {ocr_txt_path}")
        ocr_path = ocr_txt_path
    else:
        print("错误：未找到OCR结果文件")
        return None
    
    extractor = create_speech_extractor(api_provider="qwen", test_mode=True)
    
    print(f"\n[步骤1] 加载OCR结果...")
    ocr_data = extractor.load_ocr_result(str(ocr_path))
    print(f"  加载页数: {len(ocr_data.get('pages', []))}")
    
    print(f"\n[步骤2] 分析出版年代...")
    publication_info = extractor.analyze_publication_date(ocr_data)
    print(f"  推断年份: {publication_info.get('inferred_year')}")
    print(f"  年号: {publication_info.get('era')}")
    print(f"  置信度: {publication_info.get('confidence')}")
    if publication_info.get('evidence'):
        print(f"  证据:")
        for evidence in publication_info['evidence']:
            print(f"    - {evidence}")
    
    print(f"\n[步骤3] 处理OCR结果...")
    records = extractor.process_ocr_result(ocr_data)
    print(f"  处理页数: {len(records)}")
    
    print(f"\n[步骤4] 提取统计信息...")
    stats = extractor.get_statistics(records)
    print(f"  总发言数: {stats['total_speeches']}")
    print(f"  总年代数: {stats['total_dates']}")
    print(f"  总实体数: {stats['total_entities']}")
    print(f"  独立发言者: {stats['unique_speakers']}")
    
    if stats.get('year_range'):
        print(f"  年代范围: {stats['year_range']['min']} - {stats['year_range']['max']}")
    
    if stats.get('top_speakers'):
        print(f"  主要发言者:")
        for speaker, count in stats['top_speakers'][:5]:
            print(f"    - {speaker}: {count}次")
    
    if stats.get('entity_type_distribution'):
        print(f"  实体类型分布:")
        for entity_type, count in stats['entity_type_distribution'].items():
            print(f"    - {entity_type}: {count}个")
    
    output_dir = project_root / "data" / "output" / "speech_extraction"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n[步骤5] 导出结果...")
    
    json_output = output_dir / f"speech_result_{timestamp}.json"
    extractor.export_results(records, str(json_output), format='json')
    
    csv_output = output_dir / f"speech_result_{timestamp}.csv"
    extractor.export_results(records, str(csv_output), format='csv')
    
    md_output = output_dir / f"speech_result_{timestamp}.md"
    extractor.export_results(records, str(md_output), format='markdown')
    
    print(f"\n[完成] 结果已保存到: {output_dir}")
    
    print(f"\n[详细结果预览]")
    print("-" * 40)
    
    for i, record in enumerate(records[:3]):
        print(f"\n=== 第{record.page_number}页 ===")
        
        if record.speeches:
            print(f"发言内容 ({len(record.speeches)}条):")
            for j, speech in enumerate(record.speeches[:3], 1):
                print(f"  {j}. [{speech.speech_type}] {speech.speaker or '未知'}")
                print(f"     {speech.text[:80]}...")
        
        if record.dates:
            print(f"年代信息 ({len(record.dates)}条):")
            for date in record.dates[:3]:
                date_str = f"{date.year}年"
                if date.month:
                    date_str += f"{date.month}月"
                if date.day:
                    date_str += f"{date.day}日"
                if date.era_name:
                    date_str += f" ({date.era_name})"
                print(f"  - {date_str}")
        
        if record.entities:
            print(f"命名实体 ({len(record.entities)}个):")
            entity_by_type = {}
            for entity in record.entities[:10]:
                cat = entity.get('category', 'unknown')
                if cat not in entity_by_type:
                    entity_by_type[cat] = []
                entity_by_type[cat].append(entity.get('entity', ''))
            
            for cat, entities in entity_by_type.items():
                print(f"  - {cat}: {', '.join(entities[:5])}")
    
    return records


def test_with_pdf_direct():
    """第二次测试：从PDF从头执行完整流程"""
    print("\n" + "=" * 60)
    print("第二次测试：从PDF从头执行完整流程")
    print("=" * 60)
    
    pdf_path = project_root / "伊藤博文伝 中-1.pdf"
    
    if not pdf_path.exists():
        print(f"错误：PDF文件不存在: {pdf_path}")
        return None
    
    print(f"\n[步骤1] PDF OCR处理...")
    print(f"  PDF路径: {pdf_path}")
    print(f"  页面范围: 41-45页")
    
    from modules.llm_ocr_processor import QwenVLOCRProcessor
    
    output_dir = project_root / "data" / "output" / "ocr_results"
    
    try:
        ocr_processor = QwenVLOCRProcessor(
            pdf_path=str(pdf_path),
            output_dir=str(output_dir)
        )
        
        print(f"\n  正在处理PDF...")
        ocr_pages = ocr_processor.process_all_pages(start_page=41, end_page=45)
        print(f"  OCR处理完成: {len(ocr_pages)}页")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ocr_json_path = output_dir / "final" / f"test_ocr_{timestamp}.json"
        ocr_processor.export_json(ocr_pages, str(ocr_json_path))
        print(f"  OCR结果保存: {ocr_json_path}")
        
        ocr_data = {
            'metadata': {
                'processing_date': datetime.now().isoformat(),
                'ocr_method': 'qwen-vl-ocr-latest',
                'total_pages': len(ocr_pages)
            },
            'pages': []
        }
        
        for page in ocr_pages:
            ocr_data['pages'].append({
                'pdf_page_number': page.pdf_page_number,
                'ocr_page_number': page.ocr_page_number,
                'header': page.header,
                'footer': page.footer,
                'text': page.text,
                'text_length': page.text_length
            })
        
    except Exception as e:
        print(f"  OCR处理失败: {e}")
        print(f"  使用已有OCR结果进行测试...")
        
        ocr_json_path = project_root / "data" / "output" / "ocr_results" / "final" / "llm_ocr_result_20260330_194807.json"
        if ocr_json_path.exists():
            with open(ocr_json_path, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
            ocr_data['pages'] = ocr_data['pages'][:5]
        else:
            print("错误：无法获取OCR数据")
            return None
    
    print(f"\n[步骤2] 发言识别与年代提取...")
    
    extractor = create_speech_extractor(api_provider="qwen", test_mode=True)
    
    records = extractor.process_ocr_result(ocr_data)
    print(f"  处理页数: {len(records)}")
    
    print(f"\n[步骤3] 提取统计信息...")
    stats = extractor.get_statistics(records)
    print(f"  总发言数: {stats['total_speeches']}")
    print(f"  总年代数: {stats['total_dates']}")
    print(f"  总实体数: {stats['total_entities']}")
    
    output_dir = project_root / "data" / "output" / "speech_extraction"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    json_output = output_dir / f"speech_result_from_pdf_{timestamp}.json"
    extractor.export_results(records, str(json_output), format='json')
    
    md_output = output_dir / f"speech_result_from_pdf_{timestamp}.md"
    extractor.export_results(records, str(md_output), format='markdown')
    
    print(f"\n[完成] 结果已保存到: {output_dir}")
    
    return records


def main():
    parser = argparse.ArgumentParser(description='史料发言识别与年代提取模块测试')
    parser.add_argument('--test', type=int, default=1, choices=[1, 2],
                       help='测试类型: 1=使用已有OCR结果, 2=从PDF从头处理')
    parser.add_argument('--test-mode', action='store_true',
                       help='使用测试模式（不调用真实API）')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("史料发言识别与年代提取模块 - 测试脚本")
    print("=" * 60)
    print(f"测试类型: {args.test}")
    print(f"测试模式: {'启用' if args.test_mode else '禁用'}")
    print(f"项目根目录: {project_root}")
    
    if args.test == 1:
        records = test_with_existing_ocr()
    else:
        records = test_with_pdf_direct()
    
    if records:
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
