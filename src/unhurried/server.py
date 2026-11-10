"""FastAPI WebSocket around a Session (ticket 07). Only bytes and JSON in and out; the Call lives in Session.

    uv run uvicorn unhurried.server:app

WS /ws?endpointer=patient|baseline (the demo toggle; patient by default).
  client -> server  binary: 16 kHz mono PCM16 little-endian, any length
                    text:   {"type": "keypad", "digits": "45218830"}
  server -> client  text:   one JSON event per message (see session.py)

STT runs in a worker thread (asyncio.to_thread) so Vosk doesn't block the event loop.
"""

from __future__ import annotations

import asyncio
import json
from typing import Callable

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from unhurried.endpointer.baseline import Baseline
from unhurried.endpointer.patient import Patient
from unhurried.endpointer.types import Endpointer
from unhurried.session import Dialogue, Session
from unhurried.stt import STT

ENDPOINTERS: dict[str, Callable[[], Endpointer]] = {"patient": Patient, "baseline": Baseline}


def default_stt() -> STT:
    from unhurried.stt import VoskSTT
    return VoskSTT()


def default_dialogue() -> Dialogue:
    from unhurried.dialogue import Dialogue as RealDialogue
    return RealDialogue()


def pcm16_to_float(data: bytes) -> np.ndarray:
    """Inverse of stt.to_pcm16; the same scaling as eval.audio.read_wav."""
    return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0


def create_app(make_stt: Callable[[], STT] = default_stt,
               make_dialogue: Callable[[], Dialogue] = default_dialogue) -> FastAPI:
    app = FastAPI(title="Unhurried")

    @app.websocket("/ws")
    async def call(ws: WebSocket, endpointer: str = "patient") -> None:
        if endpointer not in ENDPOINTERS:
            await ws.close(code=1008, reason=f"endpointer must be one of {sorted(ENDPOINTERS)}")
            return
        await ws.accept()
        stt = await asyncio.to_thread(make_stt)   # loading the Vosk model takes about a second
        session = Session(ENDPOINTERS[endpointer](), stt, make_dialogue())

        async def send(events: list[dict]) -> None:
            for event in events:
                await ws.send_text(json.dumps(event))

        try:
            await send(session.start())
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    await send(await asyncio.to_thread(session.feed, pcm16_to_float(message["bytes"])))
                elif message.get("text") is not None:
                    data = json.loads(message["text"])
                    if data.get("type") == "keypad":
                        await send(session.keypad(str(data.get("digits", ""))))
        except WebSocketDisconnect:
            pass

    return app


app = create_app()
