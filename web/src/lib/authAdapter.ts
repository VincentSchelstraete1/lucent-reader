export type AuthAttempt = { status: "unavailable"; message: string }

// Security boundary for the public auth UI. The repository currently has no
// OAuth provider, callback route, session endpoint, or user-backed session.
// Replace this adapter only when those pieces are deliberately introduced.
export const authAdapter = {
  configured: false,
  async continueWithGoogle(): Promise<AuthAttempt> {
    return { status: "unavailable", message: "Google sign-in is not connected in this build yet." }
  },
  async continueWithEmail(): Promise<AuthAttempt> {
    return { status: "unavailable", message: "Email sign-in is not connected in this build yet." }
  }
}
