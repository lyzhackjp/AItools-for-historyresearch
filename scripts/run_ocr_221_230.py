"""
Run ndlocr-lite on pages 221-230 (block 1-6 each)
"""
import os
import sys
import subprocess
from pathlib import Path
from tqdm import tqdm

BASE_DIR = Path(r'C:\Users\lyzha\Desktop\AItools-for-historyresearch')
SPLIT_DIR = BASE_DIR / 'ocr_output' / 'full_pages' / 'split_new'
OUTPUT_DIR = BASE_DIR / 'ocr_output' / 'full_pages' / 'ocr_new'

START_PAGE = 221
END_PAGE = 230

# ndlocr-lite paths
NDLOCR_SCRIPT = BASE_DIR / 'ndlocr-lite' / 'src' / 'ocr.py'
PYTHON = sys.executable

def run_ocr(image_path: Path, output_dir: Path) -> dict:
    """Run ndlocr-lite on a single image."""
    cmd = [
        PYTHON,
        str(NDLOCR_SCRIPT),
        '--sourceimg', str(image_path),
        '--output', str(output_dir),
        '--device', 'cpu'
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    return {
        'returncode': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr
    }

def main():
    print(f"Running OCR on pages {START_PAGE}-{END_PAGE}")
    print(f"Output directory: {OUTPUT_DIR}")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get all blocks
    blocks = []
    for page_num in range(START_PAGE, END_PAGE + 1):
        for block_num in range(1, 7):
            block_name = f"page_{page_num:04d}_block_{block_num}.png"
            block_path = SPLIT_DIR / block_name
            if block_path.exists():
                blocks.append((page_num, block_num, block_path))

    print(f"Total blocks to process: {len(blocks)}")

    # Process blocks
    success_count = 0
    error_count = 0

    for page_num, block_num, block_path in tqdm(blocks, desc="OCR"):
        # Output will be: output_dir / stem.txt
        stem = block_path.stem  # page_0221_block_1
        expected_txt = OUTPUT_DIR / f"{stem}.txt"

        # Skip if already processed
        if expected_txt.exists():
            success_count += 1
            continue

        result = run_ocr(block_path, OUTPUT_DIR)

        if result['returncode'] == 0:
            success_count += 1
        else:
            error_count += 1
            print(f"\nError processing {block_path.name}:")
            print(f"  stderr: {result['stderr'][:200]}")

    print(f"\nComplete!")
    print(f"  Success: {success_count}")
    print(f"  Errors: {error_count}")

if __name__ == "__main__":
    main()
