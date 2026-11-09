# The Endpointer consumes an event stream, not audio

The Endpointer never sees raw audio. Its input is a timestamped stream of events (speech/silence from the VAD, and words from the STT). This lets the same Endpointer code run on symbolic synthetic timelines (thousands of Turns, faster than real time, used for tuning and headline numbers) and on the live pipeline and synthetic audio. The cost: any signal not in the event stream, such as pitch or the strain in a Block, is invisible to the Endpointer unless it is added as a new event type.

The Endpointer is also a pure state machine with no clock of its own: time arrives only through event timestamps, including periodic `Tick` events, so "silent for long enough" can be decided between other events. The live server sends real Ticks; the evaluation simulates them.

## Implementation note (demo, ticket 01)

For the demo, the event stream is simplified to one call per VAD frame: `Endpointer.step(is_speech, frame_ms, transcript)` returns a `Decision`, and `reset()` starts a new Turn. Each 32 ms frame (512 samples at 16 kHz) works as both the speech/silence event and the Tick: time moves forward only by the `frame_ms` passed in, so the Endpointer still has no clock of its own, and the evaluation can replay frames faster than real time. Words come in as the latest partial `transcript` on each frame, not as separate timestamped word events. If a later Endpointer needs exact word timings or events between frames, the interface can grow back toward the full event stream.
