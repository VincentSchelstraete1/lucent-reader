import { useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { api, type Document, type Note, type Source } from "../api/client"
import { Skeleton } from "../components/Skeleton"

type Material = { document: Document; source?: Source; note?: Note }
type State = { status: "loading" | "error" | "loaded"; materials: Material[]; message?: string }
type LibraryView = "library" | "learn" | "flashcards" | "quiz"

function materialType(material: Material) {
  const title = material.document.title.toLowerCase()
  if (title.endsWith(".pdf")) return "PDF"
  if (title.endsWith(".docx")) return "DOCX"
  if (title.endsWith(".pptx")) return "PPTX"
  return material.source?.type === "upload" ? "Document" : "Website"
}

export function formatMaterialTitle(title: string) {
  const cleaned = title.replace(/^(pdf|docx|pptx):/i, "").replace(/\.(pdf|docx|pptx)$/i, "").replace(/\s+/g, " ").trim()
  if (!cleaned) return "Untitled material"
  if (!/[_-]/.test(cleaned)) return cleaned
  return cleaned.split(/[_-]+/).filter(Boolean).map((word) => word.length <= 3 ? word.toUpperCase() : `${word[0].toUpperCase()}${word.slice(1)}`).join(" ")
}

function materialTitle(material: Material) {
  return formatMaterialTitle(material.document.title)
}

function noteSummary(note?: Note) {
  if (!note) return "Ready to create notes"
  try {
    const payload = JSON.parse(note.content) as { sectionNotes?: unknown[] }
    return `${payload.sectionNotes?.length ?? 0} sections · Notes ready`
  } catch { return "Notes ready" }
}

function noteSectionCount(note?: Note) {
  if (!note) return 0
  try { return (JSON.parse(note.content) as { sectionNotes?: unknown[] }).sectionNotes?.length ?? 0 } catch { return 0 }
}

function noteExperienceCount(note?: Note) {
  if (!note) return 0
  try {
    const sections = (JSON.parse(note.content) as { sectionNotes?: Array<{ components?: Array<{ kind?: string }> }> }).sectionNotes ?? []
    return sections.reduce((count, section) => count + (section.components ?? []).filter((component) => component.kind === "walkthrough").length, 0)
  } catch { return 0 }
}

function sourceDomain(url?: string | null) {
  if (!url) return ""
  try { return new URL(url).hostname }
  catch { return "" }
}

export function Library() {
  const [state, setState] = useState<State>({ status: "loading", materials: [] })
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState<"all" | "documents" | "websites">("all")
  const [sort, setSort] = useState<"recent" | "name">("recent")
  const [newOpen, setNewOpen] = useState(false)
  const [openMenu, setOpenMenu] = useState<number | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingTitle, setEditingTitle] = useState("")
  const [deleteTarget, setDeleteTarget] = useState<Material | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const view = (searchParams.get("view") as LibraryView | null) ?? "library"

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
    if (view === "learn" && noteExperienceCount(material.note) === 0) return false
    if (view === "flashcards" && !material.note) return false
    if (view === "quiz" && !material.note) return false
    const haystack = `${materialTitle(material)} ${material.source?.url ?? ""}`.toLowerCase()
    const matchesQuery = !query.trim() || haystack.includes(query.trim().toLowerCase())
    const type = materialType(material)
    const matchesFilter = filter === "all" || (filter === "documents" ? type !== "Website" : type === "Website")
    return matchesQuery && matchesFilter
  }).sort((a, b) => sort === "name" ? materialTitle(a).localeCompare(materialTitle(b)) : new Date(b.document.updated_at).getTime() - new Date(a.document.updated_at).getTime()), [filter, query, sort, state.materials, view])

  async function renameMaterial(material: Material) {
    const title = editingTitle.trim()
    if (!title) return
    try {
      const document = await api.updateDocument(material.document.id, { title })
      setState((current) => ({ ...current, materials: current.materials.map((item) => item.document.id === document.id ? { ...item, document } : item) }))
      setEditingId(null); setOpenMenu(null); setActionError(null)
    } catch { setActionError("We couldn't rename this material. Please try again.") }
  }

  async function deleteMaterial() {
    if (!deleteTarget) return
    try {
      await api.deleteDocument(deleteTarget.document.id)
      setState((current) => ({ ...current, materials: current.materials.filter((item) => item.document.id !== deleteTarget.document.id) }))
      setDeleteTarget(null); setOpenMenu(null); setActionError(null)
    } catch { setActionError("We couldn't delete this material. Please try again."); setDeleteTarget(null) }
  }

  return <div className="page library-page">
    <header className="library-header"><div><p className="note-kicker">Lucent library</p><h1>{view === "library" ? "Study materials" : view === "learn" ? "Learn" : view === "flashcards" ? "Flashcards" : "Quiz"}</h1><p className="page-subtitle">{view === "library" ? "Your lectures, chapters, and articles in one place." : view === "learn" ? "Open a guided experience from any material that has one." : view === "flashcards" ? "Review recall cards from your saved study materials." : "Choose a material to test your understanding."}</p></div><div className="library-new-wrap"><button className="btn btn-primary" type="button" aria-haspopup="menu" aria-expanded={newOpen} onKeyDown={(event) => { if (event.key === "Escape") setNewOpen(false) }} onClick={() => setNewOpen((open) => !open)}>+ New</button>{newOpen && <div className="library-new-menu" role="menu"><Link to="/app/notes" role="menuitem" onClick={() => setNewOpen(false)}>Upload document <small>PDF, DOCX, PPTX</small></Link><Link to="/app/notes" role="menuitem" onClick={() => setNewOpen(false)}>Add webpage <small>Save a webpage to Lucent</small></Link></div>}</div></header>
    <div className="library-toolbar"><label className="library-search"><span className="sr-only">Search materials</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search materials" /></label><div className="library-controls"><div className="library-filters" role="group" aria-label="Filter materials">{([['all', 'All'], ['documents', 'Documents'], ['websites', 'Websites']] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{label}</button>)}</div><label className="library-sort">Sort <select value={sort} onChange={(event) => setSort(event.target.value as "recent" | "name")}><option value="recent">Recent</option><option value="name">Name</option></select></label></div></div>
    {state.status === "loading" && <Skeleton rows={3} />}
    {state.status === "error" && <p className="error">Could not load your study materials: {state.message}</p>}
    {state.status === "loaded" && materials.length === 0 && (state.materials.length === 0 ? <section className="library-empty"><h2>Your library is empty</h2><p>Add a lecture, article, or document and Lucent will turn it into a learning experience.</p><Link className="btn btn-primary" to="/app/notes">+ Add your first material</Link></section> : <section className="library-empty"><h2>No materials match{query ? ` “${query}”` : " this filter"}</h2><p>Try a different search or filter.</p>{(query || filter !== "all") && <button className="btn btn-secondary" type="button" onClick={() => { setQuery(""); setFilter("all") }}>Clear search and filters</button>}</section>)}
    {actionError && <p className="error" role="alert">{actionError}</p>}
    {state.status === "loaded" && materials.length > 0 && <section className="library-list" aria-label="Study materials"><h2>{view === "library" ? "All materials" : "Study materials"}</h2>{materials.map((material) => <div className="material-row" key={material.document.id}><Link className="material-row-main" to={`/app/material/${material.document.id}${view === "learn" ? "?mode=learn" : view === "flashcards" ? "?mode=flashcards" : "?mode=notes"}`}><div><h3>{materialTitle(material)}</h3><p>{materialType(material)}{materialType(material) === "Website" && sourceDomain(material.source?.url) ? ` · ${sourceDomain(material.source?.url)}` : ""}</p></div><div className="material-status">{noteSummary(material.note)}{noteExperienceCount(material.note) > 0 && <span> · {noteExperienceCount(material.note)} walkthrough{noteExperienceCount(material.note) === 1 ? "" : "s"}</span>}</div></Link><div className="material-actions"><button type="button" className="material-menu-button" aria-label={`Actions for ${materialTitle(material)}`} aria-expanded={openMenu === material.document.id} onClick={() => setOpenMenu(openMenu === material.document.id ? null : material.document.id)} onKeyDown={(event) => { if (event.key === "Escape") setOpenMenu(null) }}>•••</button>{openMenu === material.document.id && <div className="material-menu" role="menu"><button type="button" role="menuitem" onClick={() => { setEditingId(material.document.id); setEditingTitle(material.document.title.replace(/\.(pdf|docx|pptx)$/i, "")); setOpenMenu(null) }}>Rename</button>{material.source?.url && materialType(material) === "Website" && <a href={material.source.url} target="_blank" rel="noreferrer" role="menuitem">Open original source</a>}<button type="button" role="menuitem" onClick={() => { setDeleteTarget(material); setOpenMenu(null) }}>Delete</button></div>}</div>{editingId === material.document.id && <form className="material-rename" onSubmit={(event) => { event.preventDefault(); void renameMaterial(material) }}><label htmlFor={`rename-${material.document.id}`}>Rename material</label><input id={`rename-${material.document.id}`} value={editingTitle} onChange={(event) => setEditingTitle(event.target.value)} autoFocus /><button type="submit" className="btn btn-primary">Save</button><button type="button" className="btn btn-secondary" onClick={() => setEditingId(null)}>Cancel</button></form>}</div>)}</section>}
    {deleteTarget && <div className="dialog-backdrop" role="presentation"><section className="library-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-material-title"><h2 id="delete-material-title">Delete “{materialTitle(deleteTarget)}”?</h2><p>This removes the material and its Lucent study content.</p><div><button type="button" className="btn btn-secondary" onClick={() => setDeleteTarget(null)}>Cancel</button><button type="button" className="btn btn-danger" onClick={() => void deleteMaterial()}>Delete</button></div></section></div>}
  </div>
}
