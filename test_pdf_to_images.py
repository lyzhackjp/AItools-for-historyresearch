#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple PDF to images test"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
import fitz

pdf_path = r"c:\Users\lyzha\Desktop\AItools-for-historyresearch\伊藤博文伝 中-1.pdf"
output_dir = r"c:\Users\lyzha\Desktop\AItools-for-historyresearch\temp_images"
Path(output_dir).mkdir(exist_ok=True)

print(f"Opening PDF: {pdf_path}")
doc = fitz.open(pdf_path)
print(f"Total pages: {len(doc)}")

for page_num in range(len(doc)):
    page = doc[page_num]
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    output_file = Path(output_dir) / f"page_{page_num + 1:04d}.png"
    pix.save(str(output_file))
    print(f"Saved: {output_file}")

doc.close()
print("Done!")
