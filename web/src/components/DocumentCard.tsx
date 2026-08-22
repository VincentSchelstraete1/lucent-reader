import { Link } from "react-router-dom"
import type { Document } from "../api/client"

export function DocumentCard({ document }: { document: Document }) {
  return (
    <Link to={`/documents/${document.id}`} className="card card-link-wrap">
      <div className="card-title">{document.title}</div>
      <div className="card-body">{document.content.slice(0, 200)}</div>
      <div className="card-meta">Updated {new Date(document.updated_at).toLocaleString()}</div>
    </Link>
  )
}
