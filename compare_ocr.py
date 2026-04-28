"""
OCR对比测试脚本
在相同块上对比 NDL OCR 和 Qwen VL OCR
"""
import sys
import os
import time
import base64
import requests
from pathlib import Path
from PIL import Image

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


def read_api_key():
    """读取API密钥"""
    keys_file = Path(__file__).parent / 'secrets' / 'api_keys.txt'
    with open(keys_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('qwen'):
                return line.split('=')[1].strip()
    return None


def compress_image(image_path, max_pixels=(2000, 2000), quality=85):
    """压缩图片"""
    img = Image.open(image_path)
    ratio = min(max_pixels[0] / img.width, max_pixels[1] / img.height)
    if ratio < 1:
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    img = img.convert('RGB')
    temp_path = image_path.replace('.png', '_qwen.jpg')
    img.save(temp_path, 'JPEG', quality=quality, optimize=True)
    return temp_path


def ocr_with_qwen(image_path, api_key):
    """使用 Qwen VL OCR"""
    compressed = compress_image(image_path)

    with open(compressed, 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

    size_mb = len(image_data) / 1024 / 1024
    if size_mb > 9.5:
        print(f"图片太大: {size_mb:.2f}MB")
        return None

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': 'qwen-vl-ocr',
        'input': {
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'image': f'data:image/jpeg;base64,{image_base64}'},
                        {'text': '''这是一页日本历史文献。请仔细识别所有文字。

注意：
1. 这是竖排日文文献
2. 每个人物条目包含：姓名、出生、本籍、学历、工作经历等信息
3. 请按原阅读顺序输出所有文字
4. 时间格式如"明治42年"、"昭和8年12月"等'''}
                    ]
                }
            ]
        },
        'parameters': {
            'temperature': 0.1,
            'max_tokens': 4000
        }
    }

    print(f"发送 Qwen VL OCR 请求 ({size_mb:.2f}MB)...")

    resp = requests.post(
        'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
        headers=headers,
        json=payload,
        timeout=180
    )

    # 删除临时文件
    if os.path.exists(compressed):
        os.remove(compressed)

    if resp.status_code == 200:
        result = resp.json()
        if 'output' in result and 'choices' in result['output']:
            content = result['output']['choices'][0]['message']['content']
            if isinstance(content, list):
                return '\n'.join([item.get('text', '') for item in content if isinstance(item, dict)])
            return content
    else:
        print(f"Qwen OCR 错误: {resp.status_code} - {resp.text[:200]}")
    return None


def main():
    api_key = read_api_key()
    if not api_key:
        print("未找到 API 密钥")
        return

    # 测试块
    block_path = Path('ocr_output/test_blocks/split_all/page_0400/page_0400_middle.png')

    if not block_path.exists():
        print(f"文件不存在: {block_path}")
        return

    print(f"测试图片: {block_path}")
    print("=" * 60)

    # Qwen VL OCR
    print("\n[Qwen VL OCR]")
    start = time.time()
    qwen_text = ocr_with_qwen(str(block_path), api_key)
    qwen_time = time.time() - start

    if qwen_text:
        print(f"识别成功! 耗时: {qwen_time:.1f}秒, 字符数: {len(qwen_text)}")

        # 保存结果
        output_path = block_path.with_suffix('.qwen.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(qwen_text)
        print(f"保存到: {output_path}")

        print("\n--- Qwen OCR 结果 (前1500字符) ---")
        print(qwen_text[:1500])
    else:
        print("Qwen OCR 失败")

    print("\n" + "=" * 60)

    # NDL OCR
    print("\n[NDL OCR]")
    from modules.ndl_ocr_batch_processor import NDLOCRBatchProcessor

    processor = NDLOCRBatchProcessor()
    start = time.time()
    success, ndl_text = processor.process_image(str(block_path), 'ocr_output/test_blocks/ndl_single')
    ndl_time = time.time() - start

    if success:
        print(f"识别成功! 耗时: {ndl_time:.1f}秒, 字符数: {len(ndl_text)}")

        # 保存结果
        output_path = block_path.with_suffix('.ndl.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ndl_text)
        print(f"保存到: {output_path}")

        print("\n--- NDL OCR 结果 (前1500字符) ---")
        print(ndl_text[:1500])
    else:
        print("NDL OCR 失败")


if __name__ == "__main__":
    main()
