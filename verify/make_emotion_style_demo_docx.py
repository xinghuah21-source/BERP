import json, math, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(r'e:\game\BERP')
out_path = ROOT / '情感风格匹配示意表_非实测.docx'
json_path = ROOT / 'verify' / 'emotion_style_demo_results.json'

profiles = {
    '咏鹅': {
        'profile': '童趣型',
        'target': (0.62, 0.70),
        'radius': 0.55,
        'band': {'arousal_min': 0.40, 'arousal_max': 0.85, 'valence_min': 0.45, 'valence_max': 0.90},
    },
    '静夜思': {
        'profile': '内敛型',
        'target': (0.30, 0.25),
        'radius': 0.40,
        'band': {'arousal_min': 0.15, 'arousal_max': 0.45, 'valence_min': 0.10, 'valence_max': 0.40},
    },
}

samples = [
    ('咏鹅', '匹配样本', (0.74, 0.68)),
    ('咏鹅', '背离样本', (0.25, 0.30)),
    ('咏鹅', '中性样本', (0.50, 0.50)),
    ('静夜思', '匹配样本', (0.33, 0.22)),
    ('静夜思', '背离样本', (0.76, 0.72)),
    ('静夜思', '中性样本', (0.43, 0.34)),
]

def deviation(distance, radius):
    ratio = distance / radius if radius > 0 else 999
    if ratio <= 0.33:
        return '轻微'
    if ratio <= 0.66:
        return '中等'
    return '严重'

rows = []
for poem, sample_type, det in samples:
    p = profiles[poem]
    ta, tv = p['target']
    da = det[0] - ta
    dv = det[1] - tv
    dist = math.sqrt(da*da + dv*dv)
    norm = dist / p['radius']
    style = max(0.0, min(100.0, math.exp(-(norm ** 2) * 0.8) * 100.0))
    band = p['band']
    in_band = band['arousal_min'] <= det[0] <= band['arousal_max'] and band['valence_min'] <= det[1] <= band['valence_max']
    rows.append({
        'poem': poem,
        'profile': p['profile'],
        'target_arousal': ta,
        'target_valence': tv,
        'band': band,
        'sample_type': sample_type,
        'detected_arousal': round(det[0], 4),
        'detected_valence': round(det[1], 4),
        'distance': round(dist, 3),
        'in_band': in_band,
        'deviation_rating': deviation(dist, p['radius']),
        'style_match': int(round(style)),
    })

json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')

headers = ['诗歌', '情感配置（目标区间）', '样本类型', '检测值（arousal, valence）', '与目标中心距离', '是否在容差带宽内', '实际风格偏差评级', '风格匹配度']
widths = [900, 3200, 1400, 1900, 1300, 1600, 1500, 1200]

def xml_text_runs(text: str, bold: bool=False):
    parts = str(text).split('\n')
    out = []
    for idx, part in enumerate(parts):
        rpr = '<w:rPr><w:b/></w:rPr>' if bold else ''
        out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{escape(part)}</w:t></w:r>')
        if idx != len(parts) - 1:
            out.append('<w:r><w:br/></w:r>')
    return ''.join(out)

def cell(text, width=None, bold=False):
    tc_pr = f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>' if width else ''
    return f'<w:tc>{tc_pr}<w:p>{xml_text_runs(text, bold)}</w:p></w:tc>'

trs = []
trs.append('<w:tr>' + ''.join(cell(h, widths[i], True) for i, h in enumerate(headers)) + '</w:tr>')
for r in rows:
    config = f"{r['profile']}\ntarget=({r['target_arousal']:.2f}, {r['target_valence']:.2f})\nA[{r['band']['arousal_min']:.2f}, {r['band']['arousal_max']:.2f}]\nV[{r['band']['valence_min']:.2f}, {r['band']['valence_max']:.2f}]"
    row = [
        r['poem'],
        config,
        r['sample_type'],
        f"({r['detected_arousal']:.4f}, {r['detected_valence']:.4f})",
        f"{r['distance']:.3f}",
        '是' if r['in_band'] else '否',
        r['deviation_rating'],
        f"{r['style_match']}"
    ]
    trs.append('<w:tr>' + ''.join(cell(row[i], widths[i]) for i in range(len(headers))) + '</w:tr>')

tbl = (
    '<w:tbl>'
    '<w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/>'
    '<w:tblBorders>'
    '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:left w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:right w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:insideH w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '<w:insideV w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
    '</w:tblBorders></w:tblPr>'
    '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths) + '</w:tblGrid>' + ''.join(trs) + '</w:tbl>'
)

notes = [
    '说明：本表为示意数据，非实际测试结果，仅用于论文展示算法预期效果。',
    '目标区间依据当前项目中的诗歌情感画像配置设定。',
    '风格匹配度按当前项目公式计算：style_match = exp(-(normalized_distance^2)*0.8) * 100。',
]
notes_xml = ''.join(f'<w:p><w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>' for line in notes)

document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" xmlns:wne="http://schemas.microsoft.com/office/2006/wordml" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" mc:Ignorable="w14 wp14">
  <w:body>
    <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr><w:t>情感风格匹配示意表（非实测）</w:t></w:r></w:p>
    {tbl}
    <w:p/>
    {notes_xml}
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
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>情感风格匹配示意表（非实测）</dc:title><dc:creator>GPT-5.4</dc:creator><cp:lastModifiedBy>GPT-5.4</cp:lastModifiedBy></cp:coreProperties>'''
app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Office Word</Application></Properties>'''
styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="table" w:default="1" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style></w:styles>'''

with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('[Content_Types].xml', content_types)
    zf.writestr('_rels/.rels', rels)
    zf.writestr('docProps/core.xml', core)
    zf.writestr('docProps/app.xml', app)
    zf.writestr('word/document.xml', document_xml)
    zf.writestr('word/styles.xml', styles)

print(str(out_path))
