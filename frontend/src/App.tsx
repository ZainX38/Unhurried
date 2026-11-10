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
  transcript: string;
  now: Decision | null; // the latest decision (one per 32 ms frame)
  lastStop: Decision | null; // the latest END or PROMPT, which only lasts one frame in `now`
  botLines: string[];
  state: string;
  expectedSlot: string;
  slots: Record<string, string>;
  turnLabel: string | null;
}

const EMPTY: View = {
  inCall: false, status: "", transcript: "", now: null, lastStop: null,
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
      if (e.type === "transcript") return { ...v, transcript: e.text };
      if (e.type === "bot") return { ...v, botLines: [...v.botLines, e.line] };
      if (e.type === "state")
        return {
          ...v, state: e.state, expectedSlot: e.expected_slot, slots: e.slots, transcript: "",
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

  return (
    <main>
      <header>
        <h1>Unhurried</h1>
        <p className="tagline">A phone line that doesn't cut off callers who stammer.</p>
      </header>

      <fieldset className="mode">
        <legend>Line</legend>
        {(["baseline", "patient"] as Mode[]).map((m) => (
          <label key={m} className={mode === m ? "chosen" : ""}>
            <input
              type="radio"
              name="mode"
              value={m}
              checked={mode === m}
              onChange={() => chooseMode(m)}
            />
            <span className="mode-name">{MODE_LABEL[m]}</span>
            <span className="mode-hint">{MODE_HINT[m]}</span>
          </label>
        ))}
      </fieldset>

      <section className="why" aria-labelledby="why-h">
        <h2 id="why-h">Why it's waiting</h2>
        {now ? (
          <>
            <p className={`action action-${now.action.toLowerCase()}`}>
              {ACTION_LABEL[now.action]}
              {botSpeaking && <span className="muted-note"> · bot speaking, caller audio muted</span>}
            </p>
            <p className="reason">{now.reason}</p>
          </>
        ) : (
          <p className="reason">Start a call to see each decision and its reason.</p>
        )}
        {stop && (
          <p className="last-stop">
            Last {stop.action === "END" ? "turn end" : "prompt"} at {secs(stop.t_ms)}: {stop.reason}
          </p>
        )}
      </section>

      <section className="controls" aria-label="Call controls">
        <fieldset className="source">
          <legend>Caller</legend>
          <label>
            <input
              type="radio"
              name="source"
              checked={source === "sample"}
              onChange={() => setSource("sample")}
              disabled={view.inCall}
            />
            Play sample caller (recorded, with a stammer)
          </label>
          <label>
            <input
              type="radio"
              name="source"
              checked={source === "mic"}
              onChange={() => setSource("mic")}
              disabled={view.inCall}
            />
            My microphone (use headphones)
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

      <div className="columns">
        <section aria-labelledby="heard-h">
          <h2 id="heard-h">Heard</h2>
          <p className="transcript">{view.transcript || "…"}</p>
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

        <section aria-labelledby="bot-h">
          <h2 id="bot-h">Northwind Energy</h2>
          <ol className="bot-lines" aria-live="polite">
            {view.botLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ol>
        </section>

        <Keypad disabled={!view.inCall} onSend={(d) => call.current?.sendKeypad(d)} />
      </div>
    </main>
  );
}
