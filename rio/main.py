import json
import os, sys

from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse

from bot import main

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/")
async def start_call(request: Request):
    try:
        body = await request.body()
        print(f"Request body: {body}")
        file_path = os.path.join(os.path.dirname(__file__), "templates/streams.xml")
        return HTMLResponse(
            content=open(file_path).read(),  # Can try absolute path
            media_type="application/xml",
        )
    except Exception as e:
        print(f"Error parsing request: {e}")
        return HTMLResponse(content=f"Internal Server Error: {e}", status_code=500)


@app.websocket("/ws")
async def web_socket_connection(websocket: WebSocket):
    await websocket.accept()
    start_data = websocket.iter_text()
    await start_data.__anext__()
    call_data = json.loads(await start_data.__anext__())
    print(call_data, flush=True)
    stream_sid = call_data["start"]["streamSid"]
    print("Websocket connection accepted...")
    await main(websocket, stream_sid)
