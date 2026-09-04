import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { api, type Source, type Document } from "../api/client"
import { Skeleton } from "../components/Skeleton"

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; source: Source; documents: Document[] }

export function SourceDetail() {
  const { sourceId } = useParams()
  const navigate = useNavigate()
  const [state, setState] = useState<State>({ status: "loading" })

  useEffect(() => {
    let cancelled = false
    setState({ status: "loading" })

    const id = Number(sourceId)
    Promise.all([api.getSource(id), api.getDocuments()])
      .then(([source, documents]) => {
        if (cancelled) return
        const matchingDocuments = documents.filter((d) => d.source_id === id)
        if (matchingDocuments.length === 1) {
          navigate(`/app/material/${matchingDocuments[0].id}?mode=notes`, { replace: true })
          return
        }
        setState({
          status: "loaded",
          source,
          documents: matchingDocuments
        })
      })
      .catch((err) => {
        if (cancelled) return
        setState({
          status: "error",
          message: err instanceof Error ? err.message : "Something went wrong"
        })
      })

    return () => {
      cancelled = true
    }
  }, [navigate, sourceId])

  return (
    <div className="page">
      <nav className="breadcrumbs">
        <Link to="/app">Library</Link>
        <span> / </span>
        <span>Choose study material</span>
      </nav>

      {state.status === "loading" && <Skeleton rows={2} />}

      {state.status === "error" && (
        <p className="error">Failed to load this source: {state.message}</p>
      )}

      {state.status === "loaded" && (
        <>
          <div className="page-header">
            <h1>Choose a study material</h1>
            <p className="page-subtitle">This link contains more than one saved material.</p>
          </div>

          {state.documents.length === 0 ? (
            <p className="empty">No study materials are available here. Return to your library.</p>
          ) : (
            <div className="card-grid">
              {state.documents.map((document) => (
                <Link key={document.id} to={`/app/material/${document.id}?mode=notes`} className="card card-link-wrap">
                  <div className="card-title">{document.title.replace(/\.(pdf|docx|pptx)$/i, "") || "Untitled material"}</div>
                  <div className="card-meta">Open study material →</div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
