"""
批量OCR测试 - 5页×3块
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from modules.ndl_ocr_batch_processor import NDLOCRBatchProcessor


def main():
    processor = NDLOCRBatchProcessor()

    pages = ['0398', '0399', '0400', '0401', '0402']
    blocks = ['left', 'middle', 'right']

    total = len(pages) * len(blocks)
    current = 0
    results = []

    print(f"开始批量 OCR 测试: {total} 个块")
    print("=" * 50)

    for page in pages:
        for block in blocks:
            current += 1
            block_path = f'ocr_output/test_blocks/split_all/page_{page}/page_{page}_{block}.png'
            output_dir = f'ocr_output/test_blocks/ndl_batch/page_{page}_{block}'
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            print(f"[{current}/{total}] {page}_{block}...", end=' ')

            start = time.time()
            success, text = processor.process_image(block_path, output_dir)
            elapsed = time.time() - start

            if success:
                char_count = len(text)
                # 保存合并结果
                txt_file = Path(output_dir) / f'page_{page}_{block}.txt'
                with open(txt_file, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f"OK {char_count} chars ({elapsed:.1f}s)")

                results.append({
                    'page': page,
                    'block': block,
                    'success': True,
                    'chars': char_count,
                    'time': elapsed
                })
            else:
                print(f"FAIL")
                results.append({
                    'page': page,
                    'block': block,
                    'success': False,
                    'chars': 0,
                    'time': elapsed
                })

    print("\n" + "=" * 50)
    print("批量测试完成!")

    # 统计
    success_count = sum(1 for r in results if r['success'])
    total_chars = sum(r['chars'] for r in results)
    avg_time = sum(r['time'] for r in results) / len(results)

    print(f"成功: {success_count}/{total}")
    print(f"总字符: {total_chars}")
    print(f"平均耗时: {avg_time:.1f}秒/块")

    # 估算全量处理时间
    total_blocks = 888 * 3  # 每页3块
    estimated_time = (total_blocks / 3) * avg_time / 60
    print(f"估算全量处理时间: {estimated_time:.0f} 分钟")


if __name__ == "__main__":
    main()
