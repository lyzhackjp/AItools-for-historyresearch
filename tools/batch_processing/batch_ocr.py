"""
批量OCR处理脚本
"""

import os
import subprocess
from pathlib import Path
import time

def main():
    """主函数"""
    
    base_dir = Path(__file__).parent.parent.parent
    img_dir = base_dir / "data" / "input" / "test_images"
    ndlocr_path = base_dir / "ndlocr-lite" / "src" / "ocr.py"
    output_dir = base_dir / "data" / "output" / "ocr_results"
    
    os.makedirs(output_dir, exist_ok=True)
    
    image_files = sorted(img_dir.glob("page_*.png"))[:20]
    
    print(f"找到 {len(image_files)} 张图片")
    print(f"输出目录: {output_dir}")
    
    start_time = time.time()
    
    for i, img_path in enumerate(image_files, 1):
        print(f"[{i:2d}/20] {img_path.name}...", end=" ", flush=True)
        
        result_dir = output_dir / f"page_{i:04d}"
        os.makedirs(result_dir, exist_ok=True)
        
        try:
            cmd = [
                "python",
                str(ndlocr_path),
                "--sourceimg",
                str(img_path),
                "--output",
                str(result_dir)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                txt_file = result_dir / f"{img_path.stem}.txt"
                if txt_file.exists():
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        text = f.read()
                        print(f"✓ {len(text)} 字符")
                else:
                    print("✓ 完成")
            else:
                print(f"✗ {result.stderr[:50] if result.stderr else '错误'}")
                
        except subprocess.TimeoutExpired:
            print("✗ 超时")
        except Exception as e:
            print(f"✗ {e}")
    
    elapsed = time.time() - start_time
    print(f"\n用时: {elapsed:.1f} 秒")
    print(f"结果保存在: {output_dir}")

if __name__ == "__main__":
    main()
