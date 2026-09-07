import { OnboardingFlow } from "../components/onboarding/OnboardingFlow"
import styles from "../components/onboarding/onboarding.module.css"

export function OnboardingPage() {
  return (
    <div className={styles.page}>
      <OnboardingFlow />
    </div>
  )
}
