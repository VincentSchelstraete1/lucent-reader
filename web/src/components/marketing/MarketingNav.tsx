import { Link } from "react-router-dom"
import styles from "./marketing.module.css"

export function MarketingNav() {
  return (
    <nav className={styles.nav} aria-label="Main navigation">
      <Link to="/" className={styles.wordmark}>
        Lucent
      </Link>
      <div className={styles.navLinks}>
        <a href="#learn-in-action" className={styles.navLink}>
          Explore Learn
        </a>
      </div>
      <div className={styles.navActions}>
        <Link to="/login" className={styles.btnGhost}>
          Log in
        </Link>
        <Link to="/signup" className={styles.btnPrimary}>
          Get started
        </Link>
      </div>
    </nav>
  )
}
