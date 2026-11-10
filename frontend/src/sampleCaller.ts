// The "sample caller": committed demo WAVs streamed through the same WebSocket as the mic,
// paced like a live caller, and played out loud so the audience hears them.

import a1Stammered from "../../eval/data/demo/A1_stammered.wav?url";
import c1 from "../../eval/data/demo/C1.wav?url";
import c2 from "../../eval/data/demo/C2.wav?url";
import d1 from "../../eval/data/demo/D1.wav?url";
import r2 from "../../eval/data/demo/R2.wav?url";
import manifestCsv from "../../eval/data/demo/manifest.csv?raw";

export const SAMPLE_RATE = 16000;
export const FRAME_SAMPLES = 512; // 32 ms
export const FRAME_MS = (FRAME_SAMPLES / SAMPLE_RATE) * 1000;

// After each answer, send silence until the bot replies (a new state event).
// Capped just past the 6 s PROMPT so an answer the endpointer never ends can't stall the script.
const MAX_REPLY_WAIT_MS = 7000;
const MAX_REPLAYS = 3;

export interface Turn {
  label: string;
  file: string; // name in eval/data/demo/manifest.csv
  url: string;
}

export const SAMPLE_SCRIPT: Turn[] = [
  { label: "Account number, with a stammer", file: "A1_stammered.wav", url: a1Stammered },
  { label: "“No, it's 4 5 2 1 8 8 3 1” (correcting the read-back)", file: "C2.wav", url: c2 },
  { label: "“Yes, that's right”", file: "C1.wav", url: c1 },
  { label: "Date of birth", file: "D1.wav", url: d1 },
  { label: "“Yes, that's right”", file: "C1.wav", url: c1 },
  { label: "Reason for calling", file: "R2.wav", url: r2 },
];

export interface LoadedTurn extends Turn {
  pcm: Int16Array;
  /** When the caller stops speaking; the WAV may carry trailing silence after it. */
  trueEndMs: number;
}

export async function loadScript(turns: Turn[]): Promise<LoadedTurn[]> {
  const ends = trueEnds(manifestCsv);
  return Promise.all(
    turns.map(async (t) => {
      const res = await fetch(t.url);
      if (!res.ok) throw new Error(`Couldn't load ${t.url}`);
      const pcm = parseWav(await res.arrayBuffer());
      return { ...t, pcm, trueEndMs: ends.get(t.file) ?? (pcm.length / SAMPLE_RATE) * 1000 };
    }),
  );
}

/** file name -> true_end_ms, from the demo manifest. */
function trueEnds(csv: string): Map<string, number> {
  const [header, ...rows] = csv.trim().split(/\r?\n/).map(splitCsvLine);
  const file = header.indexOf("file");
  const end = header.indexOf("true_end_ms");
  return new Map(rows.map((r) => [r[file].replace(/^demo\//, ""), Number(r[end])]));
}

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') (cur += '"'), i++;
      else if (ch === '"') quoted = false;
      else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") out.push(cur), (cur = "");
    else cur += ch;
  }
  out.push(cur);
  return out;
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

/**
 * Plays the script once. Returns when it runs out, the Call is DONE, or it is aborted.
 *
 * Like a real caller who gets cut off: if the bot replies (a new state event) before the
 * clip has finished, the clip stops and the same answer is given again at the next question.
 * MAX_REPLAYS is only a safety stop; the dialogue hands over before it is reached.
 */
export async function runSampleCaller(script: LoadedTurn[], h: CallerHooks): Promise<void> {
  const stopped = () => h.signal.aborted || h.done();
  try {
    await waitUntil(() => h.stateCount() > 0, h.signal); // the greeting has arrived
    let replays = 0;
    for (let i = 0; i < script.length; ) {
      const turn = script[i];
      await h.botQuiet();
      if (stopped()) break;
      h.onTurn(replays ? `${turn.label} (cut off, saying it again)` : turn.label);
      const before = h.stateCount();
      const replied = () => h.stateCount() > before;
      let sentMs = 0;
      const playing = playOutLoud(h.audio, turn.pcm);
      await streamFrames(
        h,
        (k) => {
          if (k >= frameCount(turn.pcm)) return null;
          sentMs = k * FRAME_MS;
          return frameAt(turn.pcm, k);
        },
        () => stopped() || replied(),
      );
      playing.stop();
      if (stopped()) break;
      // A reply before the caller finished speaking is a cut-off; after it, a normal reply.
      const cutOff = replied() && sentMs < turn.trueEndMs;
      if (cutOff && replays < MAX_REPLAYS) {
        replays++;
        continue; // same answer, next question
      }
      i++;
      replays = 0;
      if (replied()) continue; // the bot has already answered this one
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
