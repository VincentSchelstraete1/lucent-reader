import { useState } from "react"
import { Link, NavLink, Outlet } from "react-router-dom"
import { AppWalkthrough } from "../walkthrough/AppWalkthrough"
import { useAuth } from "../../lib/AuthContext"
import "../../index.css"

function SidebarIcon({ name }: { name: "library" | "learn" | "cards" | "quiz" | "settings" }) {
  const paths = { library: <><path d="M3 5.5h6l1.5 2H21v11H3z" /><path d="M3 8h18" /></>, learn: <><path d="M3 5.5c3.4-.8 6 .2 9 2.2v11c-3-2-5.6-3-9-2.2z" /><path d="M21 5.5c-3.4-.8-6 .2-9 2.2v11c3-2 5.6-3 9-2.2z" /></>, cards: <><rect x="4" y="6" width="14" height="11" rx="1.5" /><path d="M7 4h13v11" /></>, quiz: <><circle cx="12" cy="12" r="8.5" /><path d="M9.8 9.5a2.3 2.3 0 1 1 3.8 1.7c-1 .7-1.6 1.1-1.6 2.3" /><path d="M12 16.2h.01" /></>, settings: <><path d="M4 7h10M18 7h2M4 17h2M10 17h10" /><circle cx="16" cy="7" r="2" /><circle cx="8" cy="17" r="2" /></> }[name]
  return <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths}</svg>
}

// Loading this module also loads the authenticated application stylesheet.
// Public routes stay on the smaller base stylesheet until the app is opened.
export function AppLayout() {
  const { user, logout } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)
  const [logoutError, setLogoutError] = useState("")

  async function handleLogout() {
    setLoggingOut(true)
    setLogoutError("")
    try {
      await logout()
    } catch {
      setLogoutError("We couldn't log you out. Please try again.")
      setLoggingOut(false)
    }
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="Study navigation">
        <Link to="/app" className="brand" data-tour="app-brand">Lucent</Link>
        <nav className="app-sidebar-nav">
          <NavLink to="/app" end className={({ isActive }) => isActive ? "active" : ""}><SidebarIcon name="library" />Library</NavLink>
          <NavLink to="/app?view=learn" className={({ isActive }) => isActive ? "active" : ""}><SidebarIcon name="learn" />Learn</NavLink>
          <NavLink to="/app?view=flashcards" className={({ isActive }) => isActive ? "active" : ""}><SidebarIcon name="cards" />Flashcards</NavLink>
          <NavLink to="/app?view=quiz" className={({ isActive }) => isActive ? "active" : ""}><SidebarIcon name="quiz" />Quiz</NavLink>
        </nav>
        <div className="app-sidebar-footer">
          <NavLink to="/app/settings" className={({ isActive }) => `app-sidebar-settings${isActive ? " active" : ""}`}><SidebarIcon name="settings" />Settings</NavLink>
          {user && <SidebarAccount user={user} onLogout={() => void handleLogout()} loggingOut={loggingOut} error={logoutError} />}
        </div>
      </aside>
      <main><Outlet /></main>
      <AppWalkthrough />
    </div>
  )
}

export function SidebarAccount({ user, onLogout, loggingOut = false, error = "" }: {
  user: { display_name: string | null; email: string | null }
  onLogout: () => void
  loggingOut?: boolean
  error?: string
}) {
  const label = user.display_name || user.email || "Account"
  return <div className="app-sidebar-account" aria-label="Account"><span className="account-avatar">{getUserInitials(user)}</span><span className="account-label">{label}</span><button type="button" onClick={onLogout} disabled={loggingOut}>{loggingOut ? "Logging out…" : "Log out"}</button>{error && <span className="error" role="alert">{error}</span>}</div>
}

export function getUserInitials(user: { display_name: string | null; email: string | null }): string {
  const displayName = user.display_name?.trim()
  const identity = displayName || user.email?.split("@")[0]?.trim() || ""
  const parts = identity.split(/[\s._-]+/).filter(Boolean)
  if (parts.length === 0) return "A"
  const first = Array.from(parts[0])[0]
  const last = parts.length > 1 ? Array.from(parts[parts.length - 1])[0] : ""
  return `${first}${last}`.toUpperCase()
}
