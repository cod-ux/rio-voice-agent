import json
import os, sys

from fastapi import FastAPI, WebSocket, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse

from twilio.twiml.voice_response import VoiceResponse

from bot import main

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/twilio-webhook")
def twilio_webhook():
    print("Post TwiML...")
    return HTMLResponse(
        content=open("templates/streams.xml").read(), media_type="application/xml"
    )


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
