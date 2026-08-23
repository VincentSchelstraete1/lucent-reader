import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { api, type Quiz } from "../api/client"
import { QuizPlayer } from "../components/QuizPlayer"
import { Skeleton } from "../components/Skeleton"

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; quiz: Quiz }

export function QuizPage() {
  const { quizId } = useParams()
  const [state, setState] = useState<State>({ status: "loading" })

  useEffect(() => {
    let cancelled = false
    api
      .getQuiz(Number(quizId))
      .then((quiz) => {
        if (!cancelled) setState({ status: "loaded", quiz })
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof Error ? err.message : "Something went wrong"
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [quizId])

  return (
    <div className="page">
      <nav className="breadcrumbs">
        <Link to="/app">Library</Link>
        {state.status === "loaded" && (
          <>
            <span> / </span>
            <Link to={`/documents/${state.quiz.document_id}`}>Document</Link>
          </>
        )}
        <span> / </span>
        <span>Quiz</span>
      </nav>

      {state.status === "loading" && <Skeleton rows={1} />}
      {state.status === "error" && <p className="error">Failed to load this quiz: {state.message}</p>}
      {state.status === "loaded" && (
        <>
          <div className="page-header">
            <h1>{state.quiz.title}</h1>
          </div>
          <QuizPlayer quiz={state.quiz} key={state.quiz.id} />
        </>
      )}
    </div>
  )
}
