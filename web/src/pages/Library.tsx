import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api, type Source } from "../api/client"
import { SourceCard } from "../components/SourceCard"
import { Skeleton } from "../components/Skeleton"

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; sources: Source[] }

export function Library() {
  const [state, setState] = useState<State>({ status: "loading" })

  useEffect(() => {
    let cancelled = false

    api
      .getSources()
      .then((sources) => {
        if (!cancelled) setState({ status: "loaded", sources })
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
  }, [])

  return (
    <div className="page">
      <div className="page-header" data-tour="library-heading">
        <h1>Your Library</h1>
        <p className="page-subtitle">Everything you've saved from the web, organized by source.</p>
        <Link className="btn btn-primary" to="/app/notes">Create notes from a document</Link>
      </div>

      <div data-tour="library-content">
      {state.status === "loading" && <Skeleton rows={3} />}

      {state.status === "error" && (
        <p className="error">Failed to load your library: {state.message}</p>
      )}
      </div>

      {state.status === "loaded" && (
        state.sources.length === 0 ? (
          <p className="empty">
            Nothing saved yet. Highlight, explain, or simplify something with the Lucent
            extension and hit Save to see it here.
          </p>
        ) : (
          <div className="card-grid">
            {state.sources.map((source) => (
              <SourceCard key={source.id} source={source} />
            ))}
          </div>
        )
      )}
    </div>
  )
}
