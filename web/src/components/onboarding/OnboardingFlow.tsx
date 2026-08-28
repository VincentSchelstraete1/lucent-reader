import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { AnimatePresence, motion } from "framer-motion"
import { OnboardingFlower } from "./OnboardingFlower"
import styles from "./onboarding.module.css"

type AnswerState = Record<string, string[]>
type Option = { value: string; title: string; description: string; accent: "moss" | "blush" | "terracotta" | "sage" }
type Question = { key: string; title: string; subtitle: string; prompt: string; multiple: boolean; options: Option[] }

const QUESTIONS: Question[] = [
  { key: "context", title: "What are you learning?", subtitle: "Lucent adapts the experience around what you are trying to understand.", prompt: "Choose the closest fit", multiple: false, options: [
    { value: "college", title: "College", description: "Courses, lectures, papers and textbooks.", accent: "sage" },
    { value: "school", title: "School", description: "Classes, assignments and everyday study.", accent: "blush" },
    { value: "work", title: "Work", description: "Docs, research and learning new tools.", accent: "terracotta" },
    { value: "personal", title: "Personal", description: "Articles, interests and things you explore.", accent: "moss" }
  ]},
  { key: "support", title: "How should Lucent help?", subtitle: "Pick the kinds of support you want closest at hand.", prompt: "Choose one or more", multiple: true, options: [
    { value: "explain", title: "Explain", description: "Break down difficult ideas.", accent: "moss" },
    { value: "simplify", title: "Simplify", description: "Make dense writing easier.", accent: "blush" },
    { value: "visualize", title: "Visualize", description: "Show ideas another way.", accent: "terracotta" },
    { value: "focus", title: "Stay focused", description: "Reduce reading friction.", accent: "sage" }
  ]},
  { key: "presentation", title: "How do you like information?", subtitle: "We can start with a style that feels natural and adjust over time.", prompt: "Pick the style that feels most natural", multiple: false, options: [
    { value: "concise", title: "Concise", description: "Give me the key idea.", accent: "sage" },
    { value: "steps", title: "Step by step", description: "Walk me through it.", accent: "moss" },
    { value: "examples", title: "Examples first", description: "Show before explaining.", accent: "terracotta" },
    { value: "visual", title: "Visual", description: "Help me see the idea.", accent: "blush" }
  ]},
  { key: "friction", title: "What usually slows you down?", subtitle: "This helps Lucent know when to offer support without getting in the way.", prompt: "Choose what gets in your way most often", multiple: true, options: [
    { value: "wording", title: "Dense wording", description: "The language gets harder than the idea.", accent: "moss" },
    { value: "focus", title: "Losing focus", description: "Long pages make it hard to stay engaged.", accent: "blush" },
    { value: "terms", title: "New terms", description: "Too many unfamiliar words break the flow.", accent: "terracotta" },
    { value: "length", title: "Long pages", description: "The amount of content feels overwhelming.", accent: "sage" }
  ]}
]

export function OnboardingFlow() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(1)
  const [answers, setAnswers] = useState<AnswerState>({})
  const [pulse, setPulse] = useState(0)
  const question = QUESTIONS[step]
  const selected = answers[question.key] ?? []
  function toggleOption(value: string) {
    setAnswers((current) => {
      const values = current[question.key] ?? []
      const next = question.multiple ? values.includes(value) ? values.filter((item) => item !== value) : [...values, value] : [value]
      return { ...current, [question.key]: next }
    })
    setPulse((value) => value + 1)
  }
  function next() {
    if (step === QUESTIONS.length - 1) {
      sessionStorage.setItem("lucentOnboardingPreferences", JSON.stringify(answers))
      navigate("/signup", { state: { fromOnboarding: true } })
      return
    }
    setDirection(1); setStep((value) => value + 1)
  }
  function back() {
    if (step === 0) return navigate("/")
    setDirection(-1); setStep((value) => value - 1)
  }
  const progress = (step + 1) / QUESTIONS.length
  return <div className={styles.flow}>
    <div className={styles.progressRow}>
      <span className={styles.wordmark}>lucent</span>
      <div className={styles.progressTrack} role="progressbar" aria-label={"Onboarding step " + (step + 1) + " of " + QUESTIONS.length} aria-valuemin={1} aria-valuemax={QUESTIONS.length} aria-valuenow={step + 1}>
        <motion.span className={styles.progressFill} animate={{ width: (progress * 100) + "%" }} transition={{ duration: 0.35, ease: [0.2, 0.8, 0.2, 1] }} />
      </div>
      <span className={styles.stepCount}>{step + 1} / {QUESTIONS.length}</span>
    </div>
    <OnboardingFlower progress={progress} pulseKey={pulse} />
    <AnimatePresence mode="wait" initial={false} custom={direction}>
      <motion.section key={question.key} className={styles.container} custom={direction} initial={{ opacity: 0, x: direction * 18 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: direction * -18 }} transition={{ duration: 0.28, ease: "easeOut" }}>
        <h1 className={styles.heading}>{question.title}</h1>
        <p className={styles.subheading}>{question.subtitle}</p>
        <p className={styles.choicePrompt}>{question.prompt}</p>
        <div className={styles.choiceGrid}>{question.options.map((option) => {
          const active = selected.includes(option.value)
          return <button key={option.value} type="button" className={[styles.choiceCard, active ? styles.choiceCardSelected : ""].join(" ")} aria-pressed={active} onClick={() => toggleOption(option.value)}>
            <span className={[styles.choiceMark, styles["accent_" + option.accent]].join(" ")}>{option.title.charAt(0)}</span>
            <span><strong>{option.title}</strong><small>{option.description}</small></span>
          </button>
        })}</div>
      </motion.section>
    </AnimatePresence>
    <div className={styles.flowActions}>
      <button type="button" className={styles.btnGhost} onClick={back}>Back</button>
      <button type="button" className={styles.btnPrimary} onClick={next} disabled={selected.length === 0}>{step === QUESTIONS.length - 1 ? "Continue" : "Next"}</button>
    </div>
  </div>
}
