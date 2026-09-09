import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // The Tailwind plugin lets us use Tailwind utility classes everywhere
  // without needing a separate postcss/tailwind.config.js setup.
  plugins: [react(), tailwindcss()],
})
