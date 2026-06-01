import base64
import difflib
import io
import json
import os
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path
import shutil
import traceback
from typing import Any, Dict, List, Optional, Tuple

from xunfei_client import XunfeiAsrResult, transcribe_pcm

PUNCTUATION_CHARS = "，。！？；：、,.!?;:\"'“”‘’（）()《》【】[]"


def _extract_comparison_units(s: str) -> List[Tuple[int, str]]:
    units: List[Tuple[int, str]] = []
    for idx, ch in enumerate(s or ""):
        if not ch.strip():
            continue
        if ch in PUNCTUATION_CHARS:
            continue
        units.append((idx, ch))
    return units


def _normalize_text(s: str) -> str:
    return "".join(ch for _, ch in _extract_comparison_units(s))


def _calculate_accuracy(standard: str, actual: str) -> float:
    clean_standard = _normalize_text(standard)
    clean_actual = _normalize_text(actual)
    if not clean_standard:
        return 100.0 if not clean_actual else 0.0
    matcher = difflib.SequenceMatcher(None, clean_standard, clean_actual)
    return matcher.ratio() * 100.0


def _summarize_alignment(standard: str, actual: str) -> Dict[str, int]:
    standard_units = _extract_comparison_units(standard)
    actual_units = _extract_comparison_units(actual)
    standard_chars = [ch for _, ch in standard_units]
    actual_chars = [ch for _, ch in actual_units]
    matcher = difflib.SequenceMatcher(None, standard_chars, actual_chars)

    correct = 0
    mispronunciation = 0
    omission = 0
    insertion = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        ref_len = i2 - i1
        hyp_len = j2 - j1
        if tag == "equal":
            correct += ref_len
        elif tag == "replace":
            overlap = min(ref_len, hyp_len)
            mispronunciation += overlap
            omission += max(0, ref_len - overlap)
            insertion += max(0, hyp_len - overlap)
        elif tag == "delete":
            omission += ref_len
        elif tag == "insert":
            insertion += hyp_len

    return {
        "correct": int(correct),
        "mispronunciation": int(mispronunciation),
        "omission": int(omission),
        "insertion": int(insertion),
        "ref_len": int(len(standard_chars)),
        "hyp_len": int(len(actual_chars)),
    }


def _generate_error_details(standard: str, actual: str) -> List[Dict[str, Any]]:
    errors: List[Dict[str, Any]] = []
    standard_units = _extract_comparison_units(standard)
    actual_units = _extract_comparison_units(actual)
    matcher = difflib.SequenceMatcher(
        None,
        [ch for _, ch in standard_units],
        [ch for _, ch in actual_units],
    )
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        position = standard_units[i1][0] if i1 < len(standard_units) else len(standard or "")
        expected = "".join(ch for _, ch in standard_units[i1:i2])
        actual_text = "".join(ch for _, ch in actual_units[j1:j2])
        if tag == "replace":
            ref_slice = standard_units[i1:i2]
            hyp_slice = actual_units[j1:j2]
            overlap = min(len(ref_slice), len(hyp_slice))
            for idx in range(overlap):
                expected_char = ref_slice[idx][1]
                actual_char = hyp_slice[idx][1]
                if expected_char != actual_char:
                    errors.append(
                        {
                            "type": "mispronunciation",
                            "position": ref_slice[idx][0],
                            "expected": expected_char,
                            "actual": actual_char,
                        }
                    )
            if len(ref_slice) > overlap:
                remain_expected = "".join(ch for _, ch in ref_slice[overlap:])
                if remain_expected:
                    errors.append({"type": "omission", "position": ref_slice[overlap][0], "expected": remain_expected, "actual": ""})
            if len(hyp_slice) > overlap:
                remain_actual = "".join(ch for _, ch in hyp_slice[overlap:])
                if remain_actual:
                    errors.append({"type": "insertion", "position": position, "expected": "", "actual": remain_actual})
        elif tag == "delete":
            if expected:
                errors.append({"type": "omission", "position": position, "expected": expected, "actual": ""})
        elif tag == "insert":
            if actual_text:
                errors.append({"type": "insertion", "position": position, "expected": "", "actual": actual_text})
    return errors


def clean_transcript(text: str, standard_text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"([，。！？；：、,.!?;:\s])\1+", r"\1", cleaned)
    for word in ["诺", "额", "啊", "嗯", "那个", "这个"]:
        cleaned = cleaned.replace(word, "")

    # Keep misread and extra characters so downstream alignment can distinguish
    # mispronunciation/insertion from true omission.
    filtered = "".join(
        ch
        for ch in cleaned
        if ch in PUNCTUATION_CHARS
        or ch.isspace()
        or ("\u4e00" <= ch <= "\u9fff")
        or ch.isalnum()
    )
    return filtered.strip() or cleaned.strip()


def _resolve_asr_confidence(raw_confidence: float, standard_text: str, transcript: str, alignment: Optional[Dict[str, int]] = None) -> float:
    raw = max(0.0, min(1.0, float(raw_confidence or 0.0)))
    if raw > 0.0:
        return raw
    if not (transcript or "").strip():
        return 0.0

    alignment = alignment or _summarize_alignment(standard_text, transcript)
    ref_len = max(1, int(alignment.get("ref_len") or 0))
    correct = int(alignment.get("correct") or 0)
    omission = int(alignment.get("omission") or 0)
    insertion = int(alignment.get("insertion") or 0)
    mispronunciation = int(alignment.get("mispronunciation") or 0)

    sequence_ratio = max(0.0, min(1.0, _calculate_accuracy(standard_text, transcript) / 100.0))
    weighted_match = max(
        0.0,
        min(
            1.0,
            (correct - (0.8 * mispronunciation) - (1.0 * omission) - (0.4 * insertion)) / ref_len,
        ),
    )
    coverage_ratio = max(0.0, min(1.0, (ref_len - omission) / ref_len))
    quality = (sequence_ratio * 0.5) + (weighted_match * 0.3) + (coverage_ratio * 0.2)
    return round(max(0.0, min(0.98, 0.15 + (0.83 * quality))), 4)


def evaluate_with_tolerance(standard: str, transcript: str) -> Tuple[int, int]:
    standard_chars = [ch for _, ch in _extract_comparison_units(standard)]
    transcript_chars = [ch for _, ch in _extract_comparison_units(transcript)]
    if not standard_chars:
        return 100, 100

    standard_set = set(standard_chars)
    transcript_set = set(transcript_chars)
    coverage = len(standard_set & transcript_set) / max(1, len(standard_set))
    sequence_ratio = _calculate_accuracy(standard, transcript) / 100.0

    if coverage > 0.8:
        accuracy = 90 + (coverage - 0.8) * 50
    else:
        accuracy = coverage * 100
    semantic = max(accuracy, coverage * 100, sequence_ratio * 100)
    return int(round(max(0, min(100, accuracy)))), int(round(max(0, min(100, semantic))))


def _split_text_segments(text: str) -> List[str]:
    parts = re.split(r"[，。！？；：,.!?;:\n]+", text or "")
    return [_normalize_text(part) for part in parts if _normalize_text(part)]


def _count_segment_hits(standard: str, transcript: str) -> Tuple[int, int]:
    segments = _split_text_segments(standard)
    transcript_norm = _normalize_text(transcript)
    if not segments:
        return 0, 0

    hits = 0
    for seg in segments:
        matcher = difflib.SequenceMatcher(None, seg, transcript_norm)
        ratio = matcher.ratio()
        seg_set = set(seg)
        hit_chars = sum(1 for ch in seg if ch in transcript_norm)
        coverage = hit_chars / max(1, len(seg_set))
        if ratio >= 0.6 or coverage >= 0.6:
            hits += 1
    return hits, len(segments)


def _compute_content_score(standard: str, transcript: str, alignment: Dict[str, int]) -> Tuple[int, Dict[str, float]]:
    ref_len = max(1, int(alignment.get("ref_len") or 0))
    omission = int(alignment.get("omission") or 0)
    coverage_ratio = max(0.0, min(1.0, (ref_len - omission) / ref_len))
    segment_hits, segment_total = _count_segment_hits(standard, transcript)
    segment_ratio = (segment_hits / segment_total) if segment_total else 1.0

    coverage_score = coverage_ratio * 100.0
    segment_score = segment_ratio * 100.0
    content_score = (coverage_score * 0.6) + (segment_score * 0.4)
    return int(round(max(0.0, min(100.0, content_score)))), {
        "coverage_ratio": round(coverage_ratio, 4),
        "segment_hit_ratio": round(segment_ratio, 4),
        "segment_hits": float(segment_hits),
        "segment_total": float(segment_total),
    }


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


def convert_audio_for_xunfei(audio_bytes: bytes) -> bytes:
    try:
        wf = wave.open(io.BytesIO(audio_bytes), "rb")
        nchannels, sampwidth, framerate, nframes = wf.getparams()[:4]
        wf.close()
        print(f"[DEBUG] 原始音频: {len(audio_bytes)} bytes, {nchannels}ch, {framerate}Hz, {sampwidth * 8}bit", flush=True)
    except Exception:
        pass

    pcm = _any_audio_to_pcm_via_ffmpeg(audio_bytes, suffix=".wav")
    print(f"[DEBUG] 转换后PCM: {len(pcm)} bytes, 1ch, 16000Hz, 16bit, 预期时长={_pcm_duration_seconds(pcm):.2f}s", flush=True)
    return pcm


def _any_audio_to_pcm_via_ffmpeg(audio_bytes: bytes, suffix: str) -> bytes:
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


def _pcm_duration_seconds(pcm_bytes: bytes) -> float:
    return len(pcm_bytes) / 32000.0


def _audio_base64_to_pcm16k(audio_base64: str) -> bytes:
    raw, mime = _decode_audio_bytes(audio_base64)
    if mime in ("audio/wav", "audio/x-wav", "audio/wave"):
        return convert_audio_for_xunfei(raw)

    suffix = ".bin"
    if mime == "audio/webm":
        suffix = ".webm"
    elif mime == "audio/ogg":
        suffix = ".ogg"
    elif mime in ("audio/mpeg", "audio/mp3"):
        suffix = ".mp3"
    elif mime in ("audio/mp4", "video/mp4"):
        suffix = ".mp4"
    return _any_audio_to_pcm_via_ffmpeg(raw, suffix=suffix)


def _count_excessive_repeats(text: str, standard_text: str) -> int:
    actual = _normalize_text(text)
    standard = _normalize_text(standard_text)

    allowed: Dict[str, int] = {}
    idx = 0
    while idx < len(standard):
        j = idx + 1
        while j < len(standard) and standard[j] == standard[idx]:
            j += 1
        allowed[standard[idx]] = max(allowed.get(standard[idx], 1), j - idx)
        idx = j

    excessive = 0
    idx = 0
    while idx < len(actual):
        j = idx + 1
        while j < len(actual) and actual[j] == actual[idx]:
            j += 1
        run_len = j - idx
        allow_len = allowed.get(actual[idx], 1)
        if run_len > allow_len:
            excessive += run_len - allow_len
        idx = j
    return excessive


def _analyze_pauses(pcm_bytes: bytes) -> Dict[str, float]:
    if not pcm_bytes:
        return {
            "pause_count": 0.0,
            "long_pause_count": 0.0,
            "total_pause_seconds": 0.0,
            "active_span_seconds": 0.0,
            "voiced_seconds": 0.0,
            "speech_ratio": 0.0,
        }

    x = [v / 32768.0 for v in memoryview(pcm_bytes).cast("h")]
    if len(x) < 480:
        return {
            "pause_count": 0.0,
            "long_pause_count": 0.0,
            "total_pause_seconds": 0.0,
            "active_span_seconds": 0.0,
            "voiced_seconds": 0.0,
            "speech_ratio": 0.0,
        }

    import math as _math

    frame = 480
    hop = 160
    rms = []
    for start in range(0, len(x) - frame + 1, hop):
        w = x[start : start + frame]
        energy = _math.sqrt(sum(v * v for v in w) / len(w) + 1e-12)
        rms.append(energy)
    if not rms:
        return {
            "pause_count": 0.0,
            "long_pause_count": 0.0,
            "total_pause_seconds": 0.0,
            "active_span_seconds": 0.0,
            "voiced_seconds": 0.0,
            "speech_ratio": 0.0,
        }

    arr = sorted(rms)
    q_index = max(0, int(len(arr) * 0.2) - 1)
    noise_rms = arr[q_index]
    speech_thr = max(noise_rms * 3.0, 0.02)
    speech_mask = [v >= speech_thr for v in rms]

    if not any(speech_mask):
        return {
            "pause_count": 0.0,
            "long_pause_count": 0.0,
            "total_pause_seconds": 0.0,
            "active_span_seconds": 0.0,
            "voiced_seconds": 0.0,
            "speech_ratio": 0.0,
        }

    first = speech_mask.index(True)
    last = len(speech_mask) - 1 - speech_mask[::-1].index(True)
    pause_count = 0
    long_pause_count = 0
    total_pause_seconds = 0.0
    run = 0
    for flag in speech_mask[first : last + 1]:
        if not flag:
            run += 1
            continue
        if run:
            pause_seconds = (run * hop) / 16000.0
            if pause_seconds >= 0.15:
                total_pause_seconds += pause_seconds
            if pause_seconds >= 0.3:
                pause_count += 1
            if pause_seconds >= 0.8:
                long_pause_count += 1
            run = 0
    if run:
        pause_seconds = (run * hop) / 16000.0
        if pause_seconds >= 0.15:
            total_pause_seconds += pause_seconds
        if pause_seconds >= 0.3:
            pause_count += 1
        if pause_seconds >= 0.8:
            long_pause_count += 1

    active_frames = max(1, last - first + 1)
    voiced_frames = sum(1 for flag in speech_mask[first : last + 1] if flag)
    frame_seconds = hop / 16000.0
    active_span_seconds = ((active_frames - 1) * frame_seconds) + (frame / 16000.0)
    voiced_seconds = voiced_frames * frame_seconds
    speech_ratio = voiced_seconds / max(active_span_seconds, frame_seconds)

    return {
        "pause_count": float(pause_count),
        "long_pause_count": float(long_pause_count),
        "total_pause_seconds": round(float(total_pause_seconds), 4),
        "active_span_seconds": round(float(active_span_seconds), 4),
        "voiced_seconds": round(float(voiced_seconds), 4),
        "speech_ratio": round(float(speech_ratio), 4),
    }


def _compute_rate_score(rate: float, *, ideal_min: float, ideal_max: float, low_slope: float, high_slope: float) -> int:
    if ideal_min <= rate <= ideal_max:
        return 100
    if rate < ideal_min:
        return int(round(max(0.0, 100.0 - (ideal_min - rate) * low_slope)))
    return int(round(max(0.0, 100.0 - (rate - ideal_max) * high_slope)))


def _compute_fluency_score(
    *,
    pcm_bytes: bytes,
    raw_transcript: str,
    cleaned_transcript: str,
    standard_text: str,
    duration: float,
) -> Tuple[int, Dict[str, float]]:
    effective_chars = len(_normalize_text(cleaned_transcript))
    pause_info = _analyze_pauses(pcm_bytes)
    active_span_seconds = max(float(pause_info.get("active_span_seconds") or duration or 0.1), 0.1)
    voiced_seconds = max(float(pause_info.get("voiced_seconds") or 0.0), min(active_span_seconds, duration, 0.1))

    articulation_rate = effective_chars / max(voiced_seconds, 0.1)
    pace_rate = effective_chars / max(active_span_seconds, 0.1)
    articulation_score = _compute_rate_score(
        articulation_rate,
        ideal_min=2.0,
        ideal_max=4.8,
        low_slope=24.0,
        high_slope=18.0,
    )
    pace_score = _compute_rate_score(
        pace_rate,
        ideal_min=1.2,
        ideal_max=3.2,
        low_slope=35.0,
        high_slope=20.0,
    )
    speed_score = int(round((articulation_score * 0.65) + (pace_score * 0.35)))

    expected_pause_count = max(0, len(_split_text_segments(standard_text)) - 1)
    expected_long_pause_count = max(0, len(re.findall(r"[。！？.!?]+", standard_text or "")) - 1)
    excess_pause_count = max(0.0, float(pause_info["pause_count"]) - float(expected_pause_count))
    excess_long_pause_count = max(0.0, float(pause_info["long_pause_count"]) - float(expected_long_pause_count))
    pause_ratio = float(pause_info.get("total_pause_seconds") or 0.0) / max(active_span_seconds, 0.1)
    pause_penalty = (excess_pause_count * 4.0) + (excess_long_pause_count * 6.0) + (max(0.0, pause_ratio - 0.25) * 60.0)
    pause_score = int(round(max(0.0, 100.0 - pause_penalty)))

    repeat_chars = _count_excessive_repeats(raw_transcript, standard_text)
    repeat_penalty = min(30.0, repeat_chars * 5.0)
    repeat_score = int(round(max(0.0, 100.0 - repeat_penalty)))

    fluency = (speed_score * 0.45) + (pause_score * 0.4) + (repeat_score * 0.15)
    return int(round(max(0.0, min(100.0, fluency)))), {
        "speed_chars_per_sec": round(pace_rate, 4),
        "articulation_chars_per_sec": round(articulation_rate, 4),
        "active_span_seconds": round(active_span_seconds, 4),
        "voiced_seconds": round(voiced_seconds, 4),
        "speed_score": float(speed_score),
        "articulation_score": float(articulation_score),
        "pace_score": float(pace_score),
        "pause_count": float(pause_info["pause_count"]),
        "long_pause_count": float(pause_info["long_pause_count"]),
        "total_pause_seconds": float(pause_info.get("total_pause_seconds") or 0.0),
        "pause_ratio": round(pause_ratio, 4),
        "expected_pause_count": float(expected_pause_count),
        "expected_long_pause_count": float(expected_long_pause_count),
        "excess_pause_count": float(excess_pause_count),
        "excess_long_pause_count": float(excess_long_pause_count),
        "pause_score": float(pause_score),
        "repeat_chars": float(repeat_chars),
        "repeat_score": float(repeat_score),
    }


def _emit_test_report(
    *,
    base_dir: Path,
    transcript: str,
    standard_text: str,
    breakdown: Dict[str, int],
    emotion_expression: Optional[Dict[str, Any]],
) -> None:
    if not isinstance(emotion_expression, dict):
        return

    detected = emotion_expression.get("detected") or {}
    av = detected.get("av_raw") or {}
    match = emotion_expression.get("match") or {}
    target = emotion_expression.get("target") or {}
    calibration = emotion_expression.get("calibration") or {}
    top1 = detected.get("top1") or {}
    target_av = target.get("target_av_raw") or {}

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "poem_title": target.get("poem_title"),
        "calibration_mode": match.get("calibration_mode") or calibration.get("mode") or "default",
        "transcript": transcript,
        "reference": standard_text,
        "arousal": round(float(av.get("arousal") or 0.0), 4),
        "valence": round(float(av.get("valence") or 0.0), 4),
        "top1_label": top1.get("label"),
        "top1_prob": round(float(top1.get("prob") or 0.0), 4),
        "target_arousal": round(float(target_av.get("arousal") or 0.0), 4) if target_av else None,
        "target_valence": round(float(target_av.get("valence") or 0.0), 4) if target_av else None,
        "style_match": int(match.get("style_match") or 0),
        "target_center_distance": round(float(match.get("target_center_distance") or match.get("distance_from_target") or 0.0), 4),
        "normalized_distance": round(float(match.get("normalized_distance") or 0.0), 4),
        "within_tolerance": bool(match.get("within_tolerance", False)),
        "style_deviation_rating": str(match.get("style_deviation_rating") or "未知"),
        "accuracy": int(breakdown.get("accuracy") or 0),
        "pronunciation": int(breakdown.get("pronunciation") or 0),
        "fluency": int(breakdown.get("fluency") or 0),
        "semantic": int(breakdown.get("semantic") or 0),
        "content_completeness": int(breakdown.get("semantic") or 0),
    }

    print(
        "[TEST-REPORT] "
        f"arousal={report['arousal']:.4f} | "
        f"valence={report['valence']:.4f} | "
        f"top1={report['top1_label']}({report['top1_prob']:.2f}) | "
        f"style_match={report['style_match']} | "
        f"distance={report['target_center_distance']:.4f} | "
        f"mode={report['calibration_mode']} | "
        f"within_tolerance={report['within_tolerance']} | "
        f"style_deviation={report['style_deviation_rating']} | "
        f"accuracy={report['accuracy']} | pronunciation={report['pronunciation']} | "
        f"fluency={report['fluency']} | content_completeness={report['content_completeness']}",
        flush=True,
    )
    print("[TEST-REPORT-JSON-BEGIN]", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print("[TEST-REPORT-JSON-END]", flush=True)

    report_dir = base_dir / "test_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    filename = report_dir / f"test-report-{time.strftime('%Y%m%d-%H%M%S')}.json"
    try:
        filename.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        print(f"[TEST-REPORT] failed_to_write file={filename}", flush=True)


def _build_local_teacher_feedback(
    *,
    transcript: str,
    standard_text: str,
    breakdown: Dict[str, int],
    error_details: List[Dict[str, Any]],
    emotion_expression: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    accuracy = int(breakdown.get("accuracy") or 0)
    pronunciation = int(breakdown.get("pronunciation") or 0)
    fluency = int(breakdown.get("fluency") or 0)
    content = int(breakdown.get("semantic") or 0)

    emotion_match = {}
    emotion_target = {}
    detected = {}
    if isinstance(emotion_expression, dict):
        emotion_match = emotion_expression.get("match") or {}
        emotion_target = emotion_expression.get("target") or {}
        detected = emotion_expression.get("detected") or {}

    style_match = int(emotion_match.get("style_match") or 0)
    style_gap = str((emotion_expression or {}).get("feedback_rules", {}).get("style_gap") or "暂无情感分析结论")
    top1 = (detected.get("top1") or {}).get("label") if isinstance(detected, dict) else None
    tags = emotion_target.get("tags") or []

    if accuracy >= 85 and content >= 85:
        overall_comment = "背诵整体较扎实，字词准确，内容也比较完整。"
    elif accuracy >= 70:
        overall_comment = "背诵基本完成，但个别字词和内容细节还需要再巩固。"
    else:
        overall_comment = "当前背诵还不够稳定，建议先把原文内容背熟再提高表现力。"

    if style_match >= 80:
        emotion_feedback = f"情感表达与作品意境比较贴合，已经能体现出{('、'.join(tags) if tags else '诗歌')}的朗读感觉。"
    elif style_match >= 55:
        emotion_feedback = f"情感方向基本正确，但感染力还不够集中，{style_gap}。"
    else:
        emotion_feedback = f"情感表达与目标风格还有明显距离，当前更接近“{top1 or '中性'}”的表达，需要主动读出诗歌意境。"

    suggestions: List[str] = []
    if error_details:
        first_error = error_details[0]
        if first_error.get("type") == "omission":
            suggestions.append(f"先把“{first_error.get('expected') or ''}”这一处补读准确，减少漏读。")
        elif first_error.get("type") == "mispronunciation":
            suggestions.append(f"重点纠正“{first_error.get('expected') or ''}”这一处的读音和字词辨认。")
    if fluency < 75:
        suggestions.append("朗读时放慢一点速度，减少中途停顿和重复，让节奏更自然。")
    if content < 75:
        suggestions.append("建议按诗句分段背诵，先保证每一句完整，再连起来朗读。")
    if style_match < 70:
        suggestions.append("可以先听一遍示例朗读，再模仿更明快、更有画面感的语气。")
    if not suggestions:
        suggestions.append("继续保持当前状态，多练几遍，让字音、节奏和情感表达更统一。")

    poetic_insight = "背诵不仅要把字词说出来，还要让听的人感受到诗中的画面和情绪。"
    master_comparison = "可继续参考示例朗读的节奏和语气变化，重点学习句尾收束与情绪起伏。"
    return {
        "overall_comment": overall_comment,
        "emotion_feedback": emotion_feedback,
        "suggestions": suggestions[:3],
        "poetic_insight": poetic_insight,
        "master_comparison": master_comparison,
        "used_metrics": {
            "accuracy": accuracy,
            "fluency": fluency,
            "pronunciation": pronunciation,
            "semantic": content,
            "style_match": style_match,
            "stability": int((((emotion_expression or {}).get("stability") or {}).get("stability") or 0))
            if isinstance(emotion_expression, dict)
            else 0,
        },
        "source": "local_fallback",
    }


def _sanitize_intelligent_feedback(
    feedback: Optional[Dict[str, Any]],
    emotion_expression: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(feedback, dict):
        return feedback
    if not isinstance(emotion_expression, dict):
        return feedback

    match = emotion_expression.get("match") or {}
    target = emotion_expression.get("target") or {}
    style_match = int(match.get("style_match") or 0)
    if style_match < 80:
        return feedback

    tags = target.get("tags") or []
    positive_emotion_feedback = f"情感表达与作品意境较贴合，已经能体现出{('、'.join(tags) if tags else '诗歌')}的朗读感觉。"
    negative_markers = (
        "过于平淡",
        "不太符合",
        "明显偏离",
        "情感有偏差",
        "不符",
        "平淡",
        "偏离",
    )

    sanitized = dict(feedback)
    emotion_feedback = str(sanitized.get("emotion_feedback") or "")
    if any(marker in emotion_feedback for marker in negative_markers):
        sanitized["emotion_feedback"] = positive_emotion_feedback

    overall_comment = str(sanitized.get("overall_comment") or "")
    if any(marker in overall_comment for marker in negative_markers):
        sanitized["overall_comment"] = "整体背诵完成较好，内容基本准确，情感表达也与作品意境较为贴合。"

    suggestions = sanitized.get("suggestions")
    if isinstance(suggestions, list):
        filtered = []
        for item in suggestions:
            text = str(item)
            if any(marker in text for marker in negative_markers):
                continue
            filtered.append(text)
        if not filtered:
            filtered = ["继续保持当前情感方向，再把字音和节奏练得更稳定一些。"]
        sanitized["suggestions"] = filtered[:3]

    return sanitized


class Evaluator:
    def __init__(self) -> None:
        self.app_id = os.getenv("XUNFEI_APP_ID", "").strip()
        self.api_key = os.getenv("XUNFEI_API_KEY", "").strip()
        self.api_secret = os.getenv("XUNFEI_API_SECRET", "").strip()

    def transcribe(self, audio_base64: str) -> XunfeiAsrResult:
        raw, mime = _decode_audio_bytes(audio_base64)
        suffix = ".bin"
        if mime in ("audio/wav", "audio/x-wav", "audio/wave"):
            pcm = convert_audio_for_xunfei(raw)
        else:
            if mime == "audio/webm":
                suffix = ".webm"
            elif mime == "audio/ogg":
                suffix = ".ogg"
            elif mime in ("audio/mpeg", "audio/mp3"):
                suffix = ".mp3"
            elif mime in ("audio/mp4", "video/mp4"):
                suffix = ".mp4"
            pcm = _any_audio_to_pcm_via_ffmpeg(raw, suffix=suffix)
            print(f"[DEBUG] 原始音频: {len(raw)} bytes, mime={mime}; ffmpeg转换后PCM: {len(pcm)} bytes, 预期时长={_pcm_duration_seconds(pcm):.2f}s", flush=True)

        if not self.app_id or not self.api_key or not self.api_secret:
            duration = _pcm_duration_seconds(pcm)
            return XunfeiAsrResult(transcript="", confidence=0.0, segments=[], duration=duration)

        t0 = time.time()
        result = transcribe_pcm(
            pcm,
            app_id=self.app_id,
            api_key=self.api_key,
            api_secret=self.api_secret,
            timeout_seconds=6.5,
        )
        print(
            f"xunfei_transcribed seconds={round(time.time()-t0,2)} duration={round(result.duration,2)} text_len={len((result.transcript or '').strip())}",
            flush=True,
        )
        return result

    def calibrate_baseline(self, audio_base64: str, sample_text: str = "") -> Dict[str, Any]:
        from audio_feature_extractor import AudioFeatureExtractor

        extractor = AudioFeatureExtractor(base_dir=Path(__file__).resolve().parent)
        packet = extractor.extract_emotion_expression(audio_base64, sample_text or "")
        emotion_expression = packet.get("emotion_expression") or {}
        detected = emotion_expression.get("detected") or {}
        av = detected.get("av_raw") or {}
        return {
            "baseline_arousal": float(av.get("arousal") or 0.0),
            "baseline_valence": float(av.get("valence") or 0.0),
            "audio_quality": emotion_expression.get("audio_quality"),
            "detected": detected,
        }

    def evaluate(
        self,
        audio_base64: str,
        standard_text: str,
        language: str = "zh",
        user_baseline: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            asr = self.transcribe(audio_base64)
            raw_transcript = (asr.transcript or "").strip()
            transcript = clean_transcript(raw_transcript, standard_text)
            duration = max(float(asr.duration or 0.0), 0.1)
            pcm_bytes = _audio_base64_to_pcm16k(audio_base64)
            alignment = _summarize_alignment(standard_text, transcript)
            confidence = _resolve_asr_confidence(float(asr.confidence or 0.0), standard_text, transcript, alignment)

            if not transcript:
                accuracy_score = 0
                pronunciation = 0
                fluency = 0
                semantic = 0
                accuracy = 0.0
                scoring_details = {
                    "alignment": alignment,
                    "pronunciation": {"confidence": float(confidence), "mis_ratio": 0.0, "weighted_mispronunciation": 0.0},
                    "fluency": {"speed_chars_per_sec": 0.0, "speed_score": 0.0, "pause_count": 0.0, "long_pause_count": 0.0, "pause_score": 0.0, "repeat_chars": 0.0, "repeat_score": 0.0},
                    "content": {"coverage_ratio": 0.0, "segment_hit_ratio": 0.0, "segment_hits": 0.0, "segment_total": 0.0},
                }
            else:
                accuracy = _calculate_accuracy(standard_text, transcript)
                correct = alignment["correct"]
                mispronunciation_count = alignment["mispronunciation"]
                omission = alignment["omission"]
                insertion = alignment["insertion"]
                ref_len = max(1, alignment["ref_len"])

                accuracy_raw = (correct - (0.8 * mispronunciation_count) - (1.0 * omission) - (0.4 * insertion)) / ref_len
                accuracy_score = int(round(max(0.0, min(100.0, accuracy_raw * 100.0))))

                pron_base = 60.0 + (40.0 * confidence)
                mis_ratio = mispronunciation_count / ref_len
                pron_penalty = min(35.0, mis_ratio * 100.0 * 0.6)
                pronunciation = int(round(max(0.0, min(100.0, pron_base - pron_penalty))))

                fluency, fluency_features = _compute_fluency_score(
                    pcm_bytes=pcm_bytes,
                    raw_transcript=raw_transcript,
                    cleaned_transcript=transcript,
                    standard_text=standard_text,
                    duration=duration,
                )

                semantic, content_features = _compute_content_score(standard_text, transcript, alignment)
                scoring_details = {
                    "alignment": alignment,
                    "pronunciation": {
                        "confidence": round(confidence, 4),
                        "mis_ratio": round(mis_ratio, 4),
                        "weighted_mispronunciation": float(mispronunciation_count),
                    },
                    "fluency": fluency_features,
                    "content": content_features,
                }

            total_score = round((accuracy_score * 0.35) + (pronunciation * 0.25) + (fluency * 0.20) + (semantic * 0.20))
            error_details = _generate_error_details(standard_text, transcript)

            feedback = "评测完成"
            if not transcript:
                feedback = "语音识别为空，请重试"
            elif accuracy_score < 60:
                feedback = "需要多加练习，注意字词的准确性和内容完整性。"
            elif semantic < 60:
                feedback = "整体背诵基本完成，但存在漏句或关键内容缺失。"
            elif fluency < 60:
                feedback = "内容基本正确，但朗读不够流畅，停顿和节奏还需要调整。"
            elif error_details:
                err = error_details[0]
                if err["type"] == "omission":
                    feedback = f"注意不要漏读 '{err['expected']}'。"
                elif err["type"] == "mispronunciation":
                    feedback = f"注意 '{err['expected']}' 的发音。"

            emotion_schema_version = None
            emotion_expression = None
            try:
                from audio_feature_extractor import AudioFeatureExtractor

                extractor = AudioFeatureExtractor(base_dir=Path(__file__).resolve().parent)
                packet = extractor.extract_emotion_expression(
                    audio_base64,
                    standard_text,
                    user_baseline=user_baseline,
                )
                emotion_schema_version = packet.get("schema_version")
                emotion_expression = packet.get("emotion_expression")
            except Exception as e:
                print(f"emotion_extract_failed error={repr(e)} trace={traceback.format_exc(limit=3)}", flush=True)
                emotion_schema_version = None
                emotion_expression = None

            breakdown_payload = {
                "accuracy": int(accuracy_score),
                "pronunciation": int(pronunciation),
                "fluency": int(fluency),
                "semantic": int(semantic),
            }
            _emit_test_report(
                base_dir=Path(__file__).resolve().parent,
                transcript=transcript,
                standard_text=standard_text,
                breakdown=breakdown_payload,
                emotion_expression=emotion_expression,
            )

            intelligent_feedback = None
            fallback_note = None
            try:
                if isinstance(emotion_expression, dict):
                    from deepseek_client import DeepSeekClient, validate_used_metrics
                    from deepseek_prompt_builder import build_prompt

                    wpm = int(round((len(transcript) / duration) * 60.0)) if duration > 0 else 0
                    emo_target = (emotion_expression.get("target") or {}) if isinstance(emotion_expression, dict) else {}
                    structured_data = {
                        "transcript": transcript,
                        "reference": standard_text,
                        "poem_title": emo_target.get("poem_title"),
                        "breakdown": {"accuracy": accuracy_score, "fluency": fluency, "pronunciation": pronunciation, "semantic": semantic},
                        "timing_metrics": {"wpm": wpm, "pause_count": None},
                        "emotion_expression": emotion_expression,
                        "user_baseline": user_baseline,
                    }
                    prompt = build_prompt(structured_data)
                    client = DeepSeekClient()
                    print(f"deepseek_begin has_key={bool(client.api_key)}", flush=True)
                    data = client.evaluate(prompt) if client.api_key else None
                    if data:
                        print("deepseek_ok", flush=True)
                        expected = {
                            "accuracy": int(accuracy_score),
                            "fluency": int(fluency),
                            "pronunciation": int(pronunciation),
                            "semantic": int(semantic),
                            "style_match": int((((emotion_expression or {}).get("match") or {}).get("style_match")) or 0),
                            "stability": int(((emotion_expression or {}).get("stability") or {}).get("stability") or 0)
                            if isinstance(emotion_expression, dict)
                            else 0,
                        }
                        if validate_used_metrics(data, expected, tolerance=2):
                            intelligent_feedback = _sanitize_intelligent_feedback(data, emotion_expression)
                        else:
                            got = data.get("used_metrics") if isinstance(data, dict) else None
                            print(f"deepseek_discarded reason=used_metrics_mismatch expected={expected} got={got}", flush=True)
                            intelligent_feedback = _build_local_teacher_feedback(
                                transcript=transcript,
                                standard_text=standard_text,
                                breakdown=breakdown_payload,
                                error_details=error_details,
                                emotion_expression=emotion_expression,
                            )
                            fallback_note = "AI深度点评未通过校验，已切换为本地教师点评"
                    elif client.api_key and client.last_error:
                        print(f"deepseek_failed error={client.last_error}", flush=True)
                        intelligent_feedback = _build_local_teacher_feedback(
                            transcript=transcript,
                            standard_text=standard_text,
                            breakdown=breakdown_payload,
                            error_details=error_details,
                            emotion_expression=emotion_expression,
                        )
                        fallback_note = "AI深度点评服务暂不可用，已切换为本地教师点评"
                    elif not client.api_key:
                        intelligent_feedback = _build_local_teacher_feedback(
                            transcript=transcript,
                            standard_text=standard_text,
                            breakdown=breakdown_payload,
                            error_details=error_details,
                            emotion_expression=emotion_expression,
                        )
                        fallback_note = "AI深度点评未配置，已切换为本地教师点评"
            except Exception as e:
                print(f"deepseek_exception error={repr(e)} trace={traceback.format_exc(limit=3)}", flush=True)
                intelligent_feedback = _build_local_teacher_feedback(
                    transcript=transcript,
                    standard_text=standard_text,
                    breakdown=breakdown_payload,
                    error_details=error_details,
                    emotion_expression=emotion_expression,
                )
                fallback_note = "AI深度点评服务暂不可用，已切换为本地教师点评"

            if intelligent_feedback is None:
                intelligent_feedback = _build_local_teacher_feedback(
                    transcript=transcript,
                    standard_text=standard_text,
                    breakdown=breakdown_payload,
                    error_details=error_details,
                    emotion_expression=emotion_expression,
                )
                if not fallback_note:
                    fallback_note = "已展示本地教师点评"
            else:
                intelligent_feedback = _sanitize_intelligent_feedback(intelligent_feedback, emotion_expression)

            return {
                "total_score": int(total_score),
                "breakdown": breakdown_payload,
                "error_details": error_details,
                "feedback": feedback,
                "transcript": transcript,
                "confidence": float(confidence),
                "segments": [s.__dict__ for s in (asr.segments or [])],
                "duration": float(asr.duration or 0.0),
                "scoring_details": scoring_details,
                "emotion_schema_version": emotion_schema_version,
                "emotion_expression": emotion_expression,
                "intelligent_feedback": intelligent_feedback,
                "fallback_note": fallback_note,
            }
        except Exception as e:
            return {
                "total_score": 0,
                "breakdown": {"accuracy": 0, "pronunciation": 0, "fluency": 0, "semantic": 0},
                "error_details": [],
                "feedback": f"评测失败：{str(e)}",
                "transcript": "",
                "confidence": 0.0,
                "segments": [],
                "duration": 0.0,
                "scoring_details": None,
                "emotion_schema_version": None,
                "emotion_expression": None,
                "intelligent_feedback": None,
                "fallback_note": "评测失败，已降级",
            }

# Singleton instance
evaluator = None

def get_evaluator():
    global evaluator
    if evaluator is None:
        evaluator = Evaluator()
    return evaluator
