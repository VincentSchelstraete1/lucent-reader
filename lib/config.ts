const configuredOrigin = (value: string | undefined, developmentDefault: string): string =>
  (value?.trim() || developmentDefault).replace(/\/+$/, "")

// Plasmo exposes PLASMO_PUBLIC_* values at build time. Local development keeps
// working without an env file; release builds are validated by the production
// build/package command before Plasmo runs.
export const BACKEND_URL = configuredOrigin(
  process.env.PLASMO_PUBLIC_API_URL,
  "http://127.0.0.1:8000"
)

export const WEB_APP_URL = configuredOrigin(
  process.env.PLASMO_PUBLIC_WEB_APP_URL,
  "http://localhost:5173"
)
