// AudioWorklet (runs on the audio thread): mic audio at the context's rate (usually 48 kHz)
// -> 16 kHz mono PCM16, posted to the main thread in 512-sample (32 ms) frames.
//
// Resampling is linear interpolation. It has no anti-alias filter, which is fine for speech
// going into an energy VAD and Vosk; a proper low-pass would be the next step if needed.

const TARGET_RATE = 16000;
const FRAME_SAMPLES = 512;

class Pcm16Frames extends AudioWorkletProcessor {
  constructor() {
    super();
    this.step = sampleRate / TARGET_RATE; // input samples per output sample (3 at 48 kHz)
    this.t = 0; // position of the next output sample, in input samples from this block's start
    this.prev = 0; // last input sample of the previous block (position -1)
    this.frame = new Int16Array(FRAME_SAMPLES);
    this.n = 0;
  }

  process(inputs) {
    const input = inputs[0][0]; // first channel only: the mic is mono
    if (!input || input.length === 0) return true;

    while (Math.floor(this.t) + 1 < input.length) {
      const i = Math.floor(this.t);
      const frac = this.t - i;
      const a = i < 0 ? this.prev : input[i];
      const b = input[i + 1];
      const x = Math.max(-1, Math.min(1, a + (b - a) * frac));
      this.frame[this.n++] = Math.round(x * 32767);
      if (this.n === FRAME_SAMPLES) {
        this.port.postMessage(this.frame.buffer, [this.frame.buffer]);
        this.frame = new Int16Array(FRAME_SAMPLES);
        this.n = 0;
      }
      this.t += this.step;
    }
    this.t -= input.length;
    this.prev = input[input.length - 1];
    return true;
  }
}

registerProcessor("pcm16-frames", Pcm16Frames);
