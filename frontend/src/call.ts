// One WebSocket Call to the server (src/unhurried/server.py). Bytes and JSON only.

export type Mode = "baseline" | "patient";

export type Action = "CONTINUE" | "END" | "PROMPT";

export interface Decision {
  action: Action;
  reason: string;
  t_ms: number;
}

// The four event shapes documented in src/unhurried/session.py.
export type ServerEvent =
  | { type: "transcript"; text: string }
  | ({ type: "decision" } & Decision)
  | { type: "bot"; line: string }
  | { type: "state"; state: string; expected_slot: string; slots: Record<string, string> };

export interface Call {
  ready: Promise<void>;
  sendPcm(frame: Int16Array): void;
  sendKeypad(digits: string): void;
  close(): void;
}

export function openCall(
  mode: Mode,
  onEvent: (e: ServerEvent) => void,
  onClose: (why: string) => void,
): Call {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws?endpointer=${mode}`);
  ws.binaryType = "arraybuffer";

  const ready = new Promise<void>((resolve, reject) => {
    ws.onopen = () => resolve();
    ws.onerror = () => reject(new Error("Can't reach the server. Is uvicorn running on port 8000?"));
  });
  ws.onmessage = (m) => onEvent(JSON.parse(m.data as string) as ServerEvent);
  ws.onclose = (e) => onClose(e.reason || "The call ended.");

  const open = () => ws.readyState === WebSocket.OPEN;
  return {
    ready,
    sendPcm(frame) {
      if (open()) ws.send(frame); // PCM16 little-endian, as the server expects
    },
    sendKeypad(digits) {
      if (open()) ws.send(JSON.stringify({ type: "keypad", digits }));
    },
    close() {
      ws.onclose = null; // closing on purpose is not an error
      ws.close();
    },
  };
}
