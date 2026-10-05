import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from "path"
import tailwindcss from "@tailwindcss/vite"
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    headers: {
      // Evita que una pestaña conserve módulos de una versión anterior tras actualizar npm.
      'Cache-Control': 'no-store',
    },
    port: 5185,
    strictPort: true,
    allowedHosts: ["localhost"]
  }
})
