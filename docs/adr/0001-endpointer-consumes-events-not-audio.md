# The Endpointer consumes an event stream, not audio

The Endpointer never sees raw audio. Its input is a timestamped stream of events (speech/silence from the VAD, and words from the STT). This lets the same Endpointer code run on symbolic synthetic timelines (thousands of Turns, faster than real time, used for tuning and headline numbers) and on the live pipeline and synthetic audio. The cost: any signal not in the event stream, such as pitch or the strain in a Block, is invisible to the Endpointer unless it is added as a new event type.

The Endpointer is also a pure state machine with no clock of its own: time arrives only through event timestamps, including periodic `Tick` events, so "silent for long enough" can be decided between other events. The live server sends real Ticks; the evaluation simulates them.
