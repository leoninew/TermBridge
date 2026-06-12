import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 9007,
    proxy: {
      '/api': 'http://127.0.0.1:9008',
      '/health': 'http://127.0.0.1:9008',
      '/terminal': {
        target: 'http://127.0.0.1:9008',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
