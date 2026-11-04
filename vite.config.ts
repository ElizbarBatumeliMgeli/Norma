import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig(() => ({
  plugins: [react()],
  clearScreen: false,
  server: {
    // Its own port, so NORMA and MEP Master can run side by side.
    port: 1440,
    strictPort: true,
    // Browser-only development: forward API calls to a locally running engine/server.py.
    proxy: { "/api": "http://127.0.0.1:8100" },
    watch: { ignored: ["**/src-tauri/**"] },
  },
}));
