import { useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router-dom"
import styles from "./auth.module.css"

export function AuthCard({ mode }: { mode: "login" | "signup" }) {
  const navigate = useNavigate()
  const [showEmailForm, setShowEmailForm] = useState(false)

  // TODO(auth): no backend authentication exists yet. Both "Continue with
  // Google" and the email form below are visual placeholders - wire them to
  // a real OAuth/session flow here once the backend supports it, instead of
  // navigating straight to onboarding.
  function handlePlaceholderAuth(e?: FormEvent) {
    e?.preventDefault()
    navigate("/onboarding")
  }

  return (
    <div className={styles.card}>
      <p className={styles.cardWordmark}>Lucent</p>
      <h1 className={styles.cardTitle}>{mode === "login" ? "Welcome back." : "Create your account."}</h1>

      <button className={styles.googleBtn} onClick={() => handlePlaceholderAuth()}>
        Continue with Google
      </button>

      {!showEmailForm ? (
        <>
          <div className={styles.divider}>or</div>
          <button className={styles.emailLink} onClick={() => setShowEmailForm(true)}>
            Use email instead
          </button>
        </>
      ) : (
        <form className={styles.emailForm} onSubmit={handlePlaceholderAuth} style={{ marginTop: 16 }}>
          <input className={styles.input} type="email" placeholder="Email address" required />
          {mode === "signup" && <input className={styles.input} type="password" placeholder="Password" required />}
          <button type="submit" className={styles.submitBtn}>
            {mode === "login" ? "Continue" : "Create account"}
          </button>
        </form>
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
