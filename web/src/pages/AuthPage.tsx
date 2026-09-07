import { lazy, Suspense } from "react"
import { Link, Navigate } from "react-router-dom"
import { AuthCard } from "../components/auth/AuthCard"
import { LanyardErrorBoundary } from "../components/auth/LanyardErrorBoundary"
import { useReducedMotion } from "../lib/useReducedMotion"
import styles from "../components/auth/auth.module.css"
import { useAuth } from "../lib/AuthContext"

// Lazy-loaded: pulls in three/fiber/drei/rapier (incl. its WASM physics
// engine) - keep it out of the main bundle. AuthCard (the real, functional
// login/signup form) never depends on this having loaded.
const LucentLanyard = lazy(() =>
  import("../components/auth/LucentLanyard").then((m) => ({ default: m.LucentLanyard }))
)

function LanyardLoadingPlaceholder() {
  return (
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className={styles.staticCardCord} />
      <div className={styles.staticCard} />
    </div>
  )
}

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const reduced = useReducedMotion()
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
        <div className={styles.authIntro}>
          <p>KEEP WHAT CLICKS</p>
          <h2>A place for ideas to take root.</h2>
          <span>Drag the learner card and let it settle.</span>
        </div>
        <div className={styles.lanyardColumn}>
          <LanyardErrorBoundary>
            <Suspense fallback={<LanyardLoadingPlaceholder />}>
              <LucentLanyard reduced={reduced} />
            </Suspense>
          </LanyardErrorBoundary>
        </div>

        <AuthCard mode={mode} />
      </div>
    </div>
  )
}
