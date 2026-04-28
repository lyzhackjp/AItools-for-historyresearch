"""
测试 Qwen VL OCR 在压缩后图片上的效果
"""
import os
import sys
import json
import base64
import requests
from pathlib import Path
from PIL import Image

def read_api_key():
    """读取API密钥"""
    api_keys_file = Path(__file__).parent / 'secrets' / 'api_keys.txt'
    with open(api_keys_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('qwen'):
                return line.split('=')[1].strip()
    return None

def compress_image(image_path, max_pixels=(1800, 1800), quality=85):
    """压缩图片"""
    img = Image.open(image_path)

    # 计算缩放比例
    ratio = min(max_pixels[0] / img.width, max_pixels[1] / img.height)
    if ratio < 1:
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # 保存为 JPEG
    temp_path = image_path.replace('.png', '_qwen.jpg')
    img = img.convert('RGB')  # 确保是RGB模式
    img.save(temp_path, 'JPEG', quality=quality, optimize=True)

    size_mb = os.path.getsize(temp_path) / 1024 / 1024
    print(f"压缩后: {img.width}x{img.height}, {size_mb:.2f}MB")
    return temp_path

def ocr_image_qwen(image_path, api_key):
    """使用 Qwen VL OCR 识别图片"""

    # 压缩图片
    compressed = compress_image(image_path)

    # 读取图片
    with open(compressed, 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

    # 检查大小
    size_mb = len(image_data) / 1024 / 1024
    if size_mb > 9.5:
        print(f"图片仍然太大: {size_mb:.2f}MB")
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
1. 这是竖排日文，从右到左阅读
2. 页面分为多个竖向列块
3. 人名通常是大字粗体
4. 每个人物条目包含：姓名、本籍、学历、工作经历等信息
5. 请按原阅读顺序输出文字，每条信息之间用换行分隔
6. 识别时间格式如"明治19年6月"、"昭和15年"等'''}
                    ]
                }
            ]
        },
        'parameters': {
            'temperature': 0.1,
            'max_tokens': 4000
        }
    }

    print(f"发送请求... ({size_mb:.2f}MB)")

    resp = requests.post(
        'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
        headers=headers,
        json=payload,
        timeout=180
    )

    # 删除临时文件
    if os.path.exists(compressed):
        os.remove(compressed)

    print(f"状态码: {resp.status_code}")

    if resp.status_code == 200:
        result = resp.json()
        if 'output' in result and 'choices' in result['output']:
            message = result['output']['choices'][0]['message']
            # 提取文本内容
            content = message.get('content', [])
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and 'text' in item:
                        text_parts.append(item['text'])
                text = '\n'.join(text_parts)
            elif isinstance(content, str):
                text = content
            else:
                text = str(content)
            return text
        else:
            print("响应:", json.dumps(result, ensure_ascii=False)[:500])
            return None
    else:
        print(f"错误: {resp.status_code} - {resp.text[:300]}")
        return None

if __name__ == "__main__":
    api_key = read_api_key()
    if not api_key:
        print("未找到 API 密钥")
        sys.exit(1)

    # 测试第20页
    image_path = Path(__file__).parent / 'ocr_output' / 'pages' / 'page_0020.png'

    if not image_path.exists():
        print(f"图片不存在: {image_path}")
        sys.exit(1)

    print(f"测试图片: {image_path}")

    text = ocr_image_qwen(str(image_path), api_key)

    if text:
        print("\n" + "="*60)
        print("OCR 结果 (前4000字符):")
        print("="*60)
        print(text[:4000])

        # 保存结果
        output_path = image_path.with_suffix('.qwen_ocr.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"\n已保存到: {output_path}")
