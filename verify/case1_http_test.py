import base64
import difflib
import json
import time
import urllib.request
from pathlib import Path

standard = "鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。"
audio_path = Path(r"e:\game\BERP\YongE.wav")
out_path = Path(r"e:\game\BERP\verify\case1_evaluate_response.json")
summary_path = Path(r"e:\game\BERP\verify\case1_summary.json")


def normalize(s: str) -> str:
    punct = set("，。！？；：、,.!?;:\"'“”‘’（）()《》【】[] \n\t\r")
    return ''.join(ch for ch in (s or '') if ch not in punct)


audio_b64 = "data:audio/wav;base64," + base64.b64encode(audio_path.read_bytes()).decode("utf-8")
payload = json.dumps({"audio_base64": audio_b64, "standard_text": standard, "language": "zh"}).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:8001/evaluate", data=payload, headers={"Content-Type": "application/json"}, method="POST")

t0 = time.perf_counter()
with urllib.request.urlopen(req, timeout=180) as resp:
    body = resp.read().decode("utf-8")
request_seconds = time.perf_counter() - t0
obj = json.loads(body)
out_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
transcript = obj.get("transcript", "")
similarity = difflib.SequenceMatcher(None, normalize(standard), normalize(transcript)).ratio()
summary = {
    "request_seconds": round(request_seconds, 3),
    "transcript": transcript,
    "similarity": round(similarity, 4),
    "breakdown": obj.get("breakdown"),
    "total_score": obj.get("total_score"),
    "confidence": obj.get("confidence"),
    "emotion_scores": ((obj.get("emotion_expression") or {}).get("scores") if isinstance(obj.get("emotion_expression"), dict) else None),
    "emotion_detected": ((obj.get("emotion_expression") or {}).get("detected") if isinstance(obj.get("emotion_expression"), dict) else None),
    "emotion_match": ((obj.get("emotion_expression") or {}).get("match") if isinstance(obj.get("emotion_expression"), dict) else None),
    "intelligent_feedback": obj.get("intelligent_feedback"),
    "fallback_note": obj.get("fallback_note"),
}
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
