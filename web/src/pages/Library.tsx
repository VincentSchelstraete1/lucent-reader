import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { api, type Document, type Note, type Source } from "../api/client"
import { Skeleton } from "../components/Skeleton"

type Material = { document: Document; source?: Source; note?: Note }
type State = { status: "loading" | "error" | "loaded"; materials: Material[]; message?: string }

function materialType(material: Material) {
  const title = material.document.title.toLowerCase()
  if (title.endsWith(".pdf")) return "PDF"
  if (title.endsWith(".docx")) return "DOCX"
  if (title.endsWith(".pptx")) return "PPTX"
  return material.source?.type === "upload" ? "Document" : "Website"
}

function materialTitle(material: Material) {
  return material.document.title.replace(/\.(pdf|docx|pptx)$/i, "").trim() || "Untitled material"
}

function noteSummary(note?: Note) {
  if (!note) return "Ready to create notes"
  try {
    const payload = JSON.parse(note.content) as { sectionNotes?: unknown[] }
    return `${payload.sectionNotes?.length ?? 0} sections · Notes ready`
  } catch { return "Notes ready" }
}

function sourceDomain(url?: string | null) {
  if (!url) return ""
  try { return new URL(url).hostname }
  catch { return "" }
}

export function Library() {
  const [state, setState] = useState<State>({ status: "loading", materials: [] })
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<"all" | "documents" | "websites">("all")
  const [newOpen, setNewOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.getDocuments(), api.getSources(), api.getNotes()]).then(([documents, sources, notes]) => {
      if (cancelled) return
      const bySource = new Map(sources.map((source) => [source.id, source]))
      const byDocument = new Map(notes.filter((note) => note.content_type === "section_note").map((note) => [note.document_id, note]))
      setState({ status: "loaded", materials: documents.map((document) => ({ document, source: bySource.get(document.source_id), note: byDocument.get(document.id) })) })
    }).catch((error) => { if (!cancelled) setState({ status: "error", materials: [], message: error instanceof Error ? error.message : "Could not load your library" }) })
    return () => { cancelled = true }
  }, [])

  const materials = useMemo(() => state.materials.filter((material) => {
    const haystack = `${materialTitle(material)} ${material.source?.url ?? ""}`.toLowerCase()
    const matchesQuery = !query.trim() || haystack.includes(query.trim().toLowerCase())
    const type = materialType(material)
    const matchesFilter = filter === "all" || (filter === "documents" ? type !== "Website" : type === "Website")
    return matchesQuery && matchesFilter
  }), [filter, query, state.materials])

  return <div className="page library-page">
    <header className="library-header"><div><p className="note-kicker">Lucent library</p><h1>Study materials</h1><p className="page-subtitle">Your lectures, chapters, and articles in one place.</p></div><div className="library-new-wrap"><button className="btn btn-primary" type="button" aria-expanded={newOpen} onClick={() => setNewOpen((open) => !open)}>+ New</button>{newOpen && <div className="library-new-menu" role="menu"><Link to="/app/notes" role="menuitem" onClick={() => setNewOpen(false)}>Upload document <small>PDF, DOCX, PPTX</small></Link><Link to="/app/notes" role="menuitem" onClick={() => setNewOpen(false)}>Add webpage <small>Use an existing saved source</small></Link></div>}</div></header>
    <div className="library-toolbar"><label className="library-search"><span className="sr-only">Search materials</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search materials" /></label><div className="library-filters" role="group" aria-label="Filter materials">{([['all', 'All'], ['documents', 'Documents'], ['websites', 'Websites']] as const).map(([value, label]) => <button key={value} type="button" className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{label}</button>)}</div></div>
    {state.status === "loading" && <Skeleton rows={3} />}
    {state.status === "error" && <p className="error">Could not load your study materials: {state.message}</p>}
    {state.status === "loaded" && materials.length === 0 && <section className="library-empty"><h2>Your library is empty</h2><p>Add a lecture, article, or document and Lucent will turn it into a learning experience.</p><Link className="btn btn-primary" to="/app/notes">+ Add your first material</Link></section>}
    {state.status === "loaded" && materials.length > 0 && <section className="library-list" aria-label="Study materials"><h2>Recent materials</h2>{materials.map((material) => <Link className="material-row" key={material.document.id} to={`/app/material/${material.document.id}`}><div><h3>{materialTitle(material)}</h3><p>{materialType(material)}{materialType(material) === "Website" && sourceDomain(material.source?.url) ? ` · ${sourceDomain(material.source?.url)}` : ""}</p></div><div className="material-status">{noteSummary(material.note)}<span>Open →</span></div></Link>)}</section>}
  </div>
}
