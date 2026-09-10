import { useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { authAdapter } from "../../lib/authAdapter"
import { useAuth } from "../../lib/AuthContext"
import styles from "./auth.module.css"

export function AuthCard({ mode }: { mode: "login" | "signup" }) {
  const [notice, setNotice] = useState("")
  const navigate = useNavigate()
  const location = useLocation()
  const { continueAsDevelopmentUser } = useAuth()

  async function handleDevelopmentLogin() {
    try {
      await continueAsDevelopmentUser()
      const requestedPath = (location.state as { from?: string } | null)?.from
      navigate(requestedPath?.startsWith("/") ? requestedPath : "/app", { replace: true })
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Development login failed")
    }
  }

  function handleGoogleAuth() {
    const requestedPath = (location.state as { from?: string } | null)?.from
    authAdapter.continueWithGoogle(requestedPath)
  }

  return (
    <div className={styles.card}>
      <p className={styles.cardWordmark}>Your Lucent learner card</p>
      <h1 className={styles.cardTitle}>{mode === "login" ? "Welcome back." : "Create your account."}</h1>

      <button className={styles.googleBtn} onClick={handleGoogleAuth}>
        <span aria-hidden="true">G</span> Continue with Google
      </button>

      {notice && <p className={styles.authNotice} role="status">{notice}</p>}

      {import.meta.env.DEV && (
        <button className={styles.developmentBtn} onClick={handleDevelopmentLogin}>
          Continue as development user
        </button>
      )}

      <p className={styles.switchMode}>
        {mode === "login" ? (
          <>
            New to Lucent? <Link to="/signup">Create an account</Link>
          </>
        ) : (
          <>
            Already have an account? <Link to="/login">Log in</Link>
          </>
        )}
      </p>
      <p className={styles.legalLinks}>By continuing, you agree to the <Link to="/terms">Terms</Link> and acknowledge the <Link to="/privacy">Privacy notice</Link>.</p>
    </div>
  )
}
