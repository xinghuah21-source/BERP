import json
from pathlib import Path

from audio_feature_extractor import AudioFeatureExtractor, _decode_audio_bytes, _load_audio_to_waveform_16k


def file_to_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "audio/wav" if suffix == ".wav" else "application/octet-stream"
    payload = path.read_bytes()
    import base64

    return f"data:{mime};base64," + base64.b64encode(payload).decode("ascii")


def run_once(model_dir: str, audio_path: Path) -> dict:
    extractor = AudioFeatureExtractor(model_id="iic/emotion2vec_base_finetuned")
    extractor.model_dir = Path(model_dir)
    data_url = file_to_data_url(audio_path)
    packet = extractor.extract_emotion_expression(data_url, standard_text="咏鹅")
    emo = packet["emotion_expression"]
    detected = emo["detected"]
    av = detected["av_raw"]
    return {
        "model_dir": model_dir,
        "labels": detected.get("labels"),
        "raw_labels": detected.get("raw_labels"),
        "inference_seconds": detected.get("inference_seconds"),
        "arousal_raw": round(av["arousal"], 4),
        "valence_raw": round(av["valence"], 4),
        "arousal_score": emo["scores"].get("arousal_score"),
        "valence_score": emo["scores"].get("valence_score"),
        "confidence_top1": round(detected["confidence"]["top1"], 4),
        "confidence_entropy": round(detected["confidence"]["entropy"], 4),
        "top1": detected.get("top1"),
        "probs": detected.get("probs"),
    }


if __name__ == "__main__":
    audio_path = Path(r"E:\game\BERP\YongE.wav")
    model_dir = r"C:\Users\26947\.cache\modelscope\hub\models\iic\emotion2vec_base_finetuned"
    print("audio_exists=", audio_path.exists())
    if audio_path.exists():
        print(json.dumps(run_once(model_dir, audio_path), ensure_ascii=False, indent=2))
