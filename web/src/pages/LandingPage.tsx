import { MarketingNav } from "../components/marketing/MarketingNav"
import { Hero } from "../components/marketing/Hero"
import { FeatureSection } from "../components/marketing/FeatureSection"
import styles from "../components/marketing/marketing.module.css"

export function LandingPage() {
  return (
    <div className={styles.page}>
      <MarketingNav />
      <Hero />
      <FeatureSection />
    </div>
  )
}
