# Vosk for speech-to-text, not Whisper

We use Vosk (local, streaming) rather than Whisper or a cloud STT. The Endpointer needs words *while* the caller is speaking, and Vosk streams partial transcripts, while Whisper has to re-transcribe at every pause. Vosk also transcribes repetitions literally, whereas Whisper tends to quietly remove them (which would hide whether our own Cleanup works) and to invent words during long silences, which is exactly what Blocks are. Vosk is also local and needs no API keys, so reviewers can run Unhurried without an account. We accept lower raw accuracy than Whisper or cloud STT.

## Consequences

Vosk has its own internal silence-based segmentation that emits "final" results. These are treated only as transcript chunks and never as Turn ends: only the Endpointer decides Endpoints.
