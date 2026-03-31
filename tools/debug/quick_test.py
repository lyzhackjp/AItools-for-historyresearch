#!/usr/bin/env python3
"""优化后的搜索功能测试"""
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.ndl_downloader.selenium_downloader import NDLSeleniumDownloader

print("开始测试...")
downloader = NDLSeleniumDownloader(output_dir="./test_downloads", headless=True)
items = downloader.search_items("井上哲次郎", max_results=3)
print(f"找到: {len(items)}个结果")
for i, item in enumerate(items[:3], 1):
    title = item.get('title', 'N/A')
    print(f"  {i}. {title[:50]}...")
downloader.close()
print("完成")
