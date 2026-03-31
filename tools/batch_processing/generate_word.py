"""
Word文档生成脚本
从OCR结果生成Word文档
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.doc_processor import DocProcessor
from modules.ndlocr_result_processor import create_result_processor


def main():
    """主函数"""
    
    print("="*60)
    print("生成Word文档")
    print("="*60)
    
    base_dir = Path(__file__).parent
    ocr_output_dir = base_dir / "ocr_output"
    word_output = base_dir / "output" / "伊藤博文伝_OCR识别结果.docx"
    
    os.makedirs(word_output.parent, exist_ok=True)
    
    page_dirs = sorted(ocr_output_dir.glob("page_*"))
    
    print(f"\n找到 {len(page_dirs)} 页OCR结果")
    
    all_texts = []
    
    for i, page_dir in enumerate(page_dirs, 1):
        page_name = page_dir.name
        
        txt_files = list(page_dir.glob("*.txt"))
        
        if txt_files:
            txt_file = txt_files[0]
            with open(txt_file, 'r', encoding='utf-8') as f:
                text = f.read()
            
            all_texts.append(text)
            print(f"  Page {i:2d}: {len(text):5d} 字符")
        else:
            print(f"  Page {i:2d}: 无文本文件")
    
    print(f"\n总字符数: {sum(len(t) for t in all_texts):,}")
    
    print("\n数据清洗...")
    processor = create_result_processor(
        remove_extra_spaces=True,
        normalize_unicode=True,
        fix_common_errors=True,
        remove_page_numbers=True
    )
    
    cleaned_texts = []
    for text in all_texts:
        cleaned = processor.clean_text(text)
        cleaned_texts.append(cleaned)
    
    print("\n生成Word文档...")
    doc_processor = DocProcessor()
    
    paragraphs = []
    for i, text in enumerate(cleaned_texts, 1):
        para = {
            'text': f"【第 {i} 页】\n\n{text}",
            'style': 'Normal',
            'alignment': 'LEFT'
        }
        paragraphs.append(para)
    
    content = {
        'title': '伊藤博文伝 中-1（OCR识别结果）',
        'paragraphs': paragraphs,
        'tables': []
    }
    
    success = doc_processor.create_document(content, str(word_output))
    
    if success:
        print(f"\n✅ Word文档生成成功!")
        print(f"📄 {word_output}")
        print(f"📑 共 {len(paragraphs)} 页")
        print("\n✨ 处理完成！")
    else:
        print("\n❌ Word文档生成失败")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
