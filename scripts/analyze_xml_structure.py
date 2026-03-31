import sys
sys.path.append('modules')
from docx import Document
from lxml import etree
import zipfile

file_path = 'TW《新渡户论》20260324.docx'
doc = Document(file_path)

print("=== 方法1: 通过doc.element访问 ===")
ns1 = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
footnotes1 = doc.element.findall('.//w:footnote', ns1)
print(f"找到 {len(footnotes1)} 个脚注")

print()
print("=== 方法2: 直接读取XML字符串 ===")
with zipfile.ZipFile(file_path, 'r') as z:
    with z.open('word/document.xml') as f:
        doc_xml = f.read()
        tree = etree.fromstring(doc_xml)
        ns2 = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        footnotes2 = tree.findall('.//w:footnote', ns2)
        print(f"从document.xml找到 {len(footnotes2)} 个脚注")

        if len(footnotes2) > 0:
            print()
            print("=== 第一个脚注的XML结构 ===")
            print(etree.tostring(footnotes2[0], pretty_print=True, encoding='unicode')[:500])

print()
print("=== 检查Office不同命名空间的脚注 ===")
all_ns = set()
for elem in tree.iter():
    if elem.tag.startswith('{'):
        ns_tag = elem.tag.split('}')[0][1:]
        all_ns.add(ns_tag)

print("文档中使用的所有命名空间:")
for ns in sorted(all_ns):
    print(f"  {ns}")

print()
print("=== 尝试使用通配符查找 ===")
wildcard_footnotes = tree.findall('.//{*}footnote')
print(f"使用通配符找到 {len(wildcard_footnotes)} 个footnote元素")

if len(wildcard_footnotes) > 0:
    print()
    print("=== 第一个脚注的完整XML ===")
    print(etree.tostring(wildcard_footnotes[0], pretty_print=True, encoding='unicode')[:1000])
