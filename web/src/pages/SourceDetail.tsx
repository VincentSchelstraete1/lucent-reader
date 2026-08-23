import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { api, type Source, type Document } from "../api/client"
import { DocumentCard } from "../components/DocumentCard"
import { Skeleton } from "../components/Skeleton"

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; source: Source; documents: Document[] }

export function SourceDetail() {
  const { sourceId } = useParams()
  const [state, setState] = useState<State>({ status: "loading" })

  useEffect(() => {
    let cancelled = false
    setState({ status: "loading" })

    const id = Number(sourceId)
    Promise.all([api.getSource(id), api.getDocuments()])
      .then(([source, documents]) => {
        if (cancelled) return
        setState({
          status: "loaded",
          source,
          documents: documents.filter((d) => d.source_id === id)
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
  }, [sourceId])

  return (
    <div className="page">
      <nav className="breadcrumbs">
        <Link to="/app">Library</Link>
        <span> / </span>
        <span>{state.status === "loaded" ? state.source.type : "Source"}</span>
      </nav>

      {state.status === "loading" && <Skeleton rows={2} />}

      {state.status === "error" && (
        <p className="error">Failed to load this source: {state.message}</p>
      )}

      {state.status === "loaded" && (
        <>
          <div className="page-header">
            <h1>{state.source.url || "Untitled source"}</h1>
            <p className="page-subtitle">
              {state.source.type} · added {new Date(state.source.created_at).toLocaleString()}
            </p>
          </div>

          <h2>Documents ({state.documents.length})</h2>
          {state.documents.length === 0 ? (
            <p className="empty">No documents saved from this source yet.</p>
          ) : (
            <div className="card-grid">
              {state.documents.map((document) => (
                <DocumentCard key={document.id} document={document} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
