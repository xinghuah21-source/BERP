import asyncio
import base64
import io
import json
import subprocess
import tempfile
import wave
from pathlib import Path
import sys
import urllib.request

import websockets

ROOT = Path(r'e:\game\BERP')
sys.path.insert(0, str(ROOT / 'verify'))
from ai_engine_path import import_ai_engine_evaluator

mod = import_ai_engine_evaluator()

STANDARD_YONGE = '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。'
STANDARD_JINGYESI = '床前明月光，疑是地上霜。举头望明月，低头思故乡。'


def post_ai(audio_path: Path, standard_text: str):
    mime = 'audio/wav' if audio_path.suffix.lower() == '.wav' else 'audio/webm'
    payload = {
        'audio_base64': f'data:{mime};base64,' + base64.b64encode(audio_path.read_bytes()).decode('utf-8'),
        'standard_text': standard_text,
        'language': 'zh',
    }
    req = urllib.request.Request('http://127.0.0.1:8001/evaluate', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode('utf-8'))


def score_core(standard_text: str, transcript: str):
    alignment = mod._summarize_alignment(standard_text, transcript)
    accuracy = mod._calculate_accuracy(standard_text, transcript)
    correct = alignment['correct']
    mis = alignment['mispronunciation']
    omission = alignment['omission']
    insertion = alignment['insertion']
    ref_len = max(1, alignment['ref_len'])
    accuracy_raw = (correct - (0.8 * mis) - (1.0 * omission) - (0.4 * insertion)) / ref_len
    accuracy_score = int(round(max(0.0, min(100.0, accuracy_raw * 100.0))))
    confidence = mod._resolve_asr_confidence(0.0, standard_text, transcript, alignment)
    pron_base = 60.0 + (40.0 * confidence)
    mis_ratio = mis / ref_len
    pron_penalty = min(35.0, mis_ratio * 100.0 * 0.6)
    pronunciation = int(round(max(0.0, min(100.0, pron_base - pron_penalty))))
    semantic, content = mod._compute_content_score(standard_text, transcript, alignment)
    errors = mod._generate_error_details(standard_text, transcript)
    return {
        'alignment': alignment,
        'accuracy_ratio': round(accuracy, 2),
        'confidence': confidence,
        'breakdown': {
            'accuracy': accuracy_score,
            'pronunciation': pronunciation,
            'fluency': None,
            'semantic': semantic,
        },
        'content': content,
        'error_details': errors,
    }


def pcm16_from_audio(path: Path) -> bytes:
    ffmpeg = ROOT / 'ai-engine' / 'ffmpeg' / 'ffmpeg-master-latest-win64-gpl' / 'bin' / 'ffmpeg.exe'
    fd_out, path_out = tempfile.mkstemp(suffix='.pcm')
    Path(path_out).unlink(missing_ok=True)
    try:
        proc = subprocess.run([str(ffmpeg), '-y', '-hide_banner', '-loglevel', 'error', '-i', str(path), '-ac', '1', '-ar', '16000', '-f', 's16le', path_out], capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode('utf-8', 'replace'))
        return Path(path_out).read_bytes()
    finally:
        Path(path_out).unlink(missing_ok=True)


def wav_bytes_from_pcm(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def make_audio_data_url_from_pcm(pcm: bytes) -> str:
    return 'data:audio/wav;base64,' + base64.b64encode(wav_bytes_from_pcm(pcm)).decode('utf-8')


def fluency_from_audio(audio_path: Path, standard_text: str, transcript: str):
    pcm = pcm16_from_audio(audio_path)
    duration = len(pcm) / 32000.0
    return mod._compute_fluency_score(
        pcm_bytes=pcm,
        raw_transcript=transcript,
        cleaned_transcript=transcript,
        standard_text=standard_text,
        duration=duration,
    )


async def ws_progress_case(audio_path: Path, standard_text: str):
    pcm = pcm16_from_audio(audio_path)
    chunk_size = max(1, len(pcm) // 3)
    chunks = [pcm[i:i+chunk_size] for i in range(0, len(pcm), chunk_size)]
    if len(chunks) > 3:
        chunks = chunks[:2] + [b''.join(chunks[2:])]
    uri = 'ws://127.0.0.1:8002/ws/tester?token=test'
    messages = []
    async with websockets.connect(uri, max_size=50_000_000) as ws:
        init_msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        messages.append(init_msg)
        await ws.send(json.dumps({'type': 'set_task', 'standard_text': standard_text}))
        for idx, chunk in enumerate(chunks, start=1):
            await ws.send(json.dumps({'type': 'audio_chunk', 'seq': idx, 'is_final': idx == len(chunks), 'data': make_audio_data_url_from_pcm(chunk)}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
            messages.append(msg)
            if msg.get('type') == 'partial_result' and msg.get('progress') == 100:
                break
    partials = [m for m in messages if m.get('type') == 'partial_result']
    return {
        'message_count': len(messages),
        'progresses': [m.get('progress') for m in partials],
        'final': partials[-1] if partials else None,
    }


results = {}

# TC-EVAL-01 标准背诵真实链路
case1 = post_ai(ROOT / 'YongE.wav', STANDARD_YONGE)
results['TC-EVAL-01'] = {
    'mode': 'HTTP真实评测',
    'transcript': case1.get('transcript'),
    'breakdown': case1.get('breakdown'),
    'total_score': case1.get('total_score'),
    'feedback': case1.get('feedback'),
}

# TC-EVAL-02 部分错读
case2 = score_core(STANDARD_JINGYESI, '床前明月光，疑是地上霜。举头忘明月，低头思故乡。')
results['TC-EVAL-02'] = {
    'mode': '本地评分核心函数',
    'transcript': '床前明月光，疑是地上霜。举头忘明月，低头思故乡。',
    'breakdown': case2['breakdown'],
    'error_head': case2['error_details'][0] if case2['error_details'] else None,
}

# TC-EVAL-03 漏读句子
case3 = score_core(STANDARD_JINGYESI, '床前明月光，疑是地上霜')
results['TC-EVAL-03'] = {
    'mode': '本地评分核心函数',
    'transcript': '床前明月光，疑是地上霜',
    'breakdown': case3['breakdown'],
    'coverage_ratio': case3['content']['coverage_ratio'],
    'error_head': case3['error_details'][0] if case3['error_details'] else None,
}

# TC-EVAL-04 多读内容
case4 = score_core(STANDARD_YONGE, '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。红掌拨清波。')
results['TC-EVAL-04'] = {
    'mode': '本地评分核心函数',
    'transcript': '鹅鹅鹅，曲项向天歌。白毛浮绿水，红掌拨清波。红掌拨清波。',
    'breakdown': case4['breakdown'],
    'error_head': case4['error_details'][0] if case4['error_details'] else None,
}

# TC-EVAL-05 语速过慢（真实音频）
slow_audio = ROOT / 'test_video' / 'yonge1.wav'
slow_obj = post_ai(slow_audio, STANDARD_YONGE)
results['TC-EVAL-05'] = {
    'mode': 'HTTP真实评测',
    'file': slow_audio.name,
    'transcript': slow_obj.get('transcript'),
    'breakdown': slow_obj.get('breakdown'),
    'feedback': slow_obj.get('feedback'),
}

# TC-EVAL-06 语速过快（真实音频）
fast_audio = ROOT / 'test_video' / 'yonge2.webm'
fast_obj = post_ai(fast_audio, STANDARD_YONGE)
results['TC-EVAL-06'] = {
    'mode': 'HTTP真实评测',
    'file': fast_audio.name,
    'transcript': fast_obj.get('transcript'),
    'breakdown': fast_obj.get('breakdown'),
    'feedback': fast_obj.get('feedback'),
}

# TC-EVAL-07 评测进度反馈（WebSocket真实链路）
results['TC-EVAL-07'] = asyncio.run(ws_progress_case(ROOT / 'YongE.wav', STANDARD_YONGE))

out = ROOT / 'verify' / 'tc_eval_batch_results.json'
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False, indent=2))
