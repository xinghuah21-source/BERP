import json
import io
import os
import shutil
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


MODEL_DIR = Path(r"C:\Users\26947\.cache\modelscope\hub\models\iic\emotion2vec_base_finetuned")
MODEL_REPO_ID = "iic/emotion2vec_base_finetuned"
MODEL_CACHE_DIR = Path.home() / ".cache" / "modelscope" / "hub" / "models" / "iic" / "emotion2vec_base_finetuned"
LOCAL_FFMPEG = Path(__file__).resolve().parent / "ffmpeg" / "ffmpeg-master-latest-win64-gpl" / "bin"


def _ensure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _load_model():
    from funasr import AutoModel

    if not MODEL_DIR.exists():
        raise FileNotFoundError(f"emotion2vec model dir not found: {MODEL_DIR}")
    if not MODEL_CACHE_DIR.exists():
        MODEL_CACHE_DIR.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(MODEL_DIR, MODEL_CACHE_DIR)
    return AutoModel(model=MODEL_REPO_ID, disable_update=True)


def _ensure_ffmpeg_on_path() -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return
    if LOCAL_FFMPEG.exists():
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(LOCAL_FFMPEG) + os.pathsep + current_path


def main() -> int:
    _ensure_utf8_stdio()
    _ensure_ffmpeg_on_path()

    if len(sys.argv) != 2:
        print(json.dumps({"success": False, "error": "usage: python emotion2vec_infer.py <wav_path>"}, ensure_ascii=False))
        return 2

    wav_path = Path(sys.argv[1]).resolve()
    if not wav_path.exists():
        print(json.dumps({"success": False, "error": f"audio file not found: {wav_path}"}, ensure_ascii=False))
        return 3

    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            model = _load_model()
            result = model.generate(str(wav_path), output_dir=None, granularity="utterance", extract_embedding=False)
        item = result[0] if isinstance(result, list) and result else result
        if not isinstance(item, dict):
            raise RuntimeError(f"emotion2vec_invalid_output: {type(item)}")

        labels = item.get("labels") or []
        scores = item.get("scores") or []
        if not labels or not scores or len(labels) != len(scores):
            raise RuntimeError(f"emotion2vec_missing_scores: {item}")

        payload = {
            "success": True,
            "wav_path": str(wav_path),
            "model_dir": str(MODEL_DIR),
            "labels": labels,
            "scores": scores,
            "raw_result": item,
        }
        print(json.dumps(payload, ensure_ascii=True))
        return 0
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
