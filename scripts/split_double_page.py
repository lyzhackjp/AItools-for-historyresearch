"""
Split double-page spread images into 6 blocks for OCR processing.

Layout:
- Image width: 5168 (double-page spread)
- Center fold at x = width // 2
- Right page (block_1, 2, 3): x = center to width
- Left page (block_4, 5, 6): x = 0 to center
- Each page split into 3 horizontal blocks

Output naming:
- Right page top: block_1
- Right page middle: block_2
- Right page bottom: block_3
- Left page top: block_4
- Left page middle: block_5
- Left page bottom: block_6
"""
import os
import sys
from pathlib import Path
from PIL import Image
from tqdm import tqdm

# Paths
BASE_DIR = Path(r'C:\Users\lyzha\Desktop\AItools-for-historyresearch')
IMAGES_DIR = BASE_DIR / 'ocr_output' / 'full_pages' / 'images'
OUTPUT_DIR = BASE_DIR / 'ocr_output' / 'full_pages' / 'split_new'  # New output dir for 6-block layout

# Page range
START_PAGE = 221
END_PAGE = 230

def split_image(img_path: Path, output_dir: Path) -> list[Path]:
    """Split a double-page spread image into 6 blocks."""
    img = Image.open(img_path)
    w, h = img.size

    # Calculate dimensions
    center = w // 2  # Center fold
    half_width = center
    block_height = h // 3

    output_paths = []

    # Right page blocks (block_1, 2, 3) - from right half
    for i, (x_start, y_start) in enumerate([
        (center, 0),           # block_1: top right
        (center, block_height),  # block_2: middle right
        (center, block_height * 2),  # block_3: bottom right
    ]):
        block_num = i + 1
        block = img.crop((x_start, y_start, w, y_start + block_height))

        out_name = f"{img_path.stem}_block_{block_num}.png"
        out_path = output_dir / out_name
        block.save(out_path, optimize=True)
        output_paths.append(out_path)

    # Left page blocks (block_4, 5, 6) - from left half
    for i, (x_start, y_start) in enumerate([
        (0, 0),               # block_4: top left
        (0, block_height),     # block_5: middle left
        (0, block_height * 2), # block_6: bottom left
    ]):
        block_num = i + 4
        block = img.crop((x_start, y_start, center, y_start + block_height))

        out_name = f"{img_path.stem}_block_{block_num}.png"
        out_path = output_dir / out_name
        block.save(out_path, optimize=True)
        output_paths.append(out_path)

    return output_paths

def main():
    print(f"Splitting pages {START_PAGE}-{END_PAGE}")
    print(f"Output directory: {OUTPUT_DIR}")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Clear existing files in range
    for page_num in range(START_PAGE, END_PAGE + 1):
        for block_num in range(1, 7):
            pattern = f"page_{page_num:04d}_block_{block_num}.png"
            for existing in OUTPUT_DIR.glob(pattern):
                existing.unlink()

    # Process pages
    total_blocks = 0
    for page_num in tqdm(range(START_PAGE, END_PAGE + 1), desc="Splitting pages"):
        img_name = f"page_{page_num:04d}.png"
        img_path = IMAGES_DIR / img_name

        if not img_path.exists():
            print(f"Warning: {img_path} not found, skipping")
            continue

        try:
            blocks = split_image(img_path, OUTPUT_DIR)
            total_blocks += len(blocks)
        except Exception as e:
            print(f"Error processing {img_name}: {e}")

    print(f"\nComplete! Split {total_blocks} blocks into {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
