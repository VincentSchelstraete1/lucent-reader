import { getCsrfToken, setCsrfToken } from "../api/client"

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
export type AuthUser = { id: string; email: string | null; email_verified: boolean; display_name: string | null; avatar_url: string | null }
export type AuthSession = { user: AuthUser; csrf_token: string }

async function csrfProtectedRequest(path: string, method: "POST" | "DELETE"): Promise<Response> {
  const request = () => {
    const csrf = getCsrfToken()
    return fetch(`${API_URL}${path}`, {
      method,
      credentials: "include",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
    })
  }

  let response = await request()
  if (response.status !== 403) return response

  // The readable CSRF cookie is scoped to the API host in production, so the
  // web origin cannot obtain it through document.cookie. Refresh the token
  // from the authenticated session response and retry the mutation once.
  const auth = await fetch(`${API_URL}/auth/me`, { credentials: "include" })
  if (!auth.ok) return response
  const session = await auth.json() as AuthSession
  if (!session.csrf_token) return response
  setCsrfToken(session.csrf_token)
  response = await request()
  return response
}

export const authAdapter = {
  continueWithGoogle(returnTo = "/app"): void {
    const safe = returnTo.startsWith("/") && !returnTo.startsWith("//") ? returnTo : "/app"
    window.location.assign(`${API_URL}/auth/google/start?return_to=${encodeURIComponent(safe)}`)
  },
  async me(): Promise<AuthSession | null> {
    const response = await fetch(`${API_URL}/auth/me`, { credentials: "include" })
    if (response.status === 401) return null
    if (!response.ok) throw new Error("Unable to check authentication")
    return response.json()
  },
  async continueAsDevelopmentUser(): Promise<AuthSession> {
    const response = await fetch(`${API_URL}/auth/development-login`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" } })
    if (!response.ok) throw new Error(response.status === 404 ? "Development login is disabled on the backend." : "Development login failed.")
    return response.json()
  },
  async logout(): Promise<void> {
    const response = await csrfProtectedRequest("/auth/logout", "POST")
    if (!response.ok) throw new Error("Logout failed")
  },
  async deleteAccount(): Promise<void> {
    const response = await csrfProtectedRequest("/auth/account", "DELETE")
    if (!response.ok) throw new Error("We couldn't delete your account. Please try again.")
  }
}
