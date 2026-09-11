import { Link, useLocation } from "react-router-dom"
import { authAdapter } from "../../lib/authAdapter"
import styles from "./auth.module.css"

export function AuthCard({ mode }: { mode: "login" | "signup" }) {
  const location = useLocation()

  function handleGoogleAuth() {
    const requestedPath = (location.state as { from?: string } | null)?.from
    authAdapter.continueWithGoogle(requestedPath)
  }

  return (
    <div className={styles.card}>
      <p className={styles.cardWordmark}>Lucent Learn</p>
      <h1 className={styles.cardTitle}>{mode === "login" ? "Welcome back." : "Create your account."}</h1>
      <p className={styles.cardDescription}>
        {mode === "login"
          ? "Continue to your materials and pick up where you left off."
          : "Use Google to create your learning space."}
      </p>

      <button className={styles.googleBtn} onClick={handleGoogleAuth}>
        <span aria-hidden="true">G</span> Continue with Google
      </button>

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
