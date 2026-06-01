import asyncio
import base64
import io
import json
import subprocess
import tempfile
import wave
from pathlib import Path
import websockets

ROOT = Path(r'e:\game\BERP')
ffmpeg = ROOT / 'ai-engine' / 'ffmpeg' / 'ffmpeg-master-latest-win64-gpl' / 'bin' / 'ffmpeg.exe'


def pcm16_from_audio(path: Path) -> bytes:
    fd_out, path_out = tempfile.mkstemp(suffix='.pcm')
    try:
        import os
        os.close(fd_out)
        proc = subprocess.run([str(ffmpeg), '-y', '-hide_banner', '-loglevel', 'error', '-i', str(path), '-ac', '1', '-ar', '16000', '-f', 's16le', path_out], capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode('utf-8', 'replace'))
        return Path(path_out).read_bytes()
    finally:
        try:
            Path(path_out).unlink()
        except Exception:
            pass


def wav_bytes_from_pcm(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def data_url_from_pcm(pcm: bytes) -> str:
    return 'data:audio/wav;base64,' + base64.b64encode(wav_bytes_from_pcm(pcm)).decode('utf-8')


async def main():
    path = ROOT / 'YongE.wav'
    standard = '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'
    pcm = pcm16_from_audio(path)
    chunk_size = max(1, len(pcm) // 3)
    chunks = [pcm[i:i+chunk_size] for i in range(0, len(pcm), chunk_size)]
    if len(chunks) > 3:
        chunks = chunks[:2] + [b''.join(chunks[2:])]
    uri = 'ws://127.0.0.1:8002/ws/tester?token=test'
    msgs = []
    async with websockets.connect(uri, max_size=50_000_000) as ws:
        msgs.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=10)))
        await ws.send(json.dumps({'type':'set_task','standard_text':standard}))
        for idx, chunk in enumerate(chunks, start=1):
            await ws.send(json.dumps({'type':'audio_chunk','seq':idx,'is_final':idx==len(chunks),'data':data_url_from_pcm(chunk)}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
            msgs.append(msg)
            if msg.get('type') == 'partial_result' and msg.get('progress') == 100:
                break
    partials = [m for m in msgs if m.get('type') == 'partial_result']
    out = {
        'message_count': len(msgs),
        'progresses': [m.get('progress') for m in partials],
        'final_feedback': (partials[-1].get('feedback') if partials else None),
        'final_transcript': (partials[-1].get('transcript') if partials else None),
    }
    Path(r'e:\game\BERP\verify\tc_eval_ws_progress.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))

asyncio.run(main())
