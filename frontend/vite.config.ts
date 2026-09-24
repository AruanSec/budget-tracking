import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Dev: proxy API calls to the local FastAPI (same-origin in prod via nginx).
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
