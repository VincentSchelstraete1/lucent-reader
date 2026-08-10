import { useEffect, useState } from "react"

import {
  ASSESSMENT_PASSAGES,
  computeTargetGradeLevel,
  getTargetGradeLevel,
  setTargetGradeLevel,
  type AssessmentResponse
} from "~lib/reading-level"

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
  const [stepIndex, setStepIndex] = useState(0)
  const [responses, setResponses] = useState<AssessmentResponse[]>([])

  useEffect(() => {
    getTargetGradeLevel().then(setCurrentLevel)
  }, [])

  function startAssessment() {
    setStepIndex(0)
    setResponses([])
    setView("assessment")
  }

  async function answer(response: AssessmentResponse) {
    const next = [...responses, response]

    if (next.length < ASSESSMENT_PASSAGES.length) {
      setResponses(next)
      setStepIndex(stepIndex + 1)
      return
    }

    const level = computeTargetGradeLevel(next)
    await setTargetGradeLevel(level)
    setCurrentLevel(level)
    setView("done")
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
          Adaptive Reading Assistant
        </h1>
        <p style={{ fontSize: 14, color: tokens.captionText, marginBottom: 28 }}>
          Reading level assessment
        </p>

        {view === "intro" && (
          <div>
            <p style={{ fontSize: 15, lineHeight: 1.6 }}>
              You'll see three short passages. For each one, just say
              whether it felt too easy, too hard, or about right. That's
              used to pick a target reading level for simplified text — you
              can always change it later from the dropdown on the page too.
            </p>
            {currentLevel !== null && (
              <p
                style={{
                  fontSize: 13,
                  color: tokens.captionText,
                  marginTop: 12
                }}>
                Current target level: Grade {currentLevel}
              </p>
            )}
            <button
              onClick={startAssessment}
              style={primaryButtonStyle}>
              {currentLevel !== null ? "Take assessment" : "Start"}
            </button>
          </div>
        )}

        {view === "assessment" && (
          <div>
            <p
              style={{
                fontSize: 13,
                color: tokens.captionText,
                marginBottom: 10
              }}>
              Passage {stepIndex + 1} of {ASSESSMENT_PASSAGES.length}
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
              {ASSESSMENT_PASSAGES[stepIndex].text}
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

        {view === "done" && (
          <div>
            <div
              style={{
                backgroundColor: tokens.badgeDoneBg,
                color: tokens.badgeDoneText,
                borderRadius: 12,
                padding: 20,
                fontSize: 15
              }}>
              Target reading level set to <strong>Grade {currentLevel}</strong>.
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
