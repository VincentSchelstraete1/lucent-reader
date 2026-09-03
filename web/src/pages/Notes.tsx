import { Fragment, useEffect, useRef, useState, type ChangeEvent } from "react"
import { api, type DocumentIngestionResult, type ProgressiveSection, type SectionNote } from "../api/client"
import { StepThroughMechanism } from "../learning/experiences/StepThroughMechanism"
import { gramSchmidtGolden } from "../learning/experiences/goldenExamples"

type State = { status: "idle" | "uploading" | "processing" | "complete" | "error"; filename?: string; sections?: ProgressiveSection[]; result?: DocumentIngestionResult; message?: string }

function ComponentView({ component }: { component: SectionNote["components"][number] }) {
  const c = component as any
  const [selected, setSelected] = useState<number | null>(null)
  if (c.kind === "flow" || c.kind === "relationship_map") {
    const nodes = c.nodes ?? []; const edges = c.edges ?? []
    return <div className="note-flow" aria-label={c.title}><p className="note-hint">Select a step to see why it matters.</p>{nodes.map((node: any, index: number) => <div key={String(node.id)}><button className={`note-node${selected === index ? " selected" : ""}`} type="button" onClick={() => setSelected(selected === index ? null : index)} aria-expanded={selected === index}>{String(node.label)}</button>{selected === index && <p className="note-detail" aria-live="polite">{String(node.explanation ?? c.transitionExplanation ?? c.text ?? c.learningObject?.learningGoal ?? "This step is part of the section's learning sequence.")}</p>}{index < nodes.length - 1 && <div className="note-edge"><span>↓</span><strong>{String(edges[index]?.relation ?? "then")}</strong></div>}</div>)}</div>
  }
  if (c.kind === "structure" && c.root) {
    const tree = (node: any, index = 0): JSX.Element => <li><button className="note-node" type="button" onClick={() => setSelected(selected === index ? null : index)} aria-expanded={selected === index}>{String(node.label)}</button>{selected === index && <p className="note-detail" aria-live="polite">{String(node.explanation ?? c.text ?? "This item is part of the structure shown above.")}</p>}{Array.isArray(node.children) && <ul>{node.children.map((child: any, childIndex: number) => <Fragment key={String(child.id)}>{tree(child, index + childIndex + 1)}</Fragment>)}</ul>}</li>
    return <ul className="note-tree">{tree(c.root)}</ul>
  }
  if (c.kind === "key_definition") return <dl className="note-definition"><dt>{c.term}</dt><dd>{c.definition}</dd></dl>
  if (c.kind === "comparison") return <div className="note-table"><table><thead><tr><th>Concept</th>{(c.dimensions ?? []).map((d: string) => <th key={d}>{d}</th>)}</tr></thead><tbody>{(c.items ?? []).map((item: any) => <tr key={String(item.id ?? item.name)}><th>{String(item.name)}</th>{(c.dimensions ?? []).map((d: string) => <td key={d}>{String(item.values?.[d] ?? "—")}</td>)}</tr>)}</tbody></table></div>
  if (c.kind === "worked_example" || c.kind === "equation") {
    const steps = c.steps ?? []
    const visible = selected === null ? 0 : Math.min(selected + 1, steps.length)
    return <div className="note-example">{c.problem && <p className="note-example-problem">{c.problem}</p>}{c.equation && <code className="note-equation">{c.equation}</code>}{(c.knownValues ?? []).length > 0 && <dl className="note-values">{c.knownValues.map((value: any, i: number) => <Fragment key={i}><dt>{String(value.name ?? value.symbol ?? "Value")}</dt><dd>{String(value.value ?? value.meaning ?? value.description ?? "")}</dd></Fragment>)}</dl>}<ol>{steps.slice(0, visible).map((step: any, i: number) => <li key={String(step.order ?? i)}>{String(step.description ?? step.label ?? step)}</li>)}</ol>{steps.length > 0 && <button className="note-reveal" type="button" onClick={() => setSelected(visible >= steps.length ? null : visible)}>{visible >= steps.length ? "Start again" : visible === 0 ? "Reveal the reasoning" : "Reveal next step"}</button>}{visible >= steps.length && c.result && <p><strong>Result:</strong> {c.result}</p>}{visible >= steps.length && c.interpretation && <p><strong>Meaning:</strong> {c.interpretation}</p>}</div>
  }
  return <p>{c.text || c.takeaway || c.definition}</p>
}

function NoteView({ notes }: { notes: SectionNote[] }) {
  return <div className="notes-output">{notes.map((note) => <article className="note-section" key={note.id}><p className="note-kicker">Section</p><h2>{note.title}</h2><p className="note-big-idea">{note.bigIdea}</p>{note.components.filter((component: any) => !(component.kind === "explanation" && component.text === note.bigIdea)).map((component) => <section className="note-component" key={`${note.id}-${component.title}`}><h3>{component.title}</h3><ComponentView component={component} /></section>)}{note.keyTakeaways.length > 0 && <section className="note-takeaways"><h3>Remember</h3><ul>{note.keyTakeaways.map((item) => <li key={item}>{item}</li>)}</ul></section>}</article>)}</div>
}

export function Notes() {
  const [file, setFile] = useState<File | null>(null)
  const [state, setState] = useState<State>({ status: "idle" })
  const [history, setHistory] = useState<DocumentIngestionResult[]>([])
  const [selectedHistory, setSelectedHistory] = useState(0)
  const runRef = useRef(0)
  useEffect(() => { const saved = sessionStorage.getItem("lucent-note-history"); if (saved) { try { const parsed = JSON.parse(saved) as DocumentIngestionResult[]; if (Array.isArray(parsed)) { setHistory(parsed); setState({ status: "complete", result: parsed[0] }) } } catch { sessionStorage.removeItem("lucent-note-history") } } }, [])
  function saveResult(result: DocumentIngestionResult, run: number) { if (run !== runRef.current) return; setHistory((previous) => { const next = [result, ...previous.filter((item) => item.filename !== result.filename)]; sessionStorage.setItem("lucent-note-history", JSON.stringify(next)); sessionStorage.setItem("lucent-last-note", JSON.stringify(result)); return next }); setSelectedHistory(0); setState({ status: "complete", result }) }
  async function upload() {
    if (!file) return
    const run = ++runRef.current
    setState({ status: "uploading", filename: file.name })
    try {
      if (file.name.toLowerCase().endsWith(".pdf")) {
        const start = await api.startProgressiveDocument(file)
        if (run !== runRef.current) return
        setState({ status: "processing", filename: start.filename, sections: start.sections })
        let poll = await api.pollProgressiveDocument(start.job_id)
        while (poll.status === "processing") { if (run !== runRef.current) return; setState({ status: "processing", filename: poll.filename, sections: poll.sections }); await new Promise((resolve) => window.setTimeout(resolve, 500)); poll = await api.pollProgressiveDocument(start.job_id) }
        if (!poll.result) throw new Error("Lucent could not finish this document")
        saveResult(poll.result, run)
      } else {
        const result = await api.ingestDocument(file); saveResult(result, run)
      }
    } catch (error) { if (run === runRef.current) setState({ status: "error", message: error instanceof Error ? error.message : "Upload failed" }) }
  }
  const sections = state.sections ?? []
  const notes = state.result?.section_notes ?? []
  const availableHistory = history.length ? history : state.result ? [state.result] : []
    return <div className="page notes-page"><header className="page-header"><h1>Notes</h1><p className="page-subtitle">Turn a document into clear, structured notes.</p></header><section className="notes-import"><label htmlFor="notes-file">Import a PDF, DOCX, or PPTX</label><input id="notes-file" type="file" accept=".pdf,.docx,.pptx" onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] ?? null)} /><button className="btn btn-primary" type="button" disabled={!file || state.status === "uploading" || state.status === "processing"} onClick={upload}>{state.status === "uploading" ? "Uploading…" : state.status === "processing" ? "Building notes…" : "Create notes"}</button>{state.status === "error" && <p className="error" role="alert">{state.message}</p>}</section>{state.status === "idle" && !state.result && !history.length && <p className="empty">Import a lecture, chapter, or slide deck to begin.</p>}{availableHistory.length > 0 && state.status !== "processing" && <nav className="notes-history" aria-label="Saved notes"><span>Recent notes</span>{availableHistory.map((item, index) => <button key={item.filename} type="button" className={index === selectedHistory ? "active" : ""} onClick={() => { setSelectedHistory(index); setState({ status: "complete", result: item }) }}>{item.filename}</button>)}</nav>}{state.status === "processing" && <section aria-live="polite" className="notes-progress"><h2>{state.filename}</h2>{sections.map((section) => <article className="note-skeleton" key={section.id}><h3>{section.title || "Untitled section"}</h3><p>{section.status === "complete" ? "Ready" : section.status === "failed" ? "Using a concise fallback while this section finishes." : section.status === "generating" ? "Generating…" : "Waiting…"}</p>{section.section_note && <NoteView notes={[section.section_note]} />}</article>)}</section>}{state.status === "complete" && state.result && <><h2 className="notes-document-title">{state.result.filename}</h2>{notes.length ? <NoteView notes={notes} /> : <p className="empty">No sections were produced for this document.</p>}</>}<section className="golden-experience"><p className="note-kicker">Interactive study prototype</p><h2>Gram–Schmidt: remove overlap to create a perpendicular direction</h2><StepThroughMechanism data={gramSchmidtGolden} /></section></div>
}
