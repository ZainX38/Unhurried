import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: the page is served on :5173 and /ws is proxied to uvicorn on :8000,
// so the browser talks to one origin. The demo WAVs are imported straight
// from eval/data/demo (outside this folder), hence fs.allow.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/ws": { target: "ws://127.0.0.1:8000", ws: true } },
    fs: { allow: [".", "../eval/data/demo"] },
  },
});
