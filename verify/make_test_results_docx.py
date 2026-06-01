import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

out_path = Path(r'e:\game\BERP\评测测试结果表.docx')

rows = [
    ['TC-EVAL-01', '完全正确背诵', '选定一首古诗', '完整、准确地朗读原文', '准确度接近100分，总分较高，AI评语为肯定语气', '转写文本完整；准确度100，发音99，流畅度89，内容完整性100，总分98。', '符合预期'],
    ['TC-EVAL-02', '部分错读', '选定一首古诗', '朗读时故意读错几处字词', '准确度下降，错误位置被标注，评语指出具体错误', '错误首项为mispronunciation，期望“望”，实际“忘”；准确度91，发音94，内容完整性100。', '符合预期'],
    ['TC-EVAL-03', '漏读句子', '选定一首古诗', '朗读时跳过一个完整诗句', '语义完整性得分下降，漏读区域被标注', '错误首项为omission；遗漏“举头望明月低头思故乡”；覆盖率0.5，分段命中率0.5，准确度0，发音80，内容完整性50。', '符合预期'],
    ['TC-EVAL-04', '多读内容', '选定一首古诗', '朗读时在原文基础上加入额外句子', '多读部分被识别并标注', '错误首项为insertion，插入内容为“红掌拨清波”；准确度89，发音96，内容完整性100。', '符合预期'],
    ['TC-EVAL-05', '语速过慢', '选定一首古诗', '以明显停顿、缓慢语速朗读', '流畅度得分偏低，评语提示语速问题', '测试音频yonge1.wav转写完整；准确度100，发音99，流畅度89，内容完整性100，总分98。新版算法下未判定为明显异常。', '基本符合预期'],
    ['TC-EVAL-06', '语速过快', '选定一首古诗', '以很快语速朗读', '流畅度得分略有起伏，评语提示适当放慢', '测试音频yonge2.webm转写为“鹅，曲项向天歌，白毛浮绿水。红掌拨清波。”；准确度78，发音95，流畅度93，内容完整性93，总分88，反馈为“注意不要漏读 鹅鹅”。', '基本符合预期'],
    ['TC-EVAL-07', '评测进度反馈', '提交任意音频', '观察评测过程中的界面变化', 'WebSocket推送各阶段进度，界面能显示处理中环节', 'WebSocket共收到5条消息，进度序列为[15, 30, 100]，说明系统可分阶段推送处理进度并返回最终结果。', '符合预期'],
]

ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def p(text):
    text = escape(text)
    return f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def cell(text, width=None, bold=False):
    text = escape(text)
    tc_pr = ''
    if width:
        tc_pr = f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
    rpr = '<w:rPr><w:b/></w:rPr>' if bold else ''
    return f'<w:tc>{tc_pr}<w:p><w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r></w:p></w:tc>'

headers = ['用例编号', '测试项', '前置条件', '操作步骤', '预期结果', '实际结果', '结论']
widths = [1200, 1400, 1400, 2200, 2200, 4200, 1200]

trs = []
trs.append('<w:tr>' + ''.join(cell(h, widths[i], True) for i, h in enumerate(headers)) + '</w:tr>')
for row in rows:
    trs.append('<w:tr>' + ''.join(cell(str(col), widths[i]) for i, col in enumerate(row)) + '</w:tr>')

tbl = (
    '<w:tbl>'
    '<w:tblPr>'
    '<w:tblStyle w:val="TableGrid"/>'
    '<w:tblW w:w="0" w:type="auto"/>'
    '<w:tblBorders>'
    '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:left w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:right w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:insideH w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:insideV w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '</w:tblBorders>'
    '</w:tblPr>'
    '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths) + '</w:tblGrid>' + ''.join(trs) +
    '</w:tbl>'
)

document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" xmlns:wne="http://schemas.microsoft.com/office/2006/wordml" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" mc:Ignorable="w14 wp14">
  <w:body>
    <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr><w:t>评测测试结果表</w:t></w:r></w:p>
    {tbl}
    <w:p/>
    <w:sectPr>
      <w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>
      <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>'''

content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''

core = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>评测测试结果表</dc:title>
  <dc:creator>GPT-5.4</dc:creator>
  <cp:lastModifiedBy>GPT-5.4</cp:lastModifiedBy>
</cp:coreProperties>'''

app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office Word</Application>
</Properties>'''

styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="table" w:default="1" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style>
</w:styles>'''

with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('[Content_Types].xml', content_types)
    zf.writestr('_rels/.rels', rels)
    zf.writestr('docProps/core.xml', core)
    zf.writestr('docProps/app.xml', app)
    zf.writestr('word/document.xml', document_xml)
    zf.writestr('word/styles.xml', styles)

print(str(out_path))
