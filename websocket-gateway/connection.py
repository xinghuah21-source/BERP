import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from fastapi import WebSocket
from redis.asyncio import Redis

from audio_buffer import AudioBuffer


@dataclass
class ConnectionState:
    user_id: str
    connected_at: float
    last_seen_at: float
    current_task_text: str
    user_baseline: Optional[Dict[str, Any]]
    audio_buffer: AudioBuffer
    last_progress: int


class ConnectionManager:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._active: Dict[str, WebSocket] = {}
        self._state: Dict[str, ConnectionState] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _lock(self, user_id: str) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    async def connect(self, user_id: str, websocket: WebSocket) -> ConnectionState:
        await websocket.accept()

        async with self._lock(user_id):
            self._active[user_id] = websocket
            task_text = await self._redis.get(f"ws:task_text:{user_id}")
            if task_text is None:
                task_text = "春眠不觉晓，处处闻啼鸟"
                await self._redis.set(f"ws:task_text:{user_id}", task_text)
            else:
                task_text = task_text.decode("utf-8", errors="ignore")

            last_progress_raw = await self._redis.get(f"ws:progress:{user_id}")
            last_progress = int(last_progress_raw.decode("utf-8")) if last_progress_raw else 0

            state = ConnectionState(
                user_id=user_id,
                connected_at=time.time(),
                last_seen_at=time.time(),
                current_task_text=task_text,
                user_baseline=None,
                audio_buffer=AudioBuffer(chunk_window_size=3),
                last_progress=last_progress,
            )
            self._state[user_id] = state
            return state

    async def disconnect(self, user_id: str) -> None:
        async with self._lock(user_id):
            self._active.pop(user_id, None)
            state = self._state.pop(user_id, None)
            if state is not None:
                await self._redis.set(f"ws:task_text:{user_id}", state.current_task_text)
                await self._redis.set(f"ws:progress:{user_id}", str(state.last_progress))

    async def send_json(self, user_id: str, payload: Dict[str, Any]) -> None:
        ws = self._active.get(user_id)
        if ws is None:
            return
        await ws.send_json(payload)

    def get_state(self, user_id: str) -> Optional[ConnectionState]:
        return self._state.get(user_id)
