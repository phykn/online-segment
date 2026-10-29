import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

import pkg from './package.json' with { type: 'json' }

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
