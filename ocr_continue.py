"""
満洲紳士録 OCR 断点续传 v2
- 修复status.json同步问题
- 每10块保存一次进度
- 每150块发送飞书进度报告
- 处理完成后执行NER+CSV导出
"""
import os
import sys
import json
import time
from pathlib import Path

BASE_DIR = Path(r'C:\Users\lyzha\Desktop\AItools-for-historyresearch')
sys.path.insert(0, str(BASE_DIR))
os.chdir(str(BASE_DIR))

from modules.ndl_ocr_batch_processor import NDLOCRBatchProcessor

OUTPUT_BASE = BASE_DIR / 'ocr_output' / 'full_pages'
SPLIT_DIR = OUTPUT_BASE / 'split'
OCR_DIR = OUTPUT_BASE / 'ocr'
STATUS_FILE = OUTPUT_BASE / 'status.json'
TARGET_SESSION = 'agent:main:feishu:direct:ou_065e5bdad4f0989b318e12d180050312'

def load_status():
    with open(STATUS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_status(status):
    with open(STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

def get_ocr_txt_path(page, block):
    return OCR_DIR / f'page_{page:04d}' / f'page_{page:04d}_block_{block}.txt'

def get_block_image(page, block):
    return SPLIT_DIR / f'page_{page:04d}_block_{block}.png'

def send_progress(message):
    try:
        from openclaw_tool import sessions_send
        sessions_send(TARGET_SESSION, message)
    except Exception as e:
        print(f"[飞书] 发送失败: {e}")

def run_ner_export():
    """Step 5: NER提取和CSV导出"""
    print("\n" + "=" * 60)
    print("开始NER提取和CSV导出")
    print("=" * 60)

    sys.path.insert(0, str(BASE_DIR))
    from modules.biography_extractor import BiographicalNER

    ner = BiographicalNER()
    all_persons = []

    # Read all OCR results
    for page in range(1, 889):
        page_dir = OCR_DIR / f'page_{page:04d}'
        if not page_dir.exists():
            continue

        for block in range(3):
            txt_path = page_dir / f'page_{page:04d}_block_{block}.txt'
            if not txt_path.exists():
                continue

            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                if not text.strip():
                    continue

                # Process block (column 0=left, 1=middle, 2=right)
                persons = ner.process_vertical_layout(text, page)
                for p in persons:
                    p.column_index = block
                    all_persons.append(p)
            except Exception as e:
                print(f"  Warning: page {page} block {block}: {e}")

        if page % 100 == 0:
            print(f"  已读取 {page}/888 页...")

    ner.persons = all_persons
    ner.sort_work_experiences()

    print(f"提取到 {len(all_persons)} 个人物实体")

    # Export CSV and JSON
    csv_path = OUTPUT_BASE / 'biography_data.csv'
    json_path = OUTPUT_BASE / 'biography_data.json'

    # Use BiographyExtractor's export methods
    from modules.biography_extractor import BiographyExtractor
    # We need to use the PersonEntity list directly
    # Write CSV manually
    import csv as csvmod
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csvmod.writer(f)
        writer.writerow([
            '姓名', '读音', '本籍', '出生年月', '学历',
            '工作单位1', '工作时间1', '工作单位2', '工作时间2', '工作单位3', '工作时间3',
            '页码', '列索引', '原始文本'
        ])
        for p in all_persons:
            exps = p.work_experiences[:3]
            row = [
                p.name or '',
                p.reading or '',
                p.hometown or '',
                p.birth_date or '',
                p.education or '',
            ]
            for i in range(3):
                if i < len(exps):
                    e = exps[i]
                    row.extend([e.get('unit',''), e.get('date_range','')])
                else:
                    row.extend(['', ''])
            row.extend([p.page_number or '', p.column_index or '', p.original_text[:200] if p.original_text else ''])
            writer.writerow(row)

    # Write JSON
    json_data = {
        'total': len(all_persons),
        'persons': [
            {
                'name': p.name,
                'reading': p.reading,
                'hometown': p.hometown,
                'birth_date': p.birth_date,
                'education': p.education,
                'work_experiences': p.work_experiences,
                'page_number': p.page_number,
                'column_index': p.column_index,
                'original_text': p.original_text,
            }
            for p in all_persons
        ]
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print(f"CSV导出: {csv_path}")
    print(f"JSON导出: {json_path}")
    return len(all_persons)

def main():
    print("=" * 60)
    print("満洲紳士録 OCR 断点续传 v2")
    print("=" * 60)

    # Load current status
    status = load_status()
    processed_blocks = set(status['processed_blocks'])
    current_page = status.get('current_page', 1)

    total_done = len(processed_blocks)
    print(f"当前: {total_done}/2664 块 ({total_done/2664*100:.1f}%)")
    print(f"current_page: {current_page}")

    # Find start point
    start_page = current_page + 1
    if start_page < 151:
        start_page = 151

    # Find blocks to process
    blocks_to_process = []
    for page in range(start_page, 889):
        for block in range(3):
            block_id = f'{page}-{block}'
            if block_id not in processed_blocks:
                blocks_to_process.append((page, block))

    total_remaining = len(blocks_to_process)
    pages_remaining = total_remaining // 3 + (1 if total_remaining % 3 else 0)
    est_hours = total_remaining * 16 / 3600

    print(f"待处理: {total_remaining} 块 ({pages_remaining} 页)")
    print(f"预计耗时: ~{est_hours:.1f}小时")
    print()

    if not blocks_to_process:
        print("全部完成! 开始NER提取...")
        run_ner_export()
        return

    # Initialize processor
    processor = NDLOCRBatchProcessor()

    processed_count = 0
    session_start = time.time()
    last_save_at = 0
    last_report_at = 0
    SAVE_INTERVAL = 10  # Save every 10 blocks
    REPORT_INTERVAL = 150  # Report every 150 blocks

    print(f"开始处理从 page {blocks_to_process[0][0]}...")
    print(f"每{SAVE_INTERVAL}块保存进度，每{REPORT_INTERVAL}块报告飞书")
    print()

    for page, block in blocks_to_process:
        block_id = f'{page}-{block}'
        img_path = get_block_image(page, block)

        if not img_path.exists():
            print(f"[WARN] 找不到图片: {img_path}")
            continue

        output_dir = OCR_DIR / f'page_{page:04d}'
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{processed_count+1}/{total_remaining}] page {page:04d} block {block}...", end=" ", flush=True)

        try:
            success, text = processor.process_image(str(img_path), str(output_dir), timeout=120)

            if success:
                txt_path = get_ocr_txt_path(page, block)
                if txt_path.exists():
                    processed_blocks.add(block_id)
                    status['processed_blocks'] = list(processed_blocks)
                    status['current_page'] = page
                    processed_count += 1

                    # Frequent save
                    if processed_count - last_save_at >= SAVE_INTERVAL:
                        save_status(status)
                        last_save_at = processed_count

                    print(f"OK ({len(text)} chars)")
                else:
                    print(f"FAIL (输出文件未生成)")
            else:
                print(f"FAIL ({str(text)[:50] if text else 'error'})")
        except Exception as e:
            print(f"EXCEPTION ({e})")

        # Progress report
        if processed_count - last_report_at >= REPORT_INTERVAL:
            elapsed = time.time() - session_start
            rate = processed_count / elapsed * 3600 if elapsed > 0 else 0
            remaining_blocks = total_remaining - processed_count
            est_remaining_hours = remaining_blocks / rate / 3600 if rate > 0 else 0
            total_done_now = len(processed_blocks)
            pct = total_done_now / 2664 * 100

            msg = (
                f"## 📊 OCR进度报告\n"
                f"- 已完成: {total_done_now//3}/888页 ({pct:.1f}%)\n"
                f"- 本次新增: {processed_count}块\n"
                f"- 速度: {rate:.0f}块/小时\n"
                f"- 预计剩余: ~{est_remaining_hours:.1f}小时\n"
                f"- 当前: page {page}"
            )
            print(f"\n{msg}")
            send_progress(msg)
            last_report_at = processed_count

        time.sleep(0.3)

    # Final save
    save_status(status)

    elapsed = time.time() - session_start
    total_done = len(processed_blocks)
    pct = total_done / 2664 * 100

    print(f"\n{'='*60}")
    print(f"OCR完成!")
    print(f"总进度: {total_done}/2664 ({pct:.1f}%)")
    print(f"本次处理: {processed_count}块")
    print(f"耗时: {elapsed/3600:.2f}小时")

    send_progress(
        f"## 📊 OCR完成!\n"
        f"- 总计: {total_done}/2664块 ({pct:.1f}%)\n"
        f"- 本次: {processed_count}块\n"
        f"- 耗时: {elapsed/3600:.2f}小时"
    )

    # NER导出
    print("\n开始NER提取...")
    try:
        person_count = run_ner_export()
        send_progress(f"## ✅ NER导出完成!\n- 提取人物: {person_count}人\n- CSV: biography_data.csv\n- JSON: biography_data.json")
    except Exception as e:
        print(f"NER导出失败: {e}")
        send_progress(f"## ⚠️ NER导出失败: {e}")

if __name__ == '__main__':
    main()
