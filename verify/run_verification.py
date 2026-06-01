import base64
import json
import math
import time
import wave
from pathlib import Path

import requests


BASE = "http://127.0.0.1"


def post_ai_evaluate(audio_b64: str, standard_text: str, timeout: float = 120.0) -> dict:
    payload = {"audio_base64": audio_b64, "standard_text": standard_text, "language": "zh"}
    r = requests.post(f"{BASE}/ai/evaluate", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def wav_to_data_url(path: Path) -> str:
    return "data:audio/wav;base64," + base64.b64encode(path.read_bytes()).decode("utf-8")


def make_silence_wav(seconds: float, sr: int = 16000) -> str:
    tmp = Path(__file__).resolve().parent / "_silence.wav"
    n = int(seconds * sr)
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * n)
    return wav_to_data_url(tmp)


def calc_style_match(detected_av: dict, target: dict, tol: dict) -> float:
    da = (detected_av["arousal"] - target["arousal"]) / max(tol.get("sigma_arousal", 0.2), 0.05)
    dv = (detected_av["valence"] - target["valence"]) / max(tol.get("sigma_valence", 0.2), 0.05)
    dist = math.sqrt(da * da + dv * dv)
    return 100.0 * math.exp(-(dist * dist))


def case1_standard_flow() -> None:
    audio_path = Path(r"E:\game\BERP\YongE.wav")
    standard = "鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。"
    t0 = time.perf_counter()
    obj = post_ai_evaluate(wav_to_data_url(audio_path), standard)
    dt = time.perf_counter() - t0
    print("CASE1 request_seconds=", round(dt, 3))
    print("CASE1 transcript=", obj.get("transcript"))
    print("CASE1 breakdown=", obj.get("breakdown"))
    emo = obj.get("emotion_expression") or {}
    print("CASE1 emotion_scores=", (emo.get("scores") if isinstance(emo, dict) else None))
    print("CASE1 intelligent_feedback_is_none=", obj.get("intelligent_feedback") is None)
    if isinstance(obj.get("intelligent_feedback"), dict):
        print("CASE1 intelligent_overall_comment=", obj["intelligent_feedback"].get("overall_comment"))


def case2_omission_scoring_unit() -> None:
    from ai_engine_local_scoring import score_text_only

    standard = "床前明月光，疑是地上霜。举头望明月，低头思故乡。"
    transcript = "床前明月光，疑是地上霜"
    out = score_text_only(standard_text=standard, transcript=transcript)
    print("CASE2 transcript=", transcript)
    print("CASE2 breakdown=", out["breakdown"])
    print("CASE2 omission_head=", out["error_details"][0] if out["error_details"] else None)


def case3_emotion_mismatch_unit() -> None:
    profiles = json.load(open(r"E:\game\BERP\ai-engine\poem_emotion_profiles.json", encoding="utf-8"))
    prof = profiles["poem_profiles"]["静夜思"]["profiles"]["内敛型"]
    target = prof["target"]
    tol = prof["tolerance"]
    detected = {"arousal": 0.85, "valence": 0.75}
    style = calc_style_match(detected, target, tol)
    print("CASE3 detected_av=", detected)
    print("CASE3 target_av=", target)
    print("CASE3 style_match_score=", int(round(style)))


def case4_audio_quality_silence() -> None:
    standard = "鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。"
    audio_b64 = make_silence_wav(3.0)
    obj = post_ai_evaluate(audio_b64, standard)
    emo = obj.get("emotion_expression") or {}
    aq = (emo.get("audio_quality") or {}) if isinstance(emo, dict) else {}
    print("CASE4 transcript_len=", len(obj.get("transcript") or ""))
    print("CASE4 audio_quality=", aq)
    print("CASE4 emotion_confidence=", ((emo.get("detected") or {}).get("confidence") if isinstance(emo, dict) else None))


if __name__ == "__main__":
    for url in ["/api/health", "/ai/health", "/ws/health"]:
        r = requests.get(BASE + url, timeout=10)
        print("HEALTH", url, r.status_code, r.text)

    case1_standard_flow()
    case2_omission_scoring_unit()
    case3_emotion_mismatch_unit()
    case4_audio_quality_silence()
