#!/usr/bin/env python3
"""
扫描书引用格式整理工具 - 使用示例

使用方法：
    python tools/book_citation_example.py --input ./scanned_books --output ./organized_books

功能：
    1. 扫描目录中的书籍文件（PDF、图片）
    2. 自动识别开头和末尾页面
    3. 提取书名、作者、出版社等元数据
    4. 生成规范文件名
    5. 导出多种引用格式的CSV文件
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.book_citation_organizer import BookCitationOrganizer


def main():
    parser = argparse.ArgumentParser(
        description='扫描书引用格式整理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例：
  python tools/book_citation_example.py --input ./scanned_books --output ./organized_books
  python tools/book_citation_example.py -i ./books -o ./output --front-pages 3 --back-pages 3
  python tools/book_citation_example.py -i ./books -o ./output --llm-provider openai --api-key sk-xxx
        '''
    )

    parser.add_argument(
        '-i', '--input',
        required=True,
        help='输入目录，包含待处理的扫描书籍文件'
    )

    parser.add_argument(
        '-o', '--output',
        required=True,
        help='输出目录，处理后的文件和新文件名存放位置'
    )

    parser.add_argument(
        '--front-pages',
        type=int,
        default=5,
        help='开头识别的页数（默认：5）'
    )

    parser.add_argument(
        '--back-pages',
        type=int,
        default=5,
        help='末尾识别的页数（默认：5）'
    )

    parser.add_argument(
        '--llm-provider',
        default='dashscope',
        choices=['dashscope', 'openai', 'zhipu', 'minimax', 'deepseek'],
        help='LLM服务商（默认：dashscope）'
    )

    parser.add_argument(
        '--api-key',
        default=None,
        help='API密钥（不提供则从环境变量读取）'
    )

    parser.add_argument(
        '--copy',
        action='store_true',
        default=True,
        help='复制文件到输出目录（默认：True）'
    )

    parser.add_argument(
        '--move',
        action='store_true',
        default=False,
        help='移动文件到输出目录（注意：会修改原文件）'
    )

    parser.add_argument(
        '--overwrite',
        action='store_true',
        default=False,
        help='覆盖已存在的输出文件'
    )

    args = parser.parse_args()

    # 验证输入目录
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：输入目录不存在: {input_path}")
        sys.exit(1)

    # 创建整理器
    organizer = BookCitationOrganizer(
        input_dir=str(input_path),
        output_dir=args.output,
        api_key=args.api_key,
        llm_provider=args.llm_provider,
        front_pages=args.front_pages,
        back_pages=args.back_pages,
        copy_files=not args.move,
        overwrite=args.overwrite
    )

    # 扫描文件
    files = organizer.scan_directory()
    print(f"发现 {len(files)} 个待处理文件")

    if not files:
        print("没有找到支持的文件（.pdf, .jpg, .jpeg, .png, .tif, .tiff）")
        sys.exit(0)

    # 处理所有文件
    print("开始处理...")
    results = organizer.process_all()

    # 导出CSV
    csv_path = Path(args.output) / 'book_citations.csv'
    organizer.export_csv(str(csv_path))

    # 显示摘要
    summary = organizer.get_summary()
    print(f"\n处理完成！")
    print(f"  总文件数: {summary['total_files']}")
    print(f"  成功: {summary['success']}")
    print(f"  失败: {summary['failed']}")
    print(f"  成功率: {summary['success_rate']}")
    print(f"\nCSV文件已保存至: {csv_path}")


if __name__ == '__main__':
    main()
