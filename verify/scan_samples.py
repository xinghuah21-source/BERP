import base64, json, urllib.request
from pathlib import Path

samples = [
    (r'e:\game\BERP\YongE.wav', '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'),
    (r'e:\game\BERP\test_video\yonge1.wav', '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'),
    (r'e:\game\BERP\test_video\yonge2.webm', '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'),
    (r'e:\game\BERP\test_video\yonge3.webm', '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'),
    (r'e:\game\BERP\jingyesi.wav', '床前明月光，疑是地上霜。举头望明月，低头思故乡。'),
    (r'e:\game\BERP\test_video\jingyesi1.wav', '床前明月光，疑是地上霜。举头望明月，低头思故乡。'),
    (r'e:\game\BERP\test_video\jingyesi2.webm', '床前明月光，疑是地上霜。举头望明月，低头思故乡。'),
    (r'e:\game\BERP\test_video\jingyesi3.webm', '床前明月光，疑是地上霜。举头望明月，低头思故乡。'),
]
rows = []
for path_str, standard in samples:
    path = Path(path_str)
    mime = 'audio/wav' if path.suffix.lower()=='.wav' else 'audio/webm'
    payload = {
        'audio_base64': f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('utf-8'),
        'standard_text': standard,
        'language': 'zh',
    }
    req = urllib.request.Request('http://127.0.0.1:8001/evaluate', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=180) as resp:
        obj = json.loads(resp.read().decode('utf-8'))
    rows.append({
        'file': path.name,
        'total': obj.get('total_score'),
        'breakdown': obj.get('breakdown'),
        'transcript': obj.get('transcript'),
        'feedback': obj.get('feedback'),
    })
print(json.dumps(rows, ensure_ascii=False, indent=2))
Path(r'e:\game\BERP\verify\sample_scan.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
