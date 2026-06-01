import base64, json, time, urllib.request
from pathlib import Path
ROOT = Path(r'e:\game\BERP')
audio = ROOT / 'YongE.wav'
standard = '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'
payload = {
  'audio_base64': 'data:audio/wav;base64,' + base64.b64encode(audio.read_bytes()).decode('utf-8'),
  'standard_text': standard,
  'language': 'zh'
}
t0 = time.perf_counter()
req = urllib.request.Request('http://127.0.0.1:8001/evaluate', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=180) as resp:
    obj = json.loads(resp.read().decode('utf-8'))
elapsed = round(time.perf_counter() - t0, 3)
out = {'request_seconds': elapsed, 'response': obj}
path = ROOT / 'verify' / 'ai_comment_showcase_actual.json'
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=2))
