const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
export type AuthUser = { id: string; email: string | null; email_verified: boolean; display_name: string | null; avatar_url: string | null }
export type AuthSession = { user: AuthUser; csrf_token: string }
export type AuthAttempt = { status: "unavailable"; message: string }

export const authAdapter = {
  continueWithGoogle(returnTo = "/app"): void {
    const safe = returnTo.startsWith("/") && !returnTo.startsWith("//") ? returnTo : "/app"
    window.location.assign(`${API_URL}/auth/google/start?return_to=${encodeURIComponent(safe)}`)
  },
  async continueWithEmail(): Promise<AuthAttempt> { return { status: "unavailable", message: "Email sign-in is not available." } },
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
    const csrf = document.cookie.split("; ").find((entry) => entry.startsWith("lucent_csrf="))?.split("=")[1]
    const response = await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include", headers: csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {} })
    if (!response.ok) throw new Error("Logout failed")
  }
}
