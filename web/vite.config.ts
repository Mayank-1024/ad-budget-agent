import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard talks to the FastAPI app on :8000 through the dev-server proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", rewrite: (p) => p.replace(/^\/api/, "") } },
  },
});
