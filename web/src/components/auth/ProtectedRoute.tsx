import { Navigate, Outlet, useLocation } from "react-router-dom"
import { useAuth } from "../../lib/AuthContext"

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <div role="status" aria-live="polite">Loading Lucent…</div>
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}
