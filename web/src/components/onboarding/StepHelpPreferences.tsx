import styles from "./onboarding.module.css"

const OPTIONS = [
  "Explain things differently",
  "Visualize difficult ideas",
  "Organize what I learn",
  "Practice and remember",
  "Connect ideas",
  "I'm not sure yet"
]

export function StepHelpPreferences({
  selected,
  onToggle,
  onNext,
  onBack
}: {
  selected: string[]
  onToggle: (value: string) => void
  onNext: () => void
  onBack: () => void
}) {
  return (
    <div className={styles.container}>
      <h1 className={styles.heading}>How should Lucent help you?</h1>
      <p className={styles.subheading}>Pick any that apply.</p>

      <div className={styles.pillGrid}>
        {OPTIONS.map((option) => (
          <button
            key={option}
            className={`${styles.pill} ${selected.includes(option) ? styles.pillSelected : ""}`}
            onClick={() => onToggle(option)}
          >
            {option}
          </button>
        ))}
      </div>

      <div className={styles.actions}>
        <button className={styles.btnGhost} onClick={onBack}>
          Back
        </button>
        <button className={styles.btnPrimary} onClick={onNext}>
          Continue →
        </button>
      </div>
    </div>
  )
}
