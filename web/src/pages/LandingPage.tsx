import { MarketingNav } from "../components/marketing/MarketingNav"
import { Link } from "react-router-dom"
import { SpatialStory } from "../components/marketing/SpatialStory"
import { CHROME_EXTENSION_URL } from "../lib/extension"
import styles from "../components/marketing/marketing.module.css"

export function LandingPage() {
  return (
    <div className={styles.page}>
      <header className={styles.sectionContent}>
        <MarketingNav />
      </header>

      <SpatialStory />
      <footer className={styles.footer}><Link to="/" className={styles.wordmark}>Lucent</Link><span>Learning, made clearer.</span><nav aria-label="Legal and account"><a href={CHROME_EXTENSION_URL} target="_blank" rel="noreferrer">Chrome extension</a><Link to="/privacy">Privacy</Link><Link to="/terms">Terms</Link><Link to="/login">Log in <span aria-hidden="true">↗</span></Link></nav></footer>
    </div>
  )
}
