"""
测试人物传记提取管道
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from modules.biography_extractor import extract_biographies


def progress(current, total, desc):
    print(f"[{current}/{total}] {desc}")


if __name__ == "__main__":
    pdf_path = Path(__file__).parent / 'ndl-search' / 'downloads' / 'manshu_shinshiroku_1687712_full.pdf'
    output_dir = Path(__file__).parent / 'ocr_output' / 'biography_test'

    print(f"PDF: {pdf_path}")
    print(f"Output: {output_dir}")
    print("-" * 50)

    # 测试前50页
    success = extract_biographies(
        str(pdf_path),
        str(output_dir),
        dpi=150,
        start_page=1,
        end_page=50,
        progress_callback=progress
    )

    if success:
        print("-" * 50)
        print("提取完成!")
    else:
        print("提取失败!")
