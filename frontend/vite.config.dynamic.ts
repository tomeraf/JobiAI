import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

// Load port configuration from shared file
function loadPortConfig() {
  const configFile = path.join(__dirname, '..', '.ports.json')

  if (!fs.existsSync(configFile)) {
    // Return defaults if config doesn't exist
    return {
      backend_port: 9000,
      frontend_port: 5173,
      backend_url: 'http://localhost:9000',
      frontend_url: 'http://localhost:5173',
    }
  }

  try {
    const content = fs.readFileSync(configFile, 'utf8')
    return JSON.parse(content)
  } catch (error) {
    console.error('Failed to load port config:', error)
    // Return defaults on error
    return {
      backend_port: 9000,
      frontend_port: 5173,
      backend_url: 'http://localhost:9000',
      frontend_url: 'http://localhost:5173',
    }
  }
}

const portConfig = loadPortConfig()
console.log(`[Vite] Using backend at ${portConfig.backend_url}`)
console.log(`[Vite] Frontend will try port ${portConfig.frontend_port}`)

export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: portConfig.frontend_port,
    strictPort: false, // Allow trying next available port if this one is taken
    proxy: {
      '/api': {
        target: portConfig.backend_url,
        changeOrigin: true,
      },
    },
  },
})
