import { useState } from "react"
import { Link } from "react-router-dom"
import { api, type Quiz } from "../api/client"

export function missedQuestions(quiz: Quiz, answers: Array<number | null>) {
  return quiz.questions.map((item, questionIndex) => ({ item, questionIndex, answer: answers[questionIndex] ?? null })).filter(({ item, answer }) => answer !== item.correct_index)
}

export function QuizPlayer({ quiz }: { quiz: Quiz }) {
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [correctCount, setCorrectCount] = useState(0)
  const [finished, setFinished] = useState(false)
  const [attemptSaved, setAttemptSaved] = useState(false)
  const [answers, setAnswers] = useState<Array<number | null>>(() => quiz.questions.map(() => null))

  const question = quiz.questions[index]
  const isLast = index === quiz.questions.length - 1

  function selectChoice(choiceIndex: number) {
    if (selected !== null) return
    setSelected(choiceIndex)
    setAnswers((current) => current.map((answer, questionIndex) => questionIndex === index ? choiceIndex : answer))
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
    setAnswers(quiz.questions.map(() => null))
  }

  if (finished) {
    const missed = missedQuestions(quiz, answers)
    return (
      <div className="quiz-result">
        <h2>
          {correctCount} / {quiz.questions.length}
        </h2>
        <p className="quiz-score-message">
          {correctCount === quiz.questions.length
            ? "Perfect score!"
            : "Nice work - review the explanations above and try again anytime."}
        </p>
        {!attemptSaved && <p className="empty">(Result not saved - couldn't reach the server.)</p>}
        {missed.length > 0 && <section className="quiz-review" aria-labelledby="review-heading"><p className="note-kicker">Targeted review</p><h3 id="review-heading">Revisit what tripped you up</h3>{missed.map(({ item, questionIndex, answer }) => <article key={questionIndex}><p className="quiz-review-question">{item.question}</p><p><strong>Your answer:</strong> {answer === null ? "No answer" : item.choices[answer]}</p><p><strong>Correct answer:</strong> {item.choices[item.correct_index]}</p><p>{item.explanation}</p>{item.section_id && <Link className="quiz-review-link" to={`/app/notes?document_id=${quiz.document_id}#${item.section_id}`}>Review this concept in your notes →</Link>}</article>)}</section>}
        <div className="quiz-result-actions"><Link className="btn" to={`/app/notes?document_id=${quiz.document_id}`}>Back to notes</Link><button className="btn btn-primary" onClick={retake}>Retake quiz</button></div>
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
