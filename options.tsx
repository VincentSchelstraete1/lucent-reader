import { useEffect, useState } from "react"

import {
  type AssessmentPassage,
  type AssessmentResponse,
  MAX_QUIZ_QUESTIONS,
  type QuizState,
  applyQuizAnswer,
  finalizeQuizResult,
  getTargetGradeLevel,
  getTierLabel,
  isQuizConfident,
  pickPassageForTier,
  setTargetGradeLevel,
  startQuizState
} from "~lib/reading-level"
import {
  DEFAULT_USE_POPUP_FALLBACK,
  getUsePopupFallback,
  setUsePopupFallback
} from "~lib/side-panel-mode"

const tokens = {
  readingBg: "#F5F1E8",
  readingText: "#2C2C2A",
  accentTeal: "#1D9E75",
  badgeDoneBg: "#EEEDFE",
  badgeDoneText: "#26215C",
  captionText: "#5E5E5B"
}

type View = "intro" | "assessment" | "done"

const ANSWER_OPTIONS: { value: AssessmentResponse; label: string }[] = [
  { value: "too_easy", label: "Too easy" },
  { value: "just_right", label: "Just right" },
  { value: "too_hard", label: "Too hard" }
]

function OptionsPage() {
  const [view, setView] = useState<View>("intro")
  const [currentLevel, setCurrentLevel] = useState<number | null>(null)
  const [questionCount, setQuestionCount] = useState(0)
  const [quizState, setQuizState] = useState<QuizState>(startQuizState())
  const [passage, setPassage] = useState<AssessmentPassage | null>(null)
  const [usePopupFallback, setUsePopupFallbackState] = useState(DEFAULT_USE_POPUP_FALLBACK)

  useEffect(() => {
    getTargetGradeLevel().then(setCurrentLevel)
    getUsePopupFallback().then(setUsePopupFallbackState)
  }, [])

  async function handleUsePopupFallbackChange(next: boolean) {
    setUsePopupFallbackState(next)
    await setUsePopupFallback(next)
  }

  function startAssessment() {
    const initialState = startQuizState()
    setQuizState(initialState)
    setPassage(pickPassageForTier(initialState.tierIndex, initialState.usedPassageTexts))
    setQuestionCount(0)
    setView("assessment")
  }

  async function answer(response: AssessmentResponse) {
    if (!passage) return

    const nextState = applyQuizAnswer(quizState, passage, response)
    const nextCount = questionCount + 1

    if (nextCount >= MAX_QUIZ_QUESTIONS || isQuizConfident(nextState)) {
      const level = finalizeQuizResult(nextState)
      await setTargetGradeLevel(level)
      setCurrentLevel(level)
      setQuizState(nextState)
      setView("done")
      return
    }

    setQuizState(nextState)
    setQuestionCount(nextCount)
    setPassage(pickPassageForTier(nextState.tierIndex, nextState.usedPassageTexts))
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: tokens.readingBg,
        color: tokens.readingText,
        fontFamily: "Inter, sans-serif",
        padding: "40px 24px",
        display: "flex",
        justifyContent: "center"
      }}>
      <div style={{ maxWidth: 480, width: "100%" }}>
        <h1 style={{ fontSize: 22, marginBottom: 4 }}>
          Lucent Reader
        </h1>
        <p style={{ fontSize: 14, color: tokens.captionText, marginBottom: 28 }}>
          Reading level assessment
        </p>

        <div
          style={{
            border: `1px solid ${tokens.captionText}`,
            borderRadius: 12,
            padding: "14px 16px",
            marginBottom: 28
          }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12
            }}>
            <span style={{ fontSize: 14 }}>Toolbar icon opens a popup window</span>
            <button
              onClick={() => handleUsePopupFallbackChange(!usePopupFallback)}
              style={{
                padding: "6px 12px",
                borderRadius: 20,
                border: "none",
                fontSize: 12,
                cursor: "pointer",
                backgroundColor: usePopupFallback ? tokens.accentTeal : tokens.captionText,
                color: "#FFFFFF"
              }}>
              {usePopupFallback ? "On" : "Off"}
            </button>
          </div>
          <p style={{ fontSize: 12, color: tokens.captionText, margin: "6px 0 0", lineHeight: 1.4 }}>
            Turn this on if clicking the Lucent icon (or the on-page panel toggle) doesn't
            open anything - some browsers don't support the native side panel Lucent uses by
            default, even though they don't report an error when it fails.
          </p>
        </div>

        {view === "intro" && (
          <div>
            <p style={{ fontSize: 15, lineHeight: 1.6 }}>
              You'll see a short passage at a time. Just say whether it felt
              too easy, too hard, or about right, and the next passage will
              adjust to match - usually just a few questions before we
              settle on a level. You can always change it later from the
              dropdown on the page too.
            </p>
            {currentLevel !== null && (
              <p
                style={{
                  fontSize: 13,
                  color: tokens.captionText,
                  marginTop: 12
                }}>
                Current target level: {getTierLabel(currentLevel)}
              </p>
            )}
            <button onClick={startAssessment} style={primaryButtonStyle}>
              {currentLevel !== null ? "Take assessment" : "Start"}
            </button>
          </div>
        )}

        {view === "assessment" && passage && (
          <div>
            <p
              style={{
                fontSize: 13,
                color: tokens.captionText,
                marginBottom: 10
              }}>
              Question {questionCount + 1} (up to {MAX_QUIZ_QUESTIONS})
            </p>
            <div
              style={{
                backgroundColor: "#FFFFFF",
                border: `1px solid ${tokens.captionText}`,
                borderRadius: 12,
                padding: 20,
                fontSize: 16,
                lineHeight: 1.7,
                marginBottom: 20
              }}>
              {passage.text}
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              {ANSWER_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  onClick={() => answer(option.value)}
                  style={answerButtonStyle}>
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {view === "done" && currentLevel !== null && (
          <div>
            <div
              style={{
                backgroundColor: tokens.badgeDoneBg,
                color: tokens.badgeDoneText,
                borderRadius: 12,
                padding: 20,
                fontSize: 15
              }}>
              Target reading level set to{" "}
              <strong>{getTierLabel(currentLevel)}</strong>.
            </div>
            <button onClick={startAssessment} style={secondaryButtonStyle}>
              Take assessment again
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

const primaryButtonStyle: React.CSSProperties = {
  marginTop: 20,
  padding: "10px 20px",
  borderRadius: 20,
  border: "none",
  backgroundColor: "#1D9E75",
  color: "#FFFFFF",
  fontSize: 14,
  cursor: "pointer"
}

const secondaryButtonStyle: React.CSSProperties = {
  marginTop: 16,
  padding: "10px 20px",
  borderRadius: 20,
  border: `1px solid ${tokens.captionText}`,
  backgroundColor: "#FFFFFF",
  color: tokens.readingText,
  fontSize: 14,
  cursor: "pointer"
}

const answerButtonStyle: React.CSSProperties = {
  flex: 1,
  padding: "10px 12px",
  borderRadius: 20,
  border: `1px solid ${tokens.captionText}`,
  backgroundColor: "#FFFFFF",
  color: tokens.readingText,
  fontSize: 13,
  cursor: "pointer"
}

export default OptionsPage
