import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { authAdapter, type AuthUser } from "./authAdapter"
import { setCsrfToken } from "../api/client"

type AuthContextValue = { user: AuthUser | null; isAuthenticated: boolean; isLoading: boolean; continueAsDevelopmentUser: () => Promise<void>; logout: () => Promise<void> }
const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setLoading] = useState(true)
  useEffect(() => {
    let active = true
    authAdapter.me().then((session) => {
      if (!active) return
      setUser(session?.user ?? null)
      setCsrfToken(session?.csrf_token ?? null)
    }).finally(() => active && setLoading(false))
    return () => { active = false }
  }, [])
  const value = useMemo<AuthContextValue>(() => ({
    user, isAuthenticated: user !== null, isLoading,
    async continueAsDevelopmentUser() {
      if (!import.meta.env.DEV) throw new Error("Development login is unavailable in production")
      const session = await authAdapter.continueAsDevelopmentUser()
      setCsrfToken(session.csrf_token); setUser(session.user)
    },
    async logout() { await authAdapter.logout(); setCsrfToken(null); setUser(null) }
  }), [user, isLoading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within AuthProvider")
  return context
}
