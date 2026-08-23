import styles from "./onboarding.module.css"

export const LEARNING_GOAL_OPTIONS = [
  "Programming",
  "Math",
  "Science",
  "School",
  "Research",
  "Languages",
  "Something else"
]
const OPTIONS = LEARNING_GOAL_OPTIONS

export function StepLearningGoals({
  selected,
  onToggle,
  onNext
}: {
  selected: string[]
  onToggle: (value: string) => void
  onNext: () => void
}) {
  return (
    <div className={styles.container}>
      <h1 className={styles.heading}>What are you learning?</h1>
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
        <button className={styles.btnPrimary} onClick={onNext}>
          Continue →
        </button>
      </div>
    </div>
  )
}
