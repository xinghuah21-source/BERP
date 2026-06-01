import base64, datetime, hashlib, hmac, json, ssl, time, tempfile, subprocess, os
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from pathlib import Path
import websocket

app_id = 'e0044bde'
api_key = 'd67ab83d7b5a0682f9ed05c6ae354d42'
api_secret = 'NTQyYjQ1ZDRkOWFhMDU4YzA3MWM3YTg3'
ffmpeg = r'e:\game\BERP\ai-engine\ffmpeg\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe'


def create_ws_url(api_key, api_secret):
    base_url = 'wss://iat-api.xfyun.cn/v2/iat'
    now = datetime.datetime.now()
    date = format_date_time(time.mktime(now.timetuple()))
    signature_origin = 'host: iat-api.xfyun.cn\n' + 'date: ' + date + '\n' + 'GET /v2/iat HTTP/1.1'
    signature_sha = hmac.new(api_secret.encode('utf-8'), signature_origin.encode('utf-8'), digestmod=hashlib.sha256).digest()
    signature_sha = base64.b64encode(signature_sha).decode('utf-8')
    authorization_origin = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
    authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
    return base_url + '?' + urlencode({'authorization': authorization, 'date': date, 'host': 'iat-api.xfyun.cn'})


def wav_to_pcm(path: Path) -> bytes:
    fd_out, path_out = tempfile.mkstemp(suffix='.pcm')
    os.close(fd_out)
    try:
        proc = subprocess.run([ffmpeg,'-y','-hide_banner','-loglevel','error','-i',str(path),'-ac','1','-ar','16000','-f','s16le',path_out], capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode('utf-8','replace'))
        return Path(path_out).read_bytes()
    finally:
        try: os.remove(path_out)
        except: pass

pcm = wav_to_pcm(Path(r'e:\game\BERP\YongE.wav'))
url = create_ws_url(api_key, api_secret)
messages = []

def on_message(ws, message):
    msg = json.loads(message)
    messages.append(msg)
    print('MSG', len(messages))
    print(json.dumps(msg, ensure_ascii=False, indent=2)[:7000])
    status = ((msg.get('data') or {}).get('status'))
    if status == 2:
        ws.close()

def on_error(ws, error):
    print('ERR', repr(error))

ws = websocket.WebSocketApp(url, on_message=on_message, on_error=on_error)

def on_open(_ws):
    frame_bytes = 40960
    pos = 0
    status = 0
    while True:
        chunk = pcm[pos:pos+frame_bytes]
        pos += len(chunk)
        audio_b64 = base64.b64encode(chunk).decode('utf-8')
        if not chunk:
            status = 2
        if status == 0:
            payload = {
                'common': {'app_id': app_id},
                'business': {'language': 'zh_cn', 'domain': 'iat', 'accent': 'mandarin', 'vinfo': 1, 'pd': 'edu', 'ptt': 1},
                'data': {'status': 0, 'format': 'audio/L16;rate=16000', 'encoding': 'raw', 'audio': audio_b64},
            }
            ws.send(json.dumps(payload))
            status = 1
        elif status == 1:
            ws.send(json.dumps({'data': {'status': 1, 'format': 'audio/L16;rate=16000', 'encoding': 'raw', 'audio': audio_b64}}))
        else:
            ws.send(json.dumps({'data': {'status': 2, 'format': 'audio/L16;rate=16000', 'encoding': 'raw', 'audio': audio_b64}}))
            break

ws.on_open = on_open
ws.run_forever(sslopt={'cert_reqs': ssl.CERT_NONE}, ping_interval=15, ping_timeout=5)
print('TOTAL_MSGS', len(messages))
