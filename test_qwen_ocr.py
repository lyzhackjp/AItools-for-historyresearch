"""
测试Qwen VL OCR在人物传记页面上的效果
使用压缩图片避免超过10MB限制
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

def resize_image(image_path, max_size=(2000, 2000)):
    """调整图片大小以减少体积"""
    img = Image.open(image_path)

    # 计算新尺寸
    ratio = min(max_size[0] / img.width, max_size[1] / img.height)
    if ratio < 1:
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        print(f"图片已压缩: {img.width}x{img.height}")

    # 保存为临时文件
    temp_path = image_path.replace('.png', '_compressed.jpg')
    img.save(temp_path, 'JPEG', quality=85)
    return temp_path

def test_qwen_ocr(image_path, max_size=(2000, 2000)):
    """测试Qwen VL OCR"""
    api_key = read_api_key()
    if not api_key:
        print("未找到API密钥")
        return None

    print(f"API key: {api_key[:10]}...")

    # 压缩图片
    print(f"原始图片: {image_path}")
    compressed_path = resize_image(image_path, max_size)

    # 读取图片
    with open(compressed_path, 'rb') as f:
        image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

    print(f"压缩后大小: {len(image_data) / 1024 / 1024:.2f} MB")

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
                        {'text': '这是日本历史文献的页面图片。请仔细识别图片中的所有文字，注意这是竖排日文（从右到左阅读）。请按原样输出所有识别出的文字。'}
                    ]
                }
            ]
        },
        'parameters': {
            'temperature': 0.1,
            'max_tokens': 4000
        }
    }

    print("发送请求到 Qwen VL OCR...")

    resp = requests.post(
        'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
        headers=headers,
        json=payload,
        timeout=180
    )

    # 删除临时文件
    if compressed_path != image_path and os.path.exists(compressed_path):
        os.remove(compressed_path)

    print(f"状态码: {resp.status_code}")

    if resp.status_code == 200:
        result = resp.json()
        if 'output' in result and 'choices' in result['output']:
            text = result['output']['choices'][0]['message']['content']
            print(f"\n识别文字长度: {len(text)} 字符")
            print("\n" + "="*60)
            print("OCR 识别结果 (前3000字符):")
            print("="*60)
            print(text[:3000])

            # 保存结果
            output_path = Path(image_path).parent / f"{Path(image_path).stem}_qwen_ocr.txt"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"\n结果已保存到: {output_path}")

            return text
        else:
            print("响应格式错误:")
            print(json.dumps(result, ensure_ascii=False, indent=2)[:1000])
    else:
        print(f"请求失败: {resp.status_code}")
        print(resp.text[:500])
        return None

if __name__ == "__main__":
    # 测试第15页
    image_path = Path(__file__).parent / 'ndl-search' / 'ocr_test' / 'images3' / 'page_0015.png'

    if image_path.exists():
        test_qwen_ocr(str(image_path))
    else:
        print(f"图片不存在: {image_path}")
