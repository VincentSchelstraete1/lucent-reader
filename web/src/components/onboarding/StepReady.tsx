import styles from "./onboarding.module.css"

export function StepReady({ onStart, onBack }: { onStart: () => void; onBack: () => void }) {
  return (
    <div className={styles.container}>
      <h1 className={styles.heading}>You're ready.</h1>
      <p className={styles.subheading}>Lucent will meet you where you learn.</p>

      <div className={styles.actions}>
        <button className={styles.btnGhost} onClick={onBack}>
          Back
        </button>
        <button className={styles.btnPrimary} onClick={onStart}>
          Start learning →
        </button>
      </div>
    </div>
  )
}
