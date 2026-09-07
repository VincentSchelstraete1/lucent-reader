import { useEffect, useState } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
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
            <Link to={`/app/material/${state.quiz.document_id}?mode=notes`}>Study material</Link>
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

export function QuizGenerationPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const documentId = Number(searchParams.get("document_id"))
  const [status, setStatus] = useState<"working" | "error">("working")
  const [message, setMessage] = useState("")

  useEffect(() => {
    let cancelled = false
    if (!Number.isFinite(documentId) || documentId <= 0) {
      setStatus("error")
      setMessage("This material could not be identified.")
      return () => { cancelled = true }
    }
    api.generateQuiz(documentId).then((quiz) => {
      if (!cancelled) navigate(`/quizzes/${quiz.id}`, { replace: true })
    }).catch((error) => {
      if (!cancelled) {
        setStatus("error")
        setMessage(error instanceof Error ? error.message : "Lucent could not create this quiz.")
      }
    })
    return () => { cancelled = true }
  }, [documentId, navigate])

  return <div className="page quiz-generation" aria-live="polite">
    <nav className="breadcrumbs"><Link to="/app">Library</Link><span> / </span><span>Quiz</span></nav>
    {status === "working" ? <>
      <p className="note-kicker">Preparing your quiz</p>
      <h1>Building a quiz from this material</h1>
      <p className="page-subtitle">Lucent is selecting questions that test the important ideas.</p>
      <div className="quiz-generation-track" role="progressbar" aria-label="Generating quiz"><span /></div>
      <p className="quiz-generation-status">Generating questions…</p>
    </> : <>
      <p className="error" role="alert">{message}</p>
      {documentId > 0 && <Link className="btn btn-secondary" to={`/app/material/${documentId}?mode=notes`}>Back to study material</Link>}
    </>}
  </div>
}
