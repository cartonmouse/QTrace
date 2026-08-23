import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'
import process from 'node:process'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

function disableViteClientInjection() {
  return {
    name: 'qtrace-disable-vite-client-injection',
    transformIndexHtml: {
      order: 'post',
      handler(html) {
        // Vite 8 injects /@vite/client even with HMR disabled. In the local
        // browser runtime that client currently crashes on __BUNDLED_DEV__;
        // this app deliberately uses manual refresh during development.
        return html.replace(/\s*<script type="module" src="\/@vite\/client"><\/script>\s*/g, '\n')
      },
    },
  }
}

export default defineConfig(() => {
  // The visual baseline comes from TechSpar, but this isolated migration is
  // exercised against QTrace by default. Keep the old variable as an escape
  // hatch for a real TechSpar backend comparison.
  const apiTarget = process.env.REBUILD_API_TARGET || process.env.TECHSPAR_API_TARGET || 'http://127.0.0.1:8002'

  return {
    plugins: [react(), tailwindcss(), disableViteClientInjection()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5174,
      // Vite 8's injected dev client currently references __BUNDLED_DEV__
      // before the browser runtime defines it. Disable HMR injection so the
      // application entry can render reliably; manual refresh remains intact.
      hmr: false,
      proxy: {
        '/api': apiTarget,
        '/ws': {
          target: apiTarget,
          ws: true,
        },
      },
    },
  }
})
