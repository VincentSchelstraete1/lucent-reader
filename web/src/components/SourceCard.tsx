import { Link } from "react-router-dom"
import type { Source } from "../api/client"

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

export function SourceCard({ source }: { source: Source }) {
  return (
    <Link to={`/sources/${source.id}`} className="card card-link-wrap">
      <div className="card-title">
        {source.url ? hostnameOf(source.url) : "Untitled source"}
        <span className="badge badge-source">{source.type}</span>
      </div>
      {source.url && <div className="card-subtext">{source.url}</div>}
      <div className="card-meta">Added {new Date(source.created_at).toLocaleString()}</div>
    </Link>
  )
}
