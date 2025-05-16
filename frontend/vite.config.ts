import { defineConfig } from 'vite'

export default defineConfig({
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000', // 你的 FastAPI 后端地址
          changeOrigin: true,
          rewrite: path => path.replace(/^\/api/, '/api'),
        },
      },
    },
  });
  