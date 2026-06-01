import base64
import io
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import soundfile as sf
import torch
import torchaudio

from emotion_av import EMOTION_PROTOTYPES, normalize_emotion_label, probs_to_av

DEFAULT_EMOTION2VEC_PATH = Path(r"C:\Users\26947\.cache\modelscope\hub\models\iic\emotion2vec_base_finetuned")
DEFAULT_CONDA_PYTHON = Path(r"E:\ANACONDA\envs\BERP\python.exe")


def _decode_audio_bytes(audio_base64: str) -> Tuple[bytes, str]:
    payload = audio_base64
    mime = "application/octet-stream"
    if audio_base64.startswith("data:") and "," in audio_base64:
        header, payload = audio_base64.split(",", 1)
        mime = header[5:].split(";", 1)[0].strip().lower() or mime
    raw = base64.b64decode(payload or "", validate=False)
    if mime == "application/octet-stream":
        if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
            mime = "audio/wav"
    return raw, mime


def _any_audio_to_pcm16k_mono_s16le(audio_bytes: bytes, suffix: str) -> bytes:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        local_ffmpeg = Path(__file__).resolve().parent / "ffmpeg" / "ffmpeg-master-latest-win64-gpl" / "bin" / "ffmpeg.exe"
        if local_ffmpeg.exists():
            ffmpeg_bin = str(local_ffmpeg)
        else:
            ffmpeg_bin = "ffmpeg"
    fd_in, path_in = tempfile.mkstemp(suffix=suffix)
    os.write(fd_in, audio_bytes)
    os.close(fd_in)
    fd_out, path_out = tempfile.mkstemp(suffix=".pcm")
    os.close(fd_out)
    try:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            path_in,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "s16le",
            path_out,
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or b"ffmpeg failed").decode("utf-8", errors="replace"))
        with open(path_out, "rb") as f:
            return f.read()
    finally:
        for p in (path_in, path_out):
            try:
                os.remove(p)
            except Exception:
                pass


def _pcm16le_to_waveform(pcm: bytes) -> torch.Tensor:
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    return torch.from_numpy(arr)


def _load_audio_to_waveform_16k(audio_bytes: bytes, mime: str) -> torch.Tensor:
    if mime in ("audio/wav", "audio/x-wav", "audio/wave"):
        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)
        wav = torch.from_numpy(data.T)
        wav_mono = wav.mean(dim=0)
        if sr != 16000:
            wav_mono = torchaudio.functional.resample(wav_mono, sr, 16000)
        return wav_mono

    suffix = ".bin"
    if mime == "audio/webm":
        suffix = ".webm"
    elif mime == "audio/ogg":
        suffix = ".ogg"
    elif mime in ("audio/mpeg", "audio/mp3"):
        suffix = ".mp3"
    elif mime in ("audio/mp4", "video/mp4"):
        suffix = ".mp4"
    pcm = _any_audio_to_pcm16k_mono_s16le(audio_bytes, suffix=suffix)
    return _pcm16le_to_waveform(pcm)


def _guess_poem_title(standard_text: str) -> Optional[str]:
    t = (standard_text or "").strip()
    if "鹅鹅鹅" in t or "曲项向天歌" in t:
        return "咏鹅"
    if "床前明月光" in t or "疑是地上霜" in t:
        return "静夜思"
    if "君不见黄河之水天上来" in t or "人生得意须尽欢" in t:
        return "将进酒"
    return None


def _load_poem_profiles(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _style_deviation_rating(distance: float, tolerance_radius: float) -> str:
    if tolerance_radius <= 0:
        return "严重"
    ratio = distance / tolerance_radius
    if ratio <= 0.33:
        return "轻微"
    if ratio <= 0.66:
        return "中等"
    return "严重"


def _has_user_baseline(user_baseline: Optional[dict]) -> bool:
    if not isinstance(user_baseline, dict):
        return False
    try:
        arousal = float(user_baseline.get("baseline_arousal"))
        valence = float(user_baseline.get("baseline_valence"))
    except Exception:
        return False
    return 0.0 <= arousal <= 1.0 and 0.0 <= valence <= 1.0


def _calc_style_match_default(detected_av: dict, profile: dict) -> dict:
    target = profile["target"]
    tolerance_radius = max(float(profile.get("tolerance_radius", 0.4)), 0.05)
    da = float(detected_av["arousal"]) - float(target["arousal"])
    dv = float(detected_av["valence"]) - float(target["valence"])
    dist = math.sqrt((da * da) + (dv * dv))
    normalized = dist / tolerance_radius
    style = max(0.0, min(100.0, math.exp(-(normalized ** 2) * 0.8) * 100.0))
    within_tolerance = dist <= tolerance_radius

    bw = profile.get("bandwidth") or {}
    in_band = False
    if bw:
        in_band = (
            float(bw["arousal_min"]) <= float(detected_av["arousal"]) <= float(bw["arousal_max"])
            and float(bw["valence_min"]) <= float(detected_av["valence"]) <= float(bw["valence_max"])
        )
    return {
        "calibration_mode": "default",
        "style_match": int(round(style)),
        "in_target_bandwidth": bool(in_band),
        "within_tolerance": bool(within_tolerance),
        "distance_from_target": round(dist, 3),
        "target_center_distance": round(dist, 3),
        "tolerance_radius": round(tolerance_radius, 3),
        "normalized_distance": round(normalized, 3),
        "style_deviation_rating": _style_deviation_rating(dist, tolerance_radius),
    }


def _calc_style_match_baseline(detected_av: dict, profile: dict, user_baseline: dict) -> dict:
    baseline_arousal = float(user_baseline["baseline_arousal"])
    baseline_valence = float(user_baseline["baseline_valence"])
    target = profile["target"]

    student_offset_a = float(detected_av["arousal"]) - baseline_arousal
    student_offset_v = float(detected_av["valence"]) - baseline_valence
    target_offset_a = float(target["arousal"]) - 0.5
    target_offset_v = float(target["valence"]) - 0.5

    da = student_offset_a - target_offset_a
    dv = student_offset_v - target_offset_v
    dist = math.sqrt((da * da) + (dv * dv))
    max_distance = math.sqrt(2.0)
    style = max(0.0, min(100.0, (1.0 - (dist / max_distance)) * 100.0))

    bw = profile.get("bandwidth") or {}
    in_band = False
    offset_bandwidth = None
    if bw:
        offset_bandwidth = {
            "arousal_min": round(float(bw["arousal_min"]) - 0.5, 3),
            "arousal_max": round(float(bw["arousal_max"]) - 0.5, 3),
            "valence_min": round(float(bw["valence_min"]) - 0.5, 3),
            "valence_max": round(float(bw["valence_max"]) - 0.5, 3),
        }
        in_band = (
            float(offset_bandwidth["arousal_min"]) <= student_offset_a <= float(offset_bandwidth["arousal_max"])
            and float(offset_bandwidth["valence_min"]) <= student_offset_v <= float(offset_bandwidth["valence_max"])
        )

    return {
        "calibration_mode": "baseline",
        "style_match": int(round(style)),
        "in_target_bandwidth": bool(in_band),
        "within_tolerance": bool(in_band),
        "distance_from_target": round(dist, 3),
        "target_center_distance": round(dist, 3),
        "tolerance_radius": round(max_distance, 3),
        "style_deviation_rating": _style_deviation_rating(dist, max_distance),
        "baseline_av_raw": {"arousal": round(baseline_arousal, 3), "valence": round(baseline_valence, 3)},
        "student_offset": {"arousal": round(student_offset_a, 3), "valence": round(student_offset_v, 3)},
        "target_offset": {"arousal": round(target_offset_a, 3), "valence": round(target_offset_v, 3)},
        "offset_bandwidth": offset_bandwidth,
    }


def _calc_style_match(detected_av: dict, profile: dict, user_baseline: Optional[dict] = None) -> dict:
    if _has_user_baseline(user_baseline):
        return _calc_style_match_baseline(detected_av, profile, user_baseline or {})
    return _calc_style_match_default(detected_av, profile)


def _calc_stability(trajectory: list[dict]) -> dict:
    if len(trajectory) < 2:
        return {"stability": 50, "trajectory": trajectory, "segmentation": {"method": "fixed_window", "window_s": 2.0}}
    deltas = []
    for i in range(1, len(trajectory)):
        da = abs(float(trajectory[i]["arousal"]) - float(trajectory[i - 1]["arousal"]))
        dv = abs(float(trajectory[i]["valence"]) - float(trajectory[i - 1]["valence"]))
        deltas.append(da + dv)
    avg_delta = float(sum(deltas) / max(1, len(deltas)))
    stability = max(0.0, min(100.0, 100.0 - 200.0 * avg_delta))
    return {"stability": int(round(stability)), "trajectory": trajectory, "segmentation": {"method": "fixed_window", "window_s": 2.0}}


def _compute_audio_quality(wav_16k: torch.Tensor) -> dict:
    duration_s = float(wav_16k.numel() / 16000.0)
    if wav_16k.numel() == 0:
        return {
            "duration_seconds": 0.0,
            "duration_valid": False,
            "speech_ratio": 0.0,
            "snr_db": 0.0,
            "noise_level": "unknown",
        }

    x = wav_16k.detach().cpu().numpy().astype(np.float32)
    frame = 480
    hop = 240
    if x.shape[0] < frame:
        rms = float(np.sqrt(np.mean(x * x) + 1e-12))
        snr_db = 0.0
        speech_ratio = 1.0 if rms > 0.02 else 0.0
        duration_valid = bool(duration_s >= 1.5 and speech_ratio >= 0.2)
        return {
            "duration_seconds": round(duration_s, 3),
            "duration_valid": duration_valid,
            "speech_ratio": round(float(speech_ratio), 3),
            "snr_db": round(float(snr_db), 2),
            "noise_level": "unknown",
        }

    rms_list = []
    for start in range(0, x.shape[0] - frame + 1, hop):
        w = x[start : start + frame]
        rms_list.append(float(np.sqrt(np.mean(w * w) + 1e-12)))
    rms_arr = np.asarray(rms_list, dtype=np.float32)

    noise_thr = float(np.quantile(rms_arr, 0.2))
    noise_frames = rms_arr[rms_arr <= noise_thr]
    noise_rms = float(np.mean(noise_frames)) if noise_frames.size else float(np.mean(rms_arr))

    speech_thr = max(noise_rms * 3.0, 0.02)
    speech_frames = rms_arr[rms_arr >= speech_thr]
    speech_ratio = float(speech_frames.size / max(1, rms_arr.size))

    speech_rms = float(np.mean(speech_frames)) if speech_frames.size else float(np.mean(rms_arr))
    snr_db = 20.0 * math.log10((speech_rms + 1e-6) / (noise_rms + 1e-6))

    if snr_db >= 20:
        noise_level = "low"
    elif snr_db >= 10:
        noise_level = "medium"
    elif snr_db >= 3:
        noise_level = "high"
    else:
        noise_level = "unknown"

    duration_valid = bool(duration_s >= 1.5 and speech_ratio >= 0.2)
    return {
        "duration_seconds": round(duration_s, 3),
        "duration_valid": duration_valid,
        "speech_ratio": round(float(speech_ratio), 3),
        "snr_db": round(float(snr_db), 2),
        "noise_level": noise_level,
    }


def _status_by_target(value: float, bw: Optional[dict], target: Optional[float]) -> str:
    if bw:
        if value < float(bw.get("arousal_min", bw.get("valence_min", 0.0))):
            return "偏低"
        if value > float(bw.get("arousal_max", bw.get("valence_max", 1.0))):
            return "偏高"
        return "正常"
    if target is None:
        return "未知"
    if value < target - 0.08:
        return "偏低"
    if value > target + 0.08:
        return "偏高"
    return "正常"


class AudioFeatureExtractor:
    def __init__(
        self,
        model_id: str = "iic/emotion2vec_base_finetuned",
        base_dir: Optional[Path] = None,
        poem_profiles_path: Optional[Path] = None,
    ) -> None:
        self.model_id = model_id
        repo_root = (base_dir or Path(__file__).resolve().parent).resolve()
        self.default_model_dir = repo_root / ".modelscope_models" / model_id.replace("/", "__")
        self.model_dir = Path(os.getenv("EMOTION2VEC_MODEL_DIR", str(DEFAULT_EMOTION2VEC_PATH))).resolve()
        self.conda_python = Path(os.getenv("EMOTION2VEC_CONDA_PYTHON", str(DEFAULT_CONDA_PYTHON))).resolve()
        self.infer_script = (Path(__file__).resolve().parent / "emotion2vec_infer.py").resolve()
        self.poem_profiles_path = poem_profiles_path or (Path(__file__).resolve().parent / "poem_emotion_profiles.json")
        self._poem_profiles = _load_poem_profiles(self.poem_profiles_path)

    def _ensure_infer_runtime(self) -> None:
        if not self.model_dir.exists():
            fallback_dir = self.default_model_dir
            if fallback_dir.exists():
                self.model_dir = fallback_dir
            else:
                raise FileNotFoundError(f"emotion2vec model dir not found: {self.model_dir}")
        if not self.conda_python.exists():
            raise FileNotFoundError(f"emotion2vec conda python not found: {self.conda_python}")
        if not self.infer_script.exists():
            raise FileNotFoundError(f"emotion2vec infer script not found: {self.infer_script}")

    def _predict_from_input(self, model_input: Any) -> dict:
        self._ensure_infer_runtime()
        t0 = time.perf_counter()
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["EMOTION2VEC_MODEL_DIR"] = str(self.model_dir)
        cmd = [str(self.conda_python), str(self.infer_script), str(model_input)]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            env=env,
            check=False,
        )
        infer_s = time.perf_counter() - t0

        stdout_lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
        stderr_text = (proc.stderr or "").strip()
        if proc.returncode != 0:
            detail = stderr_text or (stdout_lines[-1] if stdout_lines else "unknown error")
            raise RuntimeError(f"emotion2vec_subprocess_failed: {detail}")
        if not stdout_lines:
            raise RuntimeError("emotion2vec_subprocess_empty_output")

        try:
            item = json.loads(stdout_lines[-1])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"emotion2vec_invalid_json: {exc}") from exc

        if not isinstance(item, dict):
            raise RuntimeError(f"emotion2vec_invalid_output: {type(item)}")
        if not item.get("success", False):
            raise RuntimeError(f"emotion2vec_subprocess_error: {item.get('error')}")

        labels = item.get("labels") or []
        scores = item.get("scores") or []
        if not labels or not scores or len(labels) != len(scores):
            raise RuntimeError(f"emotion2vec_missing_scores: {item}")

        prob_map = {}
        items = []
        for idx, (label, score) in enumerate(zip(labels, scores)):
            label_text = str(label)
            norm_label = normalize_emotion_label(label_text)
            prob = float(score)
            prob_map[norm_label] = prob_map.get(norm_label, 0.0) + prob
            items.append({"id": idx, "label": norm_label, "raw_label": label_text, "prob": prob})
        items.sort(key=lambda x: x["prob"], reverse=True)

        av = probs_to_av(prob_map)
        top1 = items[0] if items else {"label": "UNKNOWN", "raw_label": "<unk>", "prob": 0.0}
        return {
            "labels": [it["label"] for it in items],
            "raw_labels": [it["raw_label"] for it in items],
            "probs": prob_map,
            "top1": {"label": top1["label"], "raw_label": top1["raw_label"], "prob": float(top1["prob"])},
            "av_raw": {"arousal": float(av["arousal"]), "valence": float(av["valence"])},
            "confidence": {"top1": float(av["confidence_top1"]), "entropy": float(av["confidence_entropy"])},
            "inference_seconds": round(float(infer_s), 3),
            "model": {"provider": "funasr-subprocess", "repo_id": self.model_id, "path": str(self.model_dir), "conda_python": str(self.conda_python)},
        }

    def predict_emotion(self, wav_16k: torch.Tensor) -> dict:
        fd_wav, path_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd_wav)
        try:
            sf.write(path_wav, wav_16k.detach().cpu().numpy(), 16000)
            return self._predict_from_input(path_wav)
        finally:
            try:
                os.remove(path_wav)
            except Exception:
                pass

    def extract_emotion_expression(
        self,
        audio_base64: str,
        standard_text: str,
        poem_title: Optional[str] = None,
        poem_profile: Optional[str] = None,
        compute_trajectory: bool = False,
        user_baseline: Optional[dict] = None,
    ) -> Dict[str, Any]:
        raw, mime = _decode_audio_bytes(audio_base64)
        wav = _load_audio_to_waveform_16k(raw, mime)
        audio_quality = _compute_audio_quality(wav)
        duration_s = float(audio_quality["duration_seconds"])
        duration_valid = bool(audio_quality["duration_valid"])

        detected = self.predict_emotion(wav)
        av = detected["av_raw"]
        scores = {
            "arousal_score": int(round(float(av["arousal"]) * 100)),
            "valence_score": int(round(float(av["valence"]) * 100)),
        }

        title = poem_title or _guess_poem_title(standard_text)
        target_obj = None
        match_obj = None
        if title:
            poem_profiles = (self._poem_profiles.get("poem_profiles") or {}).get(title)
            if poem_profiles:
                p_name = poem_profile or poem_profiles.get("default")
                prof = (poem_profiles.get("profiles") or {}).get(p_name) if p_name else None
                if prof:
                    target_obj = {
                        "poem_title": title,
                        "profile": p_name,
                        "tags": prof.get("tags") or [],
                        "target_av_raw": {"arousal": float(prof["target"]["arousal"]), "valence": float(prof["target"]["valence"])},
                        "tolerance": prof.get("tolerance") or {},
                        "bandwidth": prof.get("bandwidth") or {},
                    }
                    match_obj = _calc_style_match(av, prof, user_baseline=user_baseline)
                    scores["style_match"] = int(match_obj["style_match"])

        stability_obj = None
        if compute_trajectory:
            trajectory = []
            window_s = 2.0
            step = int(window_s * 16000)
            max_segments = 4
            if duration_s >= 4.0:
                for idx, start in enumerate(range(0, int(wav.numel()), step)):
                    if idx >= max_segments:
                        break
                    end = min(int(wav.numel()), start + step)
                    seg = wav[start:end]
                    if seg.numel() < int(0.5 * 16000):
                        continue
                    d = self.predict_emotion(seg)
                    trajectory.append(
                        {
                            "time_start": round(start / 16000.0, 3),
                            "time_end": round(end / 16000.0, 3),
                            "arousal": float(d["av_raw"]["arousal"]),
                            "valence": float(d["av_raw"]["valence"]),
                        }
                    )
            stability_obj = _calc_stability(trajectory) if trajectory else None
        if stability_obj:
            scores["stability"] = int(stability_obj["stability"])

        base_weight = 0.15
        eff = base_weight
        eff *= min(1.0, float(detected["confidence"]["top1"]) / 0.6) if duration_valid else 0.3
        weights_used = {"emotion_in_total": base_weight, "effective_emotion_weight": round(eff, 4)}

        bw_a = None
        bw_v = None
        target_a = None
        target_v = None
        if target_obj:
            bw = target_obj.get("bandwidth") or {}
            bw_a = {"arousal_min": bw.get("arousal_min"), "arousal_max": bw.get("arousal_max")}
            bw_v = {"valence_min": bw.get("valence_min"), "valence_max": bw.get("valence_max")}
            target_a = float(target_obj["target_av_raw"]["arousal"])
            target_v = float(target_obj["target_av_raw"]["valence"])

        ar_status = _status_by_target(float(av["arousal"]), bw_a, target_a)
        va_status = _status_by_target(float(av["valence"]), bw_v, target_v)
        fb = {
            "arousal_status": ar_status,
            "valence_status": va_status,
            "confidence_note": "不稳定" if float(detected["confidence"]["top1"]) < 0.5 else "稳定",
        }
        if match_obj:
            style_match = int(match_obj["style_match"])
            if style_match >= 80:
                fb["style_gap"] = "匹配良好"
            elif style_match >= 60:
                fb["style_gap"] = "存在轻微偏差"
            elif style_match < 30:
                fb["style_gap"] = "情感表达与诗歌意境不符"
            else:
                fb["style_gap"] = "情感有偏差"
        if stability_obj:
            fb["stability_status"] = "情绪起伏过大" if int(stability_obj["stability"]) < 50 else "情绪较稳定"

        return {
            "schema_version": "1.0",
            "pipeline_versions": {"emotion_model": self.model_id, "emotion_mapping_keys": sorted(EMOTION_PROTOTYPES.keys())},
            "emotion_expression": {
                "scores": scores,
                "detected": detected,
                "target": target_obj,
                "match": match_obj,
                "stability": stability_obj,
                "audio_quality": audio_quality,
                "weights_used": weights_used,
                "feedback_rules": fb,
                "calibration": {
                    "mode": "baseline" if _has_user_baseline(user_baseline) else "default",
                    "user_baseline": user_baseline if _has_user_baseline(user_baseline) else None,
                },
            },
        }
