import { useState, type FormEvent } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { authAdapter } from "../../lib/authAdapter"
import { useAuth } from "../../lib/AuthContext"
import styles from "./auth.module.css"

export function AuthCard({ mode }: { mode: "login" | "signup" }) {
  const [showEmailForm, setShowEmailForm] = useState(false)
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

  async function handleAuth(provider: "google" | "email", e?: FormEvent) {
    e?.preventDefault()
    if (provider === "google") {
      const requestedPath = (location.state as { from?: string } | null)?.from
      authAdapter.continueWithGoogle(requestedPath)
      return
    }
    const result = await authAdapter.continueWithEmail()
    setNotice(result.message)
  }

  return (
    <div className={styles.card}>
      <p className={styles.cardWordmark}>Your Lucent learner card</p>
      <h1 className={styles.cardTitle}>{mode === "login" ? "Welcome back." : "Create your account."}</h1>

      <button className={styles.googleBtn} onClick={() => handleAuth("google")}>
        <span aria-hidden="true">G</span> Continue with Google
      </button>

      {!showEmailForm ? (
        <>
          <div className={styles.divider}>or</div>
          <button className={styles.emailLink} onClick={() => setShowEmailForm(true)}>
            Use email instead
          </button>
        </>
      ) : (
        <form className={styles.emailForm} onSubmit={(event) => handleAuth("email", event)} style={{ marginTop: 16 }}>
          <input className={styles.input} type="email" placeholder="Email address" required />
          {mode === "signup" && <input className={styles.input} type="password" placeholder="Password" required />}
          <button type="submit" className={styles.submitBtn}>
            {mode === "login" ? "Continue" : "Create account"}
          </button>
        </form>
      )}

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
    </div>
  )
}
