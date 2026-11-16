import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    // lets imports use "@/..." for "src/..." (like a path alias in Next.js)
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
})
