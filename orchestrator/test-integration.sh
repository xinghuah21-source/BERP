#!/bin/bash
set -e

cd "$(dirname "$0")"

DC="docker compose -f docker-compose.full.yml"

echo "1. API健康检查..."
curl -f http://localhost/api/health >/dev/null
curl -f http://localhost/ai/health >/dev/null
echo "✓"

echo "2. 端到端测试..."
$DC exec -T websocket python -c "import asyncio, json, time; import httpx; import websockets; from jose import jwt; \
secret='your-secret-key-here'; \
token=jwt.encode({'sub':'test','exp':int(time.time())+3600}, secret, algorithm='HS256'); \
async def main(): \
  async with httpx.AsyncClient(base_url='http://nginx', timeout=20.0) as client: \
    r=await client.post('/api/auth/register', json={'username':'test','password':'123','role':'student','grade':3}); \
    if r.status_code >= 400: \
      r=await client.post('/api/auth/login', json={'username':'test','password':'123'}); \
    tok=r.json()['access_token']; \
    tasks=(await client.get('/api/tasks', headers={'Authorization':'Bearer '+tok})).json(); \
    assert isinstance(tasks, list) and len(tasks) >= 1; \
  uri=f'ws://nginx/ws/test_user?token={token}'; \
  async with websockets.connect(uri) as ws: \
    await ws.recv(); \
    await ws.send(json.dumps({'type':'audio_chunk','data':'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=','seq':1,'is_final':False})); \
    msg=json.loads(await ws.recv()); \
    assert msg.get('type')=='partial_result'; \
asyncio.run(main())"

echo "✓ 集成测试通过"
