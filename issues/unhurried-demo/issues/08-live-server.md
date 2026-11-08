# Live pipeline server

Status: ready-for-agent
Blocked by: 01, 07

## What

FastAPI WebSocket that receives 16 kHz PCM from the browser and runs it through Silero VAD and Vosk streaming to produce events, sending real Ticks. It drives the selected Endpointer (Baseline or Unhurried, switchable per Call), then Cleanup and Dialogue, and sends back the Prompt text plus the timeline events for the UI. Barge-in: speech during system playback sends a "stop" message and continues the Turn. Vosk finals are transcript chunks only, never Turn ends (ADR 0002).

## Acceptance

`uv run unhurried` starts the server. A recorded WAV can be pushed through a test client and produces a sensible Endpoint.
