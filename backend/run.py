import uvicorn
import sys
import asyncio
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
