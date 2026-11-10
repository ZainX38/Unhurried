// The "sample caller": committed demo WAVs streamed through the same WebSocket as the mic,
// paced like a live caller, and played out loud so the audience hears them.

import a1Stammered from "../../eval/data/demo/A1_stammered.wav?url";
import c1 from "../../eval/data/demo/C1.wav?url";
import c2 from "../../eval/data/demo/C2.wav?url";
import d1 from "../../eval/data/demo/D1.wav?url";
import r2 from "../../eval/data/demo/R2.wav?url";

export const SAMPLE_RATE = 16000;
export const FRAME_SAMPLES = 512; // 32 ms
export const FRAME_MS = (FRAME_SAMPLES / SAMPLE_RATE) * 1000;

// After each answer, send silence until the bot replies (a new state event).
// Capped just past the 6 s PROMPT so an answer the endpointer never ends can't stall the script.
const MAX_REPLY_WAIT_MS = 7000;

export interface Turn {
  label: string;
  url: string;
}

export const SAMPLE_SCRIPT: Turn[] = [
  { label: "Account number, with a stammer", url: a1Stammered },
  { label: "“No, it's 4 5 2 1 8 8 3 1” (correcting the read-back)", url: c2 },
  { label: "“Yes, that's right”", url: c1 },
  { label: "Date of birth", url: d1 },
  { label: "“Yes, that's right”", url: c1 },
  { label: "Reason for calling", url: r2 },
];

export interface LoadedTurn extends Turn {
  pcm: Int16Array;
}

export async function loadScript(turns: Turn[]): Promise<LoadedTurn[]> {
  return Promise.all(
    turns.map(async (t) => {
      const res = await fetch(t.url);
      if (!res.ok) throw new Error(`Couldn't load ${t.url}`);
      return { ...t, pcm: parseWav(await res.arrayBuffer()) };
    }),
  );
}

/** The samples of a 16 kHz mono PCM16 WAV. Read directly: decodeAudioData would resample. */
export function parseWav(buf: ArrayBuffer): Int16Array {
  const view = new DataView(buf);
  const tag = (at: number) => String.fromCharCode(...new Uint8Array(buf, at, 4));
  if (tag(0) !== "RIFF" || tag(8) !== "WAVE") throw new Error("Not a WAV file");
  let at = 12;
  while (at + 8 <= buf.byteLength) {
    const id = tag(at);
    const size = view.getUint32(at + 4, true);
    if (id === "fmt ") {
      const channels = view.getUint16(at + 10, true);
      const rate = view.getUint32(at + 12, true);
      const bits = view.getUint16(at + 22, true);
      if (channels !== 1 || rate !== SAMPLE_RATE || bits !== 16)
        throw new Error(`Expected 16 kHz mono PCM16, got ${rate} Hz, ${channels} ch, ${bits}-bit`);
    } else if (id === "data") {
      return new Int16Array(buf.slice(at + 8, at + 8 + size)); // slice: aligned copy
    }
    at += 8 + size + (size % 2);
  }
  throw new Error("WAV has no data chunk");
}

export interface CallerHooks {
  sendPcm(frame: Int16Array): void;
  /** Counts state events so far; a new one means the bot has replied. */
  stateCount(): number;
  done(): boolean;
  botQuiet(): Promise<void>;
  onTurn(label: string | null): void;
  audio: AudioContext;
  signal: AbortSignal;
}

/** Plays the script once. Returns when it runs out, the Call is DONE, or it is aborted. */
export async function runSampleCaller(script: LoadedTurn[], h: CallerHooks): Promise<void> {
  const stopped = () => h.signal.aborted || h.done();
  try {
    await waitUntil(() => h.stateCount() > 0, h.signal); // the greeting has arrived
    for (const turn of script) {
      await h.botQuiet();
      if (stopped()) break;
      h.onTurn(turn.label);
      const playing = playOutLoud(h.audio, turn.pcm);
      await streamFrames(h, (k) => (k < frameCount(turn.pcm) ? frameAt(turn.pcm, k) : null), stopped);
      playing.stop();
      if (stopped()) break;
      // Silence until the bot answers this Turn (or the cap passes).
      const afterAudio = h.stateCount();
      const maxFrames = Math.ceil(MAX_REPLY_WAIT_MS / FRAME_MS);
      const silence = new Int16Array(FRAME_SAMPLES);
      await streamFrames(
        h,
        (k) => (k < maxFrames ? silence : null),
        () => stopped() || h.stateCount() > afterAudio,
      );
      if (stopped()) break;
    }
  } finally {
    h.onTurn(null);
  }
}

const frameCount = (pcm: Int16Array) => Math.floor(pcm.length / FRAME_SAMPLES);
const frameAt = (pcm: Int16Array, k: number) =>
  pcm.subarray(k * FRAME_SAMPLES, (k + 1) * FRAME_SAMPLES);

/** Sends frame k at start + k * 32 ms; catches up if a timer fires late. */
async function streamFrames(
  h: CallerHooks,
  frame: (k: number) => Int16Array | null,
  stop: () => boolean,
): Promise<void> {
  const start = performance.now();
  let k = 0;
  for (;;) {
    while (k * FRAME_MS <= performance.now() - start) {
      if (stop()) return;
      const f = frame(k);
      if (!f) return;
      h.sendPcm(f);
      k++;
    }
    await sleep(FRAME_MS / 2);
  }
}

function playOutLoud(ctx: AudioContext, pcm: Int16Array): { stop(): void } {
  const buffer = ctx.createBuffer(1, pcm.length, SAMPLE_RATE);
  const ch = buffer.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 32768;
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(ctx.destination);
  src.start();
  return {
    stop() {
      try {
        src.stop();
      } catch {
        /* already finished */
      }
    },
  };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function waitUntil(cond: () => boolean, signal: AbortSignal): Promise<void> {
  while (!cond() && !signal.aborted) await sleep(50);
}
