import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, r'e:\game\BERP\ai-engine')
import evaluator as ev

samples = [
    (Path(r'e:\game\BERP\YongE.wav'), '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'),
    (Path(r'e:\game\BERP\test_video\yonge1.wav'), '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'),
]
rows = []
for path, standard in samples:
    audio_b64 = 'data:audio/wav;base64,' + base64.b64encode(path.read_bytes()).decode('utf-8')
    pcm = ev._audio_base64_to_pcm16k(audio_b64)
    e = ev.Evaluator()
    asr = e.transcribe(audio_b64)
    raw = (asr.transcript or '').strip()
    cleaned = ev.clean_transcript(raw, standard)
    fluency, features = ev._compute_fluency_score(
        pcm_bytes=pcm,
        raw_transcript=raw,
        cleaned_transcript=cleaned,
        standard_text=standard,
        duration=max(float(asr.duration or 0.0),0.1),
    )
    rows.append({
        'file': path.name,
        'duration': round(float(asr.duration or 0.0),3),
        'raw_transcript': raw,
        'cleaned': cleaned,
        'fluency': fluency,
        'features': features,
    })
print(json.dumps(rows, ensure_ascii=False, indent=2))
