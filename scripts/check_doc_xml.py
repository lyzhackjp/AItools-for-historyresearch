import sys
sys.path.append('modules')
from docx import Document
from lxml import etree
import zipfile

file_path = 'TW《新渡户论》20260324.docx'
doc = Document(file_path)

print("=== 检查document.xml中是否有脚注相关内容 ===")
with zipfile.ZipFile(file_path, 'r') as z:
    print("ZIP文件中的文件列表:")
    for name in z.namelist():
        if 'footnote' in name.lower():
            print(f"  {name}")

    with z.open('word/document.xml') as f:
        content = f.read().decode('utf-8')
        if 'footnote' in content.lower():
            print("\n在document.xml中找到'footnote'关键字")
            print(f"document.xml文件大小: {len(content)} 字符")

            idx = content.lower().find('footnote')
            print(f"\n周围内容示例:")
            print(content[max(0, idx-100):idx+200])
        else:
            print("\ndocument.xml中没有'footnote'关键字")

print()
print("=== 检查word目录下的所有文件 ===")
with zipfile.ZipFile(file_path, 'r') as z:
    for name in z.namelist():
        if name.startswith('word/') and not name.endswith('/'):
            info = z.getinfo(name)
            print(f"  {name}: {info.file_size} bytes")
