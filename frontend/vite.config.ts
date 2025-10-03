import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

const BACKEND = process.env.BACKEND_ORIGIN || "http://localhost:8000"; // use http here
const WS_TARGET = BACKEND.replace(/^http/, "ws"); // -> ws://localhost:8000 or ws://backend:8000

export default defineConfig(({ mode }) => ({
  server: {
    host: true,
    port: 5173,
    watch: { usePolling: true },
    proxy: {
      // REST: your fetch('/api/upload-video/') becomes backend '/upload-video/' via rewrite
      "/api": {
        target: BACKEND,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
      // WebSocket: your wsURL() -> ws(s)://<origin>/ws/camera
      "/ws": {
        target: WS_TARGET,
        ws: true,
        changeOrigin: true,
      },
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(
    Boolean
  ),
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
}));
