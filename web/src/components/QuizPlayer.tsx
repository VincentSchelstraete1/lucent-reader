import { useState } from "react"
import { api, type Quiz } from "../api/client"

export function QuizPlayer({ quiz }: { quiz: Quiz }) {
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [correctCount, setCorrectCount] = useState(0)
  const [finished, setFinished] = useState(false)
  const [attemptSaved, setAttemptSaved] = useState(false)

  const question = quiz.questions[index]
  const isLast = index === quiz.questions.length - 1

  function selectChoice(choiceIndex: number) {
    if (selected !== null) return
    setSelected(choiceIndex)
    if (choiceIndex === question.correct_index) {
      setCorrectCount((c) => c + 1)
    }
  }

  function next() {
    if (isLast) {
      setFinished(true)
      const finalCorrect = correctCount
      api
        .submitQuizAttempt(quiz.id, { score: finalCorrect, total: quiz.questions.length })
        .then(() => setAttemptSaved(true))
        .catch(() => setAttemptSaved(false))
      return
    }
    setIndex((i) => i + 1)
    setSelected(null)
  }

  function retake() {
    setIndex(0)
    setSelected(null)
    setCorrectCount(0)
    setFinished(false)
    setAttemptSaved(false)
  }

  if (finished) {
    return (
      <div className="quiz-result">
        <h2>
          {correctCount} / {quiz.questions.length}
        </h2>
        <p className="page-subtitle">
          {correctCount === quiz.questions.length
            ? "Perfect score!"
            : "Nice work - review the explanations above and try again anytime."}
        </p>
        {!attemptSaved && <p className="empty">(Result not saved - couldn't reach the server.)</p>}
        <button className="btn btn-primary" onClick={retake}>
          Retake quiz
        </button>
      </div>
    )
  }

  return (
    <div className="quiz-player">
      <div className="quiz-progress">
        Question {index + 1} of {quiz.questions.length}
      </div>
      <h2 className="quiz-question">{question.question}</h2>

      <div className="quiz-choices">
        {question.choices.map((choice, i) => {
          let className = "quiz-choice"
          if (selected !== null) {
            if (i === question.correct_index) className += " quiz-choice-correct"
            else if (i === selected) className += " quiz-choice-incorrect"
          }
          return (
            <button
              key={i}
              className={className}
              disabled={selected !== null}
              onClick={() => selectChoice(i)}
            >
              {choice}
            </button>
          )
        })}
      </div>

      {selected !== null && (
        <div className={selected === question.correct_index ? "quiz-feedback quiz-feedback-correct" : "quiz-feedback quiz-feedback-incorrect"}>
          <strong>{selected === question.correct_index ? "Correct!" : "Not quite."}</strong>
          <p>{question.explanation}</p>
        </div>
      )}

      {selected !== null && (
        <button className="btn btn-primary" onClick={next}>
          {isLast ? "See score" : "Next question"}
        </button>
      )}
    </div>
  )
}
