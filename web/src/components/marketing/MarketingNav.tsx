import { Link } from "react-router-dom"
import styles from "./marketing.module.css"

export function MarketingNav() {
  return (
    <nav className={styles.nav}>
      <Link to="/" className={styles.wordmark}>
        Lucent
      </Link>
      <div className={styles.navLinks}>
        <a href="#features" className={styles.navLink}>
          Product
        </a>
        <a href="#reading-mode" className={styles.navLink}>
          Reading Mode
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
