import json
import wave
import urllib.request
from pathlib import Path

standard = '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'
base = Path(r'e:\game\BERP\verify')
base.mkdir(parents=True, exist_ok=True)
silence_wav = base / 'case4_silence.wav'
out_json = base / 'case4_response.json'
summary_json = base / 'case4_summary.json'

sr = 16000
seconds = 3
n = sr * seconds
with wave.open(str(silence_wav), 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sr)
    wf.writeframes(b'\x00\x00' * n)

import base64
payload = {
    'audio_base64': 'data:audio/wav;base64,' + base64.b64encode(silence_wav.read_bytes()).decode('utf-8'),
    'standard_text': standard,
    'language': 'zh',
}
req = urllib.request.Request(
    'http://127.0.0.1:8001/evaluate',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
with urllib.request.urlopen(req, timeout=180) as resp:
    obj = json.loads(resp.read().decode('utf-8'))

out_json.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
emo = obj.get('emotion_expression') or {}
aq = emo.get('audio_quality') or {}
detected = emo.get('detected') or {}
feedback_rules = emo.get('feedback_rules') or {}
summary = {
    'transcript': obj.get('transcript'),
    'transcript_len': len(obj.get('transcript') or ''),
    'breakdown': obj.get('breakdown'),
    'total_score': obj.get('total_score'),
    'feedback': obj.get('feedback'),
    'fallback_note': obj.get('fallback_note'),
    'audio_quality': aq,
    'emotion_confidence': detected.get('confidence'),
    'emotion_top1': detected.get('top1'),
    'feedback_rules': feedback_rules,
}
summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
