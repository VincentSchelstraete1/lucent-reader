import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { OnboardingFlower } from "./OnboardingFlower"
import { StepLearningGoals, LEARNING_GOAL_OPTIONS } from "./StepLearningGoals"
import { StepHelpPreferences } from "./StepHelpPreferences"
import { StepReady } from "./StepReady"

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export function OnboardingFlow() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [learningGoals, setLearningGoals] = useState<string[]>([])
  const [helpPreferences, setHelpPreferences] = useState<string[]>([])
  const [pulse, setPulse] = useState(0)

  function toggleLearningGoal(value: string) {
    setLearningGoals((prev) => toggle(prev, value))
    setPulse((p) => p + 1)
  }

  function toggleHelpPreference(value: string) {
    setHelpPreferences((prev) => toggle(prev, value))
    setPulse((p) => p + 1)
  }

  const stage = step === 0 ? "bud" : step === 1 ? "opening" : "bloom"
  const blend = step === 0 ? Math.min(learningGoals.length / LEARNING_GOAL_OPTIONS.length, 1) : 0

  return (
    <>
      <OnboardingFlower stage={stage} blend={blend} pulseKey={pulse} />

      {step === 0 && (
        <StepLearningGoals selected={learningGoals} onToggle={toggleLearningGoal} onNext={() => setStep(1)} />
      )}

      {step === 1 && (
        <StepHelpPreferences
          selected={helpPreferences}
          onToggle={toggleHelpPreference}
          onNext={() => setStep(2)}
          onBack={() => setStep(0)}
        />
      )}

      {step === 2 && <StepReady onStart={() => navigate("/app")} onBack={() => setStep(1)} />}
    </>
  )
}
