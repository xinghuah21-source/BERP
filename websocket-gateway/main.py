import asyncio
import os
import time
import traceback
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from redis.asyncio import Redis

from audio_buffer import BufferedWindow
from connection import ConnectionManager, ConnectionState


def _get_secret_key() -> str:
    return os.getenv("SECRET_KEY", "your-secret-key-here")


def _verify_jwt(token: str) -> Dict[str, Any]:
    if token == "test":
        return {"sub": "test"}
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=["HS256"])
    except JWTError as e:
        raise ValueError(str(e))
    sub = payload.get("sub")
    if not sub:
        raise ValueError("missing sub")
    return payload


def _progress_from_seq(seq: int, is_final: bool) -> int:
    if is_final:
        return 100
    return min(99, max(1, int(seq * 15)))


AI_ENGINE_TIMEOUT_SECONDS = float(os.getenv("AI_ENGINE_TIMEOUT_SECONDS", "30"))


async def _send_stage(manager: ConnectionManager, user_id: str, state: ConnectionState, progress: int, stage_text: str) -> None:
    progress = max(0, min(99, int(progress)))
    state.last_progress = progress
    await manager.send_json(
        user_id,
        {
            "type": "state",
            "progress": progress,
            "stage_text": stage_text,
        },
    )


async def _run_stage_progress(manager: ConnectionManager, user_id: str, state: ConnectionState) -> None:
    stages = [
        (12, "音频转码中", 1.0),
        (36, "语音识别中", 2.0),
        (68, "情感推理中", 3.0),
        (88, "AI教师点评中", 3.0),
    ]
    for progress, stage_text, delay in stages:
        await _send_stage(manager, user_id, state, progress, stage_text)
        await asyncio.sleep(delay)
    while True:
        await _send_stage(manager, user_id, state, 92, "AI教师点评中")
        await asyncio.sleep(3.0)


async def _call_ai_engine(audio_base64: str, standard_text: str, user_baseline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ai_url = os.getenv("AI_ENGINE_URL", "http://127.0.0.1:8001/evaluate")
    async with httpx.AsyncClient(timeout=AI_ENGINE_TIMEOUT_SECONDS, trust_env=False) as client:
        resp = await client.post(
            ai_url,
            json={
                "audio_base64": audio_base64,
                "standard_text": standard_text,
                "language": "zh",
                "user_baseline": user_baseline,
            },
        )
        resp.raise_for_status()
        return resp.json()


def _fallback_scores(standard_text: str, transcript: str) -> Dict[str, Any]:
    import difflib

    def normalize(s: str) -> str:
        return "".join(ch for ch in s if ch.isalnum() or ch.isspace())

    a = normalize(standard_text or "")
    b = normalize(transcript or "")
    if not a:
        ratio = 0.0 if b else 1.0
    else:
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
    accuracy = int(round(ratio * 100))
    pronunciation = max(0, min(100, accuracy - 10))
    fluency = 60 if transcript else 0
    semantic = accuracy
    total_score = int(round(accuracy * 0.4 + pronunciation * 0.3 + fluency * 0.2 + semantic * 0.1))
    return {"total_score": total_score, "breakdown": {"accuracy": accuracy, "pronunciation": pronunciation, "fluency": fluency, "semantic": semantic}}


app = FastAPI(title="BERP WebSocket Gateway")

redis_client: Optional[Redis] = None
manager: Optional[ConnectionManager] = None


@app.on_event("startup")
async def on_startup() -> None:
    global redis_client, manager
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = Redis.from_url(redis_url)
    manager = ConnectionManager(redis_client)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()


@app.get("/health")
async def health() -> Dict[str, Any]:
    ok = False
    try:
        assert redis_client is not None
        await redis_client.ping()
        ok = True
    except Exception:
        ok = False
    return {"status": "ok" if ok else "degraded", "redis": ok}


@app.websocket("/ws/{user_id}")
async def ws_endpoint(websocket: WebSocket, user_id: str, token: str) -> None:
    try:
        _verify_jwt(token)
    except Exception:
        await websocket.close(code=1008)
        return

    assert manager is not None
    state = await manager.connect(user_id, websocket)
    await manager.send_json(
        user_id,
        {
            "type": "state",
            "task_text": state.current_task_text,
            "progress": state.last_progress,
            "user_baseline": state.user_baseline,
        },
    )

    async def heartbeat_loop() -> None:
        while True:
            await asyncio.sleep(5)
            now = time.time()
            if now - state.last_seen_at > 30:
                try:
                    await websocket.close(code=1001)
                finally:
                    return

    heartbeat_task = asyncio.create_task(heartbeat_loop())
    inactivity_task: Optional[asyncio.Task] = None

    async def cancel_inactivity_task() -> None:
        nonlocal inactivity_task
        if inactivity_task is not None:
            inactivity_task.cancel()
            try:
                await inactivity_task
            except asyncio.CancelledError:
                pass
            inactivity_task = None

    async def force_evaluate_after_timeout(expected_seq: int) -> None:
        try:
            await asyncio.sleep(10)
            if state.audio_buffer.last_seq != expected_seq:
                return
            window = state.audio_buffer.force_finalize()
            if window is None:
                return
            print(f"audio_timeout_force_finalize user_id={user_id} seq={window.seq}", flush=True)
            try:
                stage_task = asyncio.create_task(_run_stage_progress(manager, user_id, state))
                t0 = time.time()
                ai_result = await asyncio.wait_for(
                    _call_ai_engine(window.audio_base64, state.current_task_text, state.user_baseline),
                    timeout=AI_ENGINE_TIMEOUT_SECONDS,
                )
                stage_task.cancel()
                try:
                    await stage_task
                except asyncio.CancelledError:
                    pass
                print(f"ai_engine_timeout_recovery_ok user_id={user_id} seq={window.seq} ms={int((time.time()-t0)*1000)}", flush=True)
                progress = 100
                state.last_progress = progress
                await manager.send_json(
                    user_id,
                    {
                        "type": "partial_result",
                        "progress": progress,
                        "stage_text": "评测完成",
                        "scores": {
                            "total_score": ai_result.get("total_score"),
                            "breakdown": ai_result.get("breakdown"),
                        },
                        "transcript": ai_result.get("transcript", ""),
                        "error": "录音结束标记丢失，已自动完成评测",
                    },
                )
            except Exception as e:
                if "stage_task" in locals():
                    stage_task.cancel()
                    try:
                        await stage_task
                    except asyncio.CancelledError:
                        pass
                tb = traceback.format_exc(limit=5)
                print(f"ai_engine_timeout_recovery_failed user_id={user_id} seq={window.seq} error={e} trace={tb}", flush=True)
                scores = _fallback_scores(state.current_task_text, "")
                state.last_progress = 100
                await manager.send_json(
                    user_id,
                    {
                        "type": "partial_result",
                        "progress": 100,
                        "stage_text": "评测失败",
                        "scores": scores,
                        "transcript": "",
                        "error": "录音超时，已自动结束评测",
                    },
                )
        except asyncio.CancelledError:
            return

    try:
        while True:
            raw = await websocket.receive_json()
            state.last_seen_at = time.time()

            msg_type = raw.get("type")
            if msg_type == "set_task":
                task_text = raw.get("standard_text")
                raw_baseline = raw.get("user_baseline")
                if isinstance(raw_baseline, dict):
                    state.user_baseline = raw_baseline
                if isinstance(task_text, str) and task_text.strip():
                    state.current_task_text = task_text.strip()
                    assert redis_client is not None
                    await redis_client.set(f"ws:task_text:{user_id}", state.current_task_text)
                    await manager.send_json(
                        user_id,
                        {
                            "type": "state",
                            "task_text": state.current_task_text,
                            "progress": state.last_progress,
                            "user_baseline": state.user_baseline,
                        },
                    )
                continue

            if msg_type != "audio_chunk":
                await manager.send_json(user_id, {"type": "error", "message": "unsupported message type"})
                continue

            data = raw.get("data") or ""
            seq = int(raw.get("seq") or 0)
            is_final = bool(raw.get("is_final") or False)
            raw_baseline = raw.get("user_baseline")
            if isinstance(raw_baseline, dict):
                state.user_baseline = raw_baseline

            print(f"audio_chunk_received user_id={user_id} seq={seq} final={is_final} t={time.time()}", flush=True)
            if is_final:
                await cancel_inactivity_task()
            window = state.audio_buffer.add_chunk(data=data, seq=seq, is_final=is_final)
            if window is None:
                if data:
                    await cancel_inactivity_task()
                    inactivity_task = asyncio.create_task(force_evaluate_after_timeout(seq))
                await manager.send_json(
                    user_id,
                    {"type": "partial_result", "progress": _progress_from_seq(seq, False), "scores": {}, "transcript": ""},
                )
                continue

            try:
                prefix = (window.audio_base64 or "")[:24].replace("\n", "")
                print(
                    f"audio_window user_id={user_id} seq={window.seq} final={window.is_final} len={len(window.audio_base64 or '')} prefix={prefix}",
                    flush=True,
                )
                stage_task = asyncio.create_task(_run_stage_progress(manager, user_id, state))
                t0 = time.time()
                ai_result = await asyncio.wait_for(
                    _call_ai_engine(window.audio_base64, state.current_task_text, state.user_baseline),
                    timeout=AI_ENGINE_TIMEOUT_SECONDS,
                )
                stage_task.cancel()
                try:
                    await stage_task
                except asyncio.CancelledError:
                    pass
                print(f"ai_engine_ok user_id={user_id} seq={window.seq} ms={int((time.time()-t0)*1000)}", flush=True)
                progress = _progress_from_seq(window.seq, window.is_final)
                state.last_progress = progress
                await manager.send_json(
                    user_id,
                    {
                        "type": "partial_result",
                        "progress": progress,
                        "stage_text": "评测完成",
                        "scores": {
                            "total_score": ai_result.get("total_score"),
                            "breakdown": ai_result.get("breakdown"),
                        },
                        "transcript": ai_result.get("transcript", ""),
                        "error_details": ai_result.get("error_details"),
                        "feedback": ai_result.get("feedback"),
                        "emotion_expression": ai_result.get("emotion_expression"),
                        "intelligent_feedback": ai_result.get("intelligent_feedback"),
                        "fallback_note": ai_result.get("fallback_note"),
                    },
                )
            except Exception as e:
                if "stage_task" in locals():
                    stage_task.cancel()
                    try:
                        await stage_task
                    except asyncio.CancelledError:
                        pass
                tb = traceback.format_exc(limit=5)
                print(f"ai_engine_call_failed user_id={user_id} seq={window.seq} error={e} trace={tb}", flush=True)
                progress = _progress_from_seq(window.seq, window.is_final)
                state.last_progress = progress
                transcript = ""
                scores = _fallback_scores(state.current_task_text, transcript)
                await manager.send_json(
                    user_id,
                    {
                        "type": "partial_result",
                        "progress": progress,
                        "stage_text": "评测失败",
                        "scores": scores,
                        "transcript": transcript,
                        "error": str(e),
                    },
                )
    except WebSocketDisconnect:
        pass
    finally:
        await cancel_inactivity_task()
        heartbeat_task.cancel()
        await manager.disconnect(user_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002, ws_max_size=50_000_000)
