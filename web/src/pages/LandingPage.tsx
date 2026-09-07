import { MarketingNav } from "../components/marketing/MarketingNav"
import { Hero } from "../components/marketing/Hero"
import { ScrollFlower } from "../components/marketing/ScrollFlower"
import { DemoContent } from "../components/marketing/DemoContent"
import { CapabilitiesContent } from "../components/marketing/CapabilitiesContent"
import { InlineHighlightContent } from "../components/marketing/InlineHighlightContent"
import { ReadingModeContent } from "../components/marketing/ReadingModeContent"
import { PersonalizationContent } from "../components/marketing/PersonalizationContent"
import { SavedUnderstandingContent } from "../components/marketing/SavedUnderstandingContent"
import { FinalCTA } from "../components/marketing/FinalCTA"
import styles from "../components/marketing/marketing.module.css"

export function LandingPage() {
  return (
    <div className={styles.page}>
      <div className={styles.sectionContent}>
        <MarketingNav />
      </div>

      <Hero />
      <ScrollFlower />
      <DemoContent />
      <CapabilitiesContent />
      <InlineHighlightContent />
      <ReadingModeContent />
      <PersonalizationContent />
      <SavedUnderstandingContent />
      <FinalCTA />
    </div>
  )
}
