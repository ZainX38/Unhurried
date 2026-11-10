import { useState, type KeyboardEvent } from "react";

// Always visible. Buttons are real <button>s (Tab + Enter/Space work); digit keys,
// Backspace and Enter also work while focus is anywhere inside the keypad.
const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

export function Keypad({ disabled, onSend }: { disabled: boolean; onSend: (digits: string) => void }) {
  const [digits, setDigits] = useState("");

  const add = (d: string) => setDigits((s) => (s + d).slice(0, 16));
  const send = () => {
    if (!digits) return;
    onSend(digits);
    setDigits("");
  };
  const onKey = (e: KeyboardEvent) => {
    if (disabled) return;
    if (/^[0-9]$/.test(e.key)) add(e.key);
    else if (e.key === "Backspace") setDigits((s) => s.slice(0, -1));
    else return;
    e.preventDefault();
  };

  return (
    <section className="card keypad" aria-labelledby="keypad-h" onKeyDown={onKey}>
      <h2 id="keypad-h" className="card-label">Keypad</h2>
      <p className="hint">During a call, type your account number, or 1 for yes and 2 for no.</p>
      <output className="typed" aria-live="polite" aria-label="Typed digits">
        {digits || " "}
      </output>
      <div className="keys">
        {KEYS.map((k) => (
          <button key={k} onClick={() => add(k)} disabled={disabled}>
            {k}
          </button>
        ))}
        <button onClick={() => setDigits("")} disabled={disabled || !digits} aria-label="Clear digits">
          Clear
        </button>
        <button onClick={() => add("0")} disabled={disabled}>
          0
        </button>
        <button className="send" onClick={send} disabled={disabled || !digits}>
          Send
        </button>
      </div>
    </section>
  );
}
