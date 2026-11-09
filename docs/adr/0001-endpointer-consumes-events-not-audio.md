# The Endpointer consumes VAD frames, not audio

The Endpointer never sees raw audio. Its input is one call per VAD frame: `Endpointer.step(is_speech, frame_ms, transcript)` returns a `Decision` (`CONTINUE`, `END` or `PROMPT`, with a reason), and `reset()` starts a new Turn. Frames are 32 ms (512 samples at 16 kHz). `is_speech` comes from the VAD and `transcript` is the latest partial transcript of the current Turn from the STT.

This lets the same Endpointer code run on the evaluation (recorded clips replayed frame by frame, faster than real time, used for tuning and headline numbers) and on the live pipeline. The cost: any signal not in the frame input, such as pitch or the strain in a Block, is invisible to the Endpointer unless it is added as a new argument.

The Endpointer is also a pure state machine with no clock of its own. Each frame is both the speech/silence signal and the tick: time moves forward only by the `frame_ms` passed in, so "silent for long enough" is decided by counting frames. The live server calls `step()` once per incoming audio frame; the evaluation replays frames from a WAV with no real waiting.

## Considered: a timestamped event stream

The first design fed the Endpointer timestamped events (`SpeechStarted`, `SpeechEnded`, `Words`, plus periodic `Tick` events so silence could be measured between other events). It was simplified to per-frame calls for the demo (ticket 01): one call shape is easier to test and to replay, and 32 ms resolution is fine for endpointing. Words arrive as the latest partial transcript on each frame rather than as separate word events. If a later Endpointer needs exact word timings or decisions between frames, the interface can grow back toward the event stream.
