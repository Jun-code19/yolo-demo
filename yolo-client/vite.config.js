import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // 数据服务API
      '/api/v1': {
        target: 'http://10.83.38.167:8001',
        changeOrigin: true,
        secure: false
      },
      // 检测服务API
      '/api/v2': {
        target: 'http://10.83.38.167:8000',
        changeOrigin: true,
        secure: false
      },
      // 检测预览WebSocket
      '/ws/detection/preview': {
        target: 'ws://10.83.38.167:8000',
        ws: true,
        changeOrigin: true
      },
      // RTSP预览WebSocket
      '/ws/rtsp/preview': {
        target: 'ws://10.83.38.167:8000',
        ws: true,
        changeOrigin: true
      }
    }
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  }
})
