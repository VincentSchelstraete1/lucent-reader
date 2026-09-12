import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react"

export function validateProductionApiOrigin(value: string | undefined): string {
  if (!value?.trim()) throw new Error("VITE_API_URL is required for a production build")
  const parsed = new URL(value)
  if (
    parsed.protocol !== "https:" ||
    !parsed.hostname ||
    parsed.username ||
    parsed.password ||
    parsed.pathname !== "/" ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error("VITE_API_URL must be a plain HTTPS origin for a production build")
  }
  return parsed.origin
}

export default defineConfig(({ command, mode }) => {
  if (command === "build") {
    validateProductionApiOrigin(loadEnv(mode, process.cwd(), "").VITE_API_URL)
  }
  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1"
    }
  }
})
