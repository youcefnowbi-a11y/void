import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// BLACK HEART OPS — un seul React pour tous (le duel des copies tue les
// hooks : une lib qui se bundle avec SA copie de react → dispatcher null
// → crash App). resolve.dedupe + optimizeDeps.include forcent l'unicité.
// (three/@react-three arrachés — le cœur est du SVG pur désormais.)
export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
  optimizeDeps: {
    include: ['react', 'react-dom'],
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  }
})
