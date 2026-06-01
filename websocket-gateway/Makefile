.PHONY: run test

PYTHON = E:\ANACONDA\envs\BERP\python.exe

run:
	$(PYTHON) main.py

test:
	$(PYTHON) -c "import asyncio, websockets, json; async def t():\n  token='';\n  async with websockets.connect(f'ws://localhost:8002/ws/test_user?token={token}') as ws:\n    await ws.send(json.dumps({'type':'audio_chunk','data':'test','seq':1,'is_final':False}));\n    print(await ws.recv());\nasyncio.run(t())"
