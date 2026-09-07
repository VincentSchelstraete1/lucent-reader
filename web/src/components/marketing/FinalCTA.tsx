import { Link } from "react-router-dom"
import styles from "./marketing.module.css"

export function FinalCTA() {
  return (
    <section className={`${styles.section} ${styles.sectionContent} ${styles.finalCta}`}>
      <p className={styles.eyebrow}>Your understanding, in bloom</p>
      <h2 className={styles.sectionHeading}>Learn your way.</h2>
      <p className={styles.sectionBody}>Bring Lucent to the next thing you want to understand.</p>
      <Link to="/signup" className={styles.btnPrimary}>
        Get started
      </Link>
    </section>
  )
}
