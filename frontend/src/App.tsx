import { useEffect, useReducer, useRef, useState } from "react";
import { openCall, type Call, type Decision, type Mode, type ServerEvent } from "./call";
import { BotVoice } from "./voice";
import { SAMPLE_SCRIPT, loadScript, runSampleCaller, type LoadedTurn } from "./sampleCaller";
import { Keypad } from "./Keypad";
import { startMic } from "./mic";

// Keep the mic muted this long after the bot stops, for the speaker tail and room echo.
const MUTE_TAIL_MS = 300;

type Source = "sample" | "mic";

interface View {
  inCall: boolean;
  status: string;
  transcript: string; // raw: what the endpointer reads
  clean: string; // cleaned: what the caller meant
  now: Decision | null; // the latest decision (one per 32 ms frame)
  lastStop: Decision | null; // the latest END or PROMPT, which only lasts one frame in `now`
  botLines: string[];
  state: string;
  expectedSlot: string;
  slots: Record<string, string>;
  turnLabel: string | null;
}

const EMPTY: View = {
  inCall: false, status: "", transcript: "", clean: "", now: null, lastStop: null,
  botLines: [], state: "", expectedSlot: "", slots: {}, turnLabel: null,
};

type Msg =
  | { kind: "start"; status: string }
  | { kind: "end"; status: string }
  | { kind: "event"; e: ServerEvent }
  | { kind: "turn"; label: string | null };

function reduce(v: View, m: Msg): View {
  switch (m.kind) {
    case "start":
      return { ...EMPTY, inCall: true, status: m.status };
    case "end":
      return { ...v, inCall: false, status: m.status, turnLabel: null };
    case "turn":
      return { ...v, turnLabel: m.label };
    case "event": {
      const e = m.e;
      if (e.type === "transcript") return { ...v, transcript: e.text, clean: e.clean };
      if (e.type === "bot") return { ...v, botLines: [...v.botLines, e.line] };
      if (e.type === "state")
        return {
          ...v, state: e.state, expectedSlot: e.expected_slot, slots: e.slots, transcript: "", clean: "",
          status: e.state === "DONE" ? "Call finished." : v.status,
        };
      const d: Decision = { action: e.action, reason: e.reason, t_ms: e.t_ms };
      return { ...v, now: d, lastStop: d.action === "CONTINUE" ? v.lastStop : d };
    }
  }
}

const MODE_LABEL: Record<Mode, string> = { baseline: "Baseline", patient: "Unhurried" };
const MODE_HINT: Record<Mode, string> = {
  baseline: "Ends your turn after 0.7 s of silence, like most voice bots.",
  patient: "Waits through pauses until your answer is complete.",
};
const ACTION_LABEL = { CONTINUE: "Listening", END: "Turn ended", PROMPT: "Still listening" } as const;
const SLOT_LABEL: Record<string, string> = {
  account_number: "your account number",
  date_of_birth: "your date of birth",
  confirm: "a yes or no",
  reason: "your reason for calling",
};

const secs = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

// Silence as a share of patience, read from the reason the panel already shows
// ("silence 400ms < patience 1700ms", or Baseline's "silence 400ms < 700ms"). null hides the bar.
function silenceBar(reason: string): number | null {
  const m = /silence (\d+)ms [<>]=? (?:patience )?(\d+)ms/.exec(reason);
  if (!m || Number(m[2]) <= 0) return null;
  return Math.min(1, Number(m[1]) / Number(m[2]));
}

export default function App() {
  const [mode, setMode] = useState<Mode>("baseline");
  const [source, setSource] = useState<Source>("sample");
  const [view, dispatch] = useReducer(reduce, EMPTY);
  const [botSpeaking, setBotSpeaking] = useState(false);
  const [script, setScript] = useState<LoadedTurn[] | null>(null);

  // Live objects of the current Call; refs because the sample caller reads them as it runs.
  const call = useRef<Call | null>(null);
  const voice = useRef<BotVoice | null>(null);
  const audio = useRef<AudioContext | null>(null);
  const abort = useRef<AbortController | null>(null);
  const states = useRef(0);
  const done = useRef(false);
  const stopMic = useRef<(() => void) | null>(null);
  const quietSince = useRef(0); // when the bot last stopped speaking

  useEffect(() => {
    loadScript(SAMPLE_SCRIPT).then(setScript, (err: Error) =>
      dispatch({ kind: "end", status: err.message }),
    );
    return () => tearDown();
  }, []);

  function tearDown() {
    stopMic.current?.();
    stopMic.current = null;
    abort.current?.abort();
    voice.current?.cancel();
    call.current?.close();
    void audio.current?.close();
    call.current = voice.current = audio.current = abort.current = null;
    setBotSpeaking(false);
  }

  function hangUp(status = "Call ended.") {
    tearDown();
    dispatch({ kind: "end", status });
  }

  async function startCall(m: Mode, s: Source) {
    tearDown();
    if (s === "sample" && !script) return;
    states.current = 0;
    done.current = false;
    dispatch({ kind: "start", status: `Calling Northwind Energy (${MODE_LABEL[m]})…` });

    // Created here, inside the click, so the browser allows sound.
    const ctx = new AudioContext();
    const v = new BotVoice((speaking) => {
      setBotSpeaking(speaking);
      if (!speaking) quietSince.current = performance.now();
    });
    const ac = new AbortController();
    const c = openCall(
      m,
      (e) => {
        if (e.type === "bot") v.say(e.line);
        if (e.type === "state") {
          states.current++;
          if (e.state === "DONE") done.current = true;
        }
        dispatch({ kind: "event", e });
      },
      (why) => hangUp(why),
    );
    audio.current = ctx;
    voice.current = v;
    abort.current = ac;
    call.current = c;

    try {
      await c.ready;
    } catch (err) {
      hangUp((err as Error).message);
      return;
    }
    if (s === "mic") {
      // Frames are dropped (not sent) while the bot speaks, so its voice can't become a Turn.
      const muted = () => v.speaking || performance.now() - quietSince.current < MUTE_TAIL_MS;
      try {
        const stop = await startMic(ctx, (f) => {
          if (!muted()) c.sendPcm(f);
        });
        if (ac.signal.aborted) stop(); // hung up while the permission prompt was open
        else stopMic.current = stop;
      } catch (err) {
        hangUp(`Microphone unavailable: ${(err as Error).message}`);
      }
      return;
    }
    if (s === "sample" && script) {
      await runSampleCaller(script, {
        sendPcm: (f) => c.sendPcm(f),
        stateCount: () => states.current,
        done: () => done.current,
        botQuiet: () => v.whenQuiet(),
        onTurn: (label) => dispatch({ kind: "turn", label }),
        audio: ctx,
        signal: ac.signal,
      });
      if (!ac.signal.aborted)
        dispatch({
          kind: "turn",
          label: done.current ? null : "Sample caller finished; the call didn't reach the end.",
        });
    }
  }

  function chooseMode(m: Mode) {
    setMode(m);
    if (view.inCall) void startCall(m, source); // the toggle reconnects: same caller, new line
  }

  const now = view.now;
  const stop = view.lastStop;
  const bar = now ? silenceBar(now.reason) : null;

  return (
    <main>
      <header className="masthead">
        <h1>Unhurried</h1>
        <p className="tagline">A phone line that doesn't cut off callers who stammer.</p>
      </header>

      {/* DOM order = reading and Tab order on one column; desktop places these in two columns with grid areas */}
      <div className="layout">
        <section className="card call-card" aria-label="Call controls">
          <fieldset className="source">
            <legend className="card-label">Caller</legend>
            <label>
              <input
                type="radio"
                name="source"
                checked={source === "sample"}
                onChange={() => setSource("sample")}
                disabled={view.inCall}
              />
              <span>Play sample caller (recorded, with a stammer)</span>
            </label>
            <label>
              <input
                type="radio"
                name="source"
                checked={source === "mic"}
                onChange={() => setSource("mic")}
                disabled={view.inCall}
              />
              <span>My microphone (use headphones)</span>
            </label>
          </fieldset>
          {view.inCall ? (
            <button className="big hangup" onClick={() => hangUp()}>
              Hang up
            </button>
          ) : (
            <button
              className="big call"
              onClick={() => void startCall(mode, source)}
              disabled={source === "sample" && !script}
            >
              Call Northwind Energy
            </button>
          )}
          <p className="status" role="status">
            {view.status}
            {view.turnLabel && <> · {view.turnLabel}</>}
          </p>
        </section>

        <section className="card line-card">
          <fieldset className="mode" aria-describedby="mode-hint">
            <legend className="card-label">Line</legend>
            <div className="segmented">
              {(["baseline", "patient"] as Mode[]).map((m) => (
                <label key={m} className={mode === m ? "chosen" : ""}>
                  <input
                    type="radio"
                    name="mode"
                    value={m}
                    checked={mode === m}
                    onChange={() => chooseMode(m)}
                  />
                  <span>{MODE_LABEL[m]}</span>
                </label>
              ))}
            </div>
            <p className="mode-hint" id="mode-hint">{MODE_HINT[mode]}</p>
          </fieldset>
        </section>

        <section className="card why" aria-labelledby="why-h">
          <h2 id="why-h" className="card-label">Why it's waiting</h2>
          <div className="live">
            {now ? (
              <>
                <p className={`action action-${now.action.toLowerCase()}`}>{ACTION_LABEL[now.action]}</p>
                <p className="reason">{now.reason}</p>
                {bar && (
                  <div className="silence-bar" aria-hidden="true">
                    <div
                      className={now.action === "END" ? "fill fill-end" : "fill"}
                      style={{ width: `${bar * 100}%` }}
                    />
                  </div>
                )}
                {botSpeaking && <p className="muted-note">Bot speaking, caller audio muted</p>}
              </>
            ) : (
              <p className="empty">Start a call to see each decision and why.</p>
            )}
          </div>
          <div className="last-stop">
            {stop ? (
              <>
                <p className={`stop-head action-${stop.action.toLowerCase()}`}>
                  Last {stop.action === "END" ? "turn end" : "prompt"} at {secs(stop.t_ms)}
                </p>
                <p className="stop-reason">{stop.reason}</p>
              </>
            ) : (
              <p className="stop-head empty">No turn end or prompt yet.</p>
            )}
          </div>
        </section>

        <section className="card bot-card" aria-labelledby="bot-h">
          <h2 id="bot-h" className="card-label">Northwind Energy</h2>
          {/* column-reverse keeps the scroll pinned to the newest line, no script needed */}
          <div className="bot-scroll" tabIndex={0} aria-labelledby="bot-h">
            {view.botLines.length === 0 && <p className="empty">The bot's lines appear here.</p>}
            <ol className="bot-lines" aria-live="polite">
              {view.botLines.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ol>
          </div>
        </section>

        <Keypad disabled={!view.inCall} onSend={(d) => call.current?.sendKeypad(d)} />

        <section className="card heard-card" aria-labelledby="heard-h">
          <h2 id="heard-h" className="card-label">Heard</h2>
          <dl className="heard">
            <div>
              <dt>Raw</dt>
              <dd className="transcript raw">{view.transcript || "…"}</dd>
            </div>
            <div>
              <dt>Clean</dt>
              <dd className="transcript">{view.clean || "…"}</dd>
            </div>
          </dl>
          {view.expectedSlot && <p className="slot">Waiting for {SLOT_LABEL[view.expectedSlot] ?? view.expectedSlot}.</p>}
          {Object.keys(view.slots).length > 0 && (
            <dl className="slots">
              {Object.entries(view.slots).map(([k, val]) => (
                <div key={k}>
                  <dt>{k.replace(/_/g, " ")}</dt>
                  <dd>{val}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      </div>
    </main>
  );
}
