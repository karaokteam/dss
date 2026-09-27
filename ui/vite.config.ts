import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// API isteklerini Flask'a (5000) yönlendir
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",   // derlenmiş arayüz alt yolda da (Run:ai /<proje>/<iş>/) çalışsın
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:5000" } },
});
