import { createContext, useContext, useMemo, useState, type ReactNode } from "react"

export type AuthUser = {
  id: string
  name: string
  email: string
  provider: "development"
}

const STORAGE_KEY = "lucent.development-user"
const DEVELOPMENT_USER: AuthUser = {
  id: "lucent-local-development-user",
  name: "Lucent Development User",
  email: "development@lucent.local",
  provider: "development"
}

type AuthContextValue = {
  user: AuthUser | null
  isAuthenticated: boolean
  continueAsDevelopmentUser: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readDevelopmentSession(): AuthUser | null {
  if (!import.meta.env.DEV) return null
  return localStorage.getItem(STORAGE_KEY) === DEVELOPMENT_USER.id ? DEVELOPMENT_USER : null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(readDevelopmentSession)

  const value = useMemo<AuthContextValue>(() => ({
    user,
    isAuthenticated: user !== null,
    continueAsDevelopmentUser() {
      if (!import.meta.env.DEV) {
        throw new Error("Development login is unavailable in production")
      }
      localStorage.setItem(STORAGE_KEY, DEVELOPMENT_USER.id)
      setUser(DEVELOPMENT_USER)
    }
  }), [user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within AuthProvider")
  return context
}
