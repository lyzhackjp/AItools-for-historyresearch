import sys
sys.path.append('modules')
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from lxml import etree
import zipfile

doc = Document()

print("=== 方式1: 使用part添加脚注 ===")
try:
    from docx.opc.part import Part
    from docx.opc.packuri import PackURI

    footnotes_part_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:footnote w:id="0" w:type="separator">
        <w:p>
            <w:r>
                <w:separator/>
            </w:r>
        </w:p>
    </w:footnote>
    <w:footnote w:id="1" w:type="normal">
        <w:p>
            <w:pPr>
                <w:pStyle w:val="FootnoteText"/>
            </w:pPr>
            <w:r>
                <w:rPr>
                    <w:rStyle w:val="FootnoteReference"/>
                </w:rPr>
                <w:footnoteRef/>
            </w:r>
            <w:r>
                <w:t>这是第一个脚注</w:t>
            </w:r>
        </w:p>
    </w:footnote>
</w:footnotes>'''

    from io import BytesIO
    blob = BytesIO(footnotes_part_xml.encode('utf-8'))

    reltype = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes'
    partname = PackURI('/word/footnotes.xml')

    part = Part(partname, 'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml', blob)

    doc.part.package.relate_to(part, reltype)

    print("脚注部分已添加")
except Exception as e:
    print(f"方式1失败: {e}")

doc.save('test_footnotes3.docx')
print("文档已保存")

print()
print("=== 检查保存的文档 ===")
with zipfile.ZipFile('test_footnotes3.docx', 'r') as z:
    print("ZIP中的文件:")
    found = False
    for name in z.namelist():
        if 'footnote' in name.lower():
            print(f"  ✓ {name}")
            found = True
    if not found:
        print("  ✗ 没有找到footnotes.xml")
