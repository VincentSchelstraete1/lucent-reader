import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { api, type Document, type Note, type Quiz } from "../api/client"
import { NoteCard } from "../components/NoteCard"
import { QuizCard } from "../components/QuizCard"
import { Skeleton } from "../components/Skeleton"

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; document: Document; notes: Note[]; quizzes: Quiz[] }

type ActionState = "idle" | "working" | "error"

export function DocumentDetail() {
  const { documentId } = useParams()
  const navigate = useNavigate()
  const [state, setState] = useState<State>({ status: "loading" })
  const [noteAction, setNoteAction] = useState<ActionState>("idle")
  const [quizAction, setQuizAction] = useState<ActionState>("idle")

  const id = Number(documentId)

  function load() {
    setState({ status: "loading" })
    Promise.all([api.getDocument(id), api.getNotes(), api.getQuizzesForDocument(id)])
      .then(([document, notes, quizzes]) => {
        setState({
          status: "loaded",
          document,
          notes: notes.filter((n) => n.document_id === id),
          quizzes
        })
      })
      .catch((err) => {
        setState({
          status: "error",
          message: err instanceof Error ? err.message : "Something went wrong"
        })
      })
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId])

  async function handleGenerateNote() {
    setNoteAction("working")
    try {
      await api.generateNote(id)
      setNoteAction("idle")
      load()
    } catch {
      setNoteAction("error")
    }
  }

  async function handleGenerateQuiz() {
    setQuizAction("working")
    try {
      const quiz = await api.generateQuiz(id)
      setQuizAction("idle")
      navigate(`/quizzes/${quiz.id}`)
    } catch {
      setQuizAction("error")
    }
  }

  return (
    <div className="page">
      <nav className="breadcrumbs">
        <Link to="/">Library</Link>
        {state.status === "loaded" && (
          <>
            <span> / </span>
            <Link to={`/sources/${state.document.source_id}`}>Source</Link>
          </>
        )}
        <span> / </span>
        <span>{state.status === "loaded" ? state.document.title : "Document"}</span>
      </nav>

      {state.status === "loading" && <Skeleton rows={2} />}

      {state.status === "error" && (
        <p className="error">Failed to load this document: {state.message}</p>
      )}

      {state.status === "loaded" && (
        <>
          <div className="page-header">
            <h1>{state.document.title}</h1>
            <p className="page-subtitle">
              Updated {new Date(state.document.updated_at).toLocaleString()}
            </p>
          </div>

          <div className="document-content">{state.document.content}</div>

          <div className="action-row">
            <button
              className="btn btn-primary"
              disabled={noteAction === "working"}
              onClick={handleGenerateNote}
            >
              {noteAction === "working" ? "Generating note..." : "Generate structured note"}
            </button>
            <button
              className="btn btn-primary"
              disabled={quizAction === "working"}
              onClick={handleGenerateQuiz}
            >
              {quizAction === "working" ? "Generating quiz..." : "Generate quiz"}
            </button>
          </div>
          {noteAction === "error" && <p className="error">Couldn't generate a note. Try again.</p>}
          {quizAction === "error" && <p className="error">Couldn't generate a quiz. Try again.</p>}

          <h2>Quizzes ({state.quizzes.length})</h2>
          {state.quizzes.length === 0 ? (
            <p className="empty">No quizzes yet - generate one above.</p>
          ) : (
            <div className="card-grid">
              {state.quizzes.map((quiz) => (
                <QuizCard key={quiz.id} quiz={quiz} />
              ))}
            </div>
          )}

          <h2>Notes ({state.notes.length})</h2>
          {state.notes.length === 0 ? (
            <p className="empty">No notes saved for this document yet.</p>
          ) : (
            <div className="card-grid">
              {state.notes.map((note) => (
                <NoteCard key={note.id} note={note} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
