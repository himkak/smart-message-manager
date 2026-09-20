import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Listen on all interfaces (e.g. LAN IP) so mobile devices on the same
    // network can reach the dev server, not just localhost.
    host: true,
  },
})
