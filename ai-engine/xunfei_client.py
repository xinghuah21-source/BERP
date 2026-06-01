import base64
import datetime
import hashlib
import hmac
import json
import ssl
import time
import _thread as thread
from dataclasses import dataclass
from time import mktime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import websocket


STATUS_FIRST_FRAME = 0
STATUS_CONTINUE_FRAME = 1
STATUS_LAST_FRAME = 2


@dataclass
class XunfeiSegment:
    text: str
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    confidence: Optional[float] = None


@dataclass
class XunfeiAsrResult:
    transcript: str
    confidence: float
    segments: List[XunfeiSegment]
    duration: float


def _create_ws_url(api_key: str, api_secret: str) -> str:
    base_url = "wss://iat-api.xfyun.cn/v2/iat"
    now = datetime.datetime.now()
    date = format_date_time(mktime(now.timetuple()))

    signature_origin = "host: " + "iat-api.xfyun.cn" + "\n"
    signature_origin += "date: " + date + "\n"
    signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"

    signature_sha = hmac.new(api_secret.encode("utf-8"), signature_origin.encode("utf-8"), digestmod=hashlib.sha256).digest()
    signature_sha = base64.b64encode(signature_sha).decode("utf-8")

    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")

    v = {"authorization": authorization, "date": date, "host": "iat-api.xfyun.cn"}
    return base_url + "?" + urlencode(v)


def _parse_any_result(result_obj: Any) -> Dict[str, Any]:
    if isinstance(result_obj, dict):
        return result_obj
    if isinstance(result_obj, str):
        try:
            raw = base64.b64decode(result_obj)
            return json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            return {}
    return {}


def _extract_words(text_json: Dict[str, Any]) -> Tuple[str, List[XunfeiSegment], float]:
    ws_list = text_json.get("ws") or []
    parts: List[str] = []
    segments: List[XunfeiSegment] = []
    conf_values: List[float] = []

    for ws in ws_list:
        start_ms = ws.get("bg")
        end_ms = ws.get("ed")
        cws = ws.get("cw") or []
        best = None
        for cand in cws:
            if best is None:
                best = cand
            elif (cand.get("sc") or 0) > (best.get("sc") or 0):
                best = cand
        if not best:
            continue
        w = str(best.get("w") or "")
        sc = best.get("sc")
        parts.append(w)
        if isinstance(sc, (int, float)):
            conf_values.append(float(sc))
        segments.append(XunfeiSegment(text=w, start_ms=start_ms if isinstance(start_ms, int) else None, end_ms=end_ms if isinstance(end_ms, int) else None, confidence=float(sc) if isinstance(sc, (int, float)) else None))

    transcript = "".join(parts).strip()
    confidence = 0.0
    if conf_values:
        confidence = sum(conf_values) / max(1, len(conf_values))
        confidence = max(0.0, min(100.0, confidence)) / 100.0
    return transcript, segments, confidence


def transcribe_pcm(
    pcm_bytes: bytes,
    *,
    app_id: str,
    api_key: str,
    api_secret: str,
    timeout_seconds: float = 6.5,
    frame_bytes: int = 40960,
    send_interval_seconds: float = 0.0,
    language: str = "zh_cn",
    accent: str = "mandarin",
) -> XunfeiAsrResult:
    websocket.setdefaulttimeout(timeout_seconds)
    ws_url = _create_ws_url(api_key=api_key, api_secret=api_secret)
    t_start = time.time()

    segments: List[XunfeiSegment] = []
    confidence_values: List[float] = []
    transcript_parts: List[str] = []

    duration = len(pcm_bytes) / 32000.0
    print(
        f"[DEBUG] pcm_bytes={len(pcm_bytes)} duration={duration:.2f}s frame_bytes={frame_bytes} frames={max(1, (len(pcm_bytes)+frame_bytes-1)//frame_bytes)}",
        flush=True,
    )

    def on_message(ws: websocket.WebSocketApp, message: str) -> None:
        nonlocal segments, confidence_values, transcript_parts
        msg = json.loads(message)
        code = msg.get("code")
        status = (msg.get("data") or {}).get("status")
        if isinstance(code, int) and code != 0:
            sid = msg.get("sid")
            m = msg.get("message")
            print(f"[DEBUG] xunfei_error code={code} message={m} sid={sid}", flush=True)
            ws.close()
            return
        result = (msg.get("data") or {}).get("result")
        text_json = _parse_any_result(result)
        if text_json:
            piece, piece_segments, piece_conf = _extract_words(text_json)
            if piece:
                transcript_parts.append(piece)
            for s in piece_segments:
                segments.append(s)
            if piece_conf > 0:
                confidence_values.append(piece_conf)
        if status == 2:
            ws.close()

    def on_error(ws: websocket.WebSocketApp, error: Any) -> None:
        print(f"[DEBUG] xunfei_ws_error {error}", flush=True)
        try:
            ws.close()
        except Exception:
            pass

    ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error)

    def run_sender() -> None:
        status = STATUS_FIRST_FRAME
        pos = 0
        while True:
            chunk = pcm_bytes[pos : pos + frame_bytes]
            pos += len(chunk)
            audio_b64 = base64.b64encode(chunk).decode("utf-8")
            if not chunk:
                status = STATUS_LAST_FRAME
            if status == STATUS_FIRST_FRAME:
                d = {
                    "common": {"app_id": app_id},
                    "business": {
                        "language": language,
                        "domain": "iat",
                        "accent": accent,
                        "vinfo": 1,
                        "pd": "edu",
                        "ptt": 1,
                    },
                    "data": {"status": 0, "format": "audio/L16;rate=16000", "encoding": "raw", "audio": audio_b64},
                }
                ws.send(json.dumps(d))
                status = STATUS_CONTINUE_FRAME
            elif status == STATUS_CONTINUE_FRAME:
                d = {"data": {"status": 1, "format": "audio/L16;rate=16000", "encoding": "raw", "audio": audio_b64}}
                ws.send(json.dumps(d))
            else:
                d = {"data": {"status": 2, "format": "audio/L16;rate=16000", "encoding": "raw", "audio": audio_b64}}
                ws.send(json.dumps(d))
                break
            if (time.time() - t_start) > timeout_seconds:
                try:
                    ws.close()
                except Exception:
                    pass
                break
            if send_interval_seconds > 0:
                time.sleep(send_interval_seconds)

    def on_open(_ws: websocket.WebSocketApp) -> None:
        thread.start_new_thread(run_sender, ())

    ws.on_open = on_open

    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_interval=15, ping_timeout=5)

    transcript = "".join(transcript_parts).strip()
    confidence = 0.0
    if confidence_values:
        confidence = sum(confidence_values) / max(1, len(confidence_values))
        confidence = max(0.0, min(1.0, confidence))
    return XunfeiAsrResult(transcript=transcript, confidence=confidence, segments=segments, duration=duration)
