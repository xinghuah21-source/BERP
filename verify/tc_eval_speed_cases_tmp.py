import base64, json, urllib.request
from pathlib import Path
ROOT = Path(r'e:\game\BERP')
STANDARD = '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'

def post_ai(path: Path):
    mime = 'audio/wav' if path.suffix.lower() == '.wav' else 'audio/webm'
    payload = {'audio_base64': f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('utf-8'), 'standard_text': STANDARD, 'language': 'zh'}
    req = urllib.request.Request('http://127.0.0.1:8001/evaluate', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode('utf-8'))
slow = post_ai(ROOT / 'test_video' / 'yonge1.wav')
fast = post_ai(ROOT / 'test_video' / 'yonge2.webm')
out = {
  'TC-EVAL-05': {'file':'yonge1.wav','transcript':slow.get('transcript'),'breakdown':slow.get('breakdown'),'total_score':slow.get('total_score'),'feedback':slow.get('feedback')},
  'TC-EVAL-06': {'file':'yonge2.webm','transcript':fast.get('transcript'),'breakdown':fast.get('breakdown'),'total_score':fast.get('total_score'),'feedback':fast.get('feedback')}
}
print(json.dumps(out, ensure_ascii=False, indent=2))
