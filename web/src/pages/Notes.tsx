import { Fragment, useEffect, useState, type ChangeEvent } from "react"
import { api, type DocumentIngestionResult, type ProgressiveSection, type SectionNote } from "../api/client"

type State = { status: "idle" | "uploading" | "processing" | "complete" | "error"; filename?: string; sections?: ProgressiveSection[]; result?: DocumentIngestionResult; message?: string }

function ComponentView({ component }: { component: SectionNote["components"][number] }) {
  const c = component as any
  const [open, setOpen] = useState(false)
  if (c.kind === "flow" || c.kind === "relationship_map") {
    const nodes = c.nodes ?? []; const edges = c.edges ?? []
    return <div className="note-flow" aria-label={c.title}>{nodes.map((node: any, index: number) => <div key={String(node.id)}><button className="note-node" type="button" onClick={() => setOpen(!open)} aria-expanded={open}>{String(node.label)}</button>{open && node.explanation && <p className="note-detail">{String(node.explanation)}</p>}{index < nodes.length - 1 && <div className="note-edge"><span>↓</span><strong>{String(edges[index]?.relation ?? "then")}</strong></div>}</div>)}</div>
  }
  if (c.kind === "structure" && c.root) {
    const tree = (node: any): JSX.Element => <li><button className="note-node" type="button" onClick={() => setOpen(!open)} aria-expanded={open}>{String(node.label)}</button>{open && node.explanation && <p className="note-detail">{String(node.explanation)}</p>}{Array.isArray(node.children) && <ul>{node.children.map((child: any) => <Fragment key={String(child.id)}>{tree(child)}</Fragment>)}</ul>}</li>
    return <ul className="note-tree">{tree(c.root)}</ul>
  }
  if (c.kind === "key_definition") return <dl className="note-definition"><dt>{c.term}</dt><dd>{c.definition}</dd></dl>
  if (c.kind === "comparison") return <div className="note-table"><table><thead><tr><th>Concept</th>{(c.dimensions ?? []).map((d: string) => <th key={d}>{d}</th>)}</tr></thead><tbody>{(c.items ?? []).map((item: any) => <tr key={String(item.id ?? item.name)}><th>{String(item.name)}</th>{(c.dimensions ?? []).map((d: string) => <td key={d}>{String(item.values?.[d] ?? "—")}</td>)}</tr>)}</tbody></table></div>
  if (c.kind === "worked_example" || c.kind === "equation") return <div className="note-example">{c.equation && <code>{c.equation}</code>}{c.problem && <p>{c.problem}</p>}<ol>{(c.steps ?? []).map((step: any, i: number) => <li key={String(step.order ?? i)}>{String(step.description ?? step.label ?? step)}</li>)}</ol>{c.result && <p><strong>Result:</strong> {c.result}</p>}{c.interpretation && <p><strong>Meaning:</strong> {c.interpretation}</p>}</div>
  return <p>{c.text || c.takeaway || c.definition}</p>
}

function NoteView({ notes }: { notes: SectionNote[] }) {
  return <div className="notes-output">{notes.map((note) => <article className="note-section" key={note.id}><p className="note-kicker">Section</p><h2>{note.title}</h2><p className="note-big-idea">{note.bigIdea}</p>{note.components.map((component) => <section className="note-component" key={`${note.id}-${component.title}`}><h3>{component.title}</h3><ComponentView component={component} /></section>)}{note.keyTakeaways.length > 0 && <section className="note-takeaways"><h3>Remember</h3><ul>{note.keyTakeaways.map((item) => <li key={item}>{item}</li>)}</ul></section>}</article>)}</div>
}

export function Notes() {
  const [file, setFile] = useState<File | null>(null)
  const [state, setState] = useState<State>({ status: "idle" })
  useEffect(() => { const saved = sessionStorage.getItem("lucent-last-note"); if (saved) { try { setState({ status: "complete", result: JSON.parse(saved) as DocumentIngestionResult }) } catch { sessionStorage.removeItem("lucent-last-note") } } }, [])
  async function upload() {
    if (!file) return
    setState({ status: "uploading", filename: file.name })
    try {
      if (file.name.toLowerCase().endsWith(".pdf")) {
        const start = await api.startProgressiveDocument(file)
        setState({ status: "processing", filename: start.filename, sections: start.sections })
        let poll = await api.pollProgressiveDocument(start.job_id)
        while (poll.status === "processing") { setState({ status: "processing", filename: poll.filename, sections: poll.sections }); await new Promise((resolve) => window.setTimeout(resolve, 500)); poll = await api.pollProgressiveDocument(start.job_id) }
        if (!poll.result) throw new Error("Lucent could not finish this document")
        sessionStorage.setItem("lucent-last-note", JSON.stringify(poll.result)); setState({ status: "complete", result: poll.result })
      } else {
        const result = await api.ingestDocument(file); sessionStorage.setItem("lucent-last-note", JSON.stringify(result)); setState({ status: "complete", result })
      }
    } catch (error) { setState({ status: "error", message: error instanceof Error ? error.message : "Upload failed" }) }
  }
  const sections = state.sections ?? []
  const notes = state.result?.section_notes ?? []
  return <div className="page notes-page"><header className="page-header"><h1>Notes</h1><p className="page-subtitle">Turn a document into clear, structured notes.</p></header><section className="notes-import"><label htmlFor="notes-file">Import a PDF, DOCX, or PPTX</label><input id="notes-file" type="file" accept=".pdf,.docx,.pptx" onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] ?? null)} /><button className="btn btn-primary" type="button" disabled={!file || state.status === "uploading" || state.status === "processing"} onClick={upload}>{state.status === "uploading" ? "Uploading…" : state.status === "processing" ? "Building notes…" : "Create notes"}</button>{state.status === "error" && <p className="error" role="alert">{state.message}</p>}</section>{state.status === "idle" && !state.result && <p className="empty">Import a lecture, chapter, or slide deck to begin.</p>}{state.status === "processing" && <section aria-live="polite" className="notes-progress"><h2>{state.filename}</h2>{sections.map((section) => <article className="note-skeleton" key={section.id}><h3>{section.title || "Untitled section"}</h3><p>{section.status === "complete" ? "Ready" : section.status === "failed" ? "We kept the section readable with a fallback." : section.status === "generating" ? "Generating…" : "Waiting…"}</p>{section.status === "complete" && section.section_note && <NoteView notes={[section.section_note]} />}</article>)}</section>}{state.status === "complete" && state.result && <><h2 className="notes-document-title">{state.result.filename}</h2>{notes.length ? <NoteView notes={notes} /> : <p className="empty">No sections were produced for this document.</p>}</>}</div>
}
