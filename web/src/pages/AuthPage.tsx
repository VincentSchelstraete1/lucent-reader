import { Link, Navigate } from "react-router-dom"
import { AuthCard } from "../components/auth/AuthCard"
import styles from "../components/auth/auth.module.css"
import { useAuth } from "../lib/AuthContext"

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (!isLoading && isAuthenticated) {
    return <Navigate to="/app" replace />
  }

  return (
    <div className={styles.page}>
      <nav className={styles.nav}>
        <Link to="/" className={styles.wordmark}>
          Lucent
        </Link>
      </nav>

      <div className={styles.stage}>
        <AuthCard mode={mode} />
      </div>
    </div>
  )
}
