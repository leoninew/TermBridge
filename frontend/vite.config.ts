import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 9007,
    proxy: {
      '/api': 'http://127.0.0.1:9008',
      '/health': 'http://127.0.0.1:9008',
    },
  },
})
