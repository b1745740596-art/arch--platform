import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Django 后端地址（可选的本地热更新代理用）
const DJANGO_TARGET = process.env.DJANGO_TARGET || 'http://127.0.0.1:8000'

// 单端口部署：由 Django 托管构建产物。
// - base 指向 /static/spa/，与 Django 的 STATIC_URL 对齐
// - 产物输出到项目根的 frontend_dist/，由 Django collectstatic 收集
// https://vite.dev/config/
export default defineConfig({
  base: '/static/spa/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: fileURLToPath(new URL('../frontend_dist', import.meta.url)),
    emptyOutDir: true,
    manifest: true,
  },
  // 可选：如仍想用 Vite 热更新开发，npm run dev 会通过代理访问 Django
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': { target: DJANGO_TARGET, changeOrigin: true },
      '/admin': { target: DJANGO_TARGET, changeOrigin: true },
      '/media': { target: DJANGO_TARGET, changeOrigin: true },
    },
  },
})
