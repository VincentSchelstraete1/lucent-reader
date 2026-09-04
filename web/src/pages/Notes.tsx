import { Fragment, useEffect, useRef, useState, type ChangeEvent } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { api, type DocumentIngestionResult, type ProgressiveSection, type SectionNote, type RawImage } from "../api/client"
import { generatedMechanismToRendererData, StepThroughMechanism } from "../learning/experiences/StepThroughMechanism"

type PersistedImage = Pick<RawImage, "id" | "asset_reference" | "caption" | "mime_type" | "page_number"> & { source_image_ids?: string[] }
type LearningNoteRecord = { filename: string; section_notes: SectionNote[]; document_id?: number | null; note_id?: number | null; source_type?: string; teaching_depth?: DepthMode; images?: PersistedImage[]; learning_blocks?: Array<{ id: string; attachedImageIds: string[] }> }
type State = { status: "idle" | "uploading" | "processing" | "complete" | "error"; filename?: string; sections?: ProgressiveSection[]; result?: LearningNoteRecord; message?: string }
type DepthMode = "concise" | "balanced" | "detailed"

function SupportingText({ text, depth = "balanced" }: { text: string; depth?: DepthMode }) {
  const sentences = text.split(/(?<=[.!?])\s+/).filter(Boolean)
  if (text.length < 220 || sentences.length < 2) return <p>{text}</p>
  const lead = sentences[0]
  if (depth === "concise") return <p>{lead}</p>
  return <details className="note-supporting" open={depth === "detailed"}><summary>{lead}</summary><p>{sentences.slice(1).join(" ")}</p></details>
}

function recordFromIngestion(result: DocumentIngestionResult): LearningNoteRecord {
  return { filename: result.filename, section_notes: result.section_notes ?? [], document_id: result.document_id, note_id: result.note_id, source_type: result.source_type, teaching_depth: result.teaching_depth, images: result.images, learning_blocks: result.learning_blocks.map((block) => ({ id: block.id, attachedImageIds: block.attached_image_ids })) }
}

function recordFromSavedNote(note: { id: number; title: string; document_id: number | null; content: string }): LearningNoteRecord | null {
  try {
    const payload = JSON.parse(note.content) as { filename?: string; sourceType?: string; teachingDepth?: DepthMode; sectionNotes?: SectionNote[]; images?: PersistedImage[]; learningBlocks?: Array<{ id: string; attachedImageIds?: string[] }> }
    if (!Array.isArray(payload.sectionNotes)) return null
    return { filename: payload.filename || note.title, source_type: payload.sourceType, teaching_depth: payload.teachingDepth, section_notes: payload.sectionNotes, document_id: note.document_id, note_id: note.id, images: payload.images ?? [], learning_blocks: (payload.learningBlocks ?? []).map((block) => ({ id: block.id, attachedImageIds: block.attachedImageIds ?? [] })) }
  } catch { return null }
}

function ComponentView({ component, depth = "balanced" }: { component: SectionNote["components"][number]; depth?: DepthMode }) {
  const c = component as any
  const [selected, setSelected] = useState<number | string | null>(null)
  if (c.kind === "relationship_map") {
    const nodes = new Map((c.nodes ?? []).map((node: any) => [String(node.id), node]))
      return <div className="note-relationships" aria-label={c.title}>{(c.edges ?? []).map((edge: any, index: number) => {
      const source = nodes.get(String(edge.source)) as any
      const target = nodes.get(String(edge.target)) as any
      const detail = edge.explanation ?? source?.explanation ?? target?.explanation
      return <div className="note-relationship" key={`${edge.source}-${edge.target}-${index}`}><button type="button" onClick={() => setSelected(selected === index ? null : index)} aria-expanded={selected === index}><span>{String(source?.label ?? edge.source)}</span><span className="note-relationship-arrow"><strong>{String(edge.relation)}</strong><i aria-hidden="true">→</i></span><span>{String(target?.label ?? edge.target)}</span></button>{selected === index && detail && <p className="note-detail" aria-live="polite">{String(detail)}</p>}</div>
    })}{c.whyItMatters && <p className="note-why"><strong>Why this matters</strong>{String(c.whyItMatters)}</p>}</div>
  }
  if (c.kind === "flow") {
    const nodeMap = new Map<string, any>((c.nodes ?? []).map((node: any) => [String(node.id), node]))
    const edges = c.edges ?? []
    const targets = new Set(edges.map((edge: any) => String(edge.target)))
    const roots = [...nodeMap.keys()].filter((id) => !targets.has(id))
    const renderNode = (nodeId: string, path: Set<string>): JSX.Element | null => {
      const node = nodeMap.get(nodeId)
      if (!node || path.has(nodeId)) return null
      const children = edges.filter((edge: any) => String(edge.source) === nodeId)
      const nextPath = new Set(path).add(nodeId)
      const nodeDetail = typeof node.explanation === "string" && node.explanation.trim() ? node.explanation : null
      const nodeView = nodeDetail ? <button className={`note-node${selected === nodeId ? " selected" : ""}`} type="button" onClick={() => setSelected(selected === nodeId ? null : nodeId)} aria-expanded={selected === nodeId}>{String(node.label)}</button> : <span className="note-node note-node-static">{String(node.label)}</span>
      return <div className="flow-branch" key={`${[...path].join("-")}-${nodeId}`}>{nodeView}{selected === nodeId && nodeDetail && <p className="note-detail" aria-live="polite">{String(nodeDetail)}</p>}{children.length > 0 && <div className={`flow-children${children.length > 1 ? " flow-split" : ""}`}>{children.map((edge: any, index: number) => <div className="flow-child" key={`${nodeId}-${edge.target}-${index}`}><div className="note-edge"><span aria-hidden="true">↓</span><strong>{String(edge.relation)}</strong></div>{renderNode(String(edge.target), nextPath)}</div>)}</div>}</div>
    }
    return <div className="note-flow" aria-label={c.title}><p className="note-hint">Select a step for its role in the mechanism.</p>{(roots.length ? roots : [...nodeMap.keys()].slice(0, 1)).map((root) => renderNode(root, new Set()))}{c.transitionExplanation && <p className="note-why"><strong>What the path means</strong>{String(c.transitionExplanation)}</p>}</div>
  }
  if (c.kind === "structure" && c.root) {
    const structureLabels = new Map<string, string>()
    const collectLabels = (node: any) => { structureLabels.set(String(node.id), String(node.label)); (node.children ?? []).forEach(collectLabels) }
    collectLabels(c.root)
    const tree = (node: any, index = 0): JSX.Element => <li><button className="note-node" type="button" onClick={() => setSelected(selected === index ? null : index)} aria-expanded={selected === index}>{String(node.label)}{node.multiplicity && <small className="note-node-multiplicity">{String(node.multiplicity)}</small>}</button>{selected === index && <p className="note-detail" aria-live="polite">{String(node.explanation ?? c.text ?? "This item is part of the structure shown above.")}</p>}{Array.isArray(node.children) && <ul>{node.children.map((child: any, childIndex: number) => <Fragment key={String(child.id)}>{tree(child, index + childIndex + 1)}</Fragment>)}</ul>}</li>
    return <><div className={`note-structure note-structure-${c.structureType ?? "hierarchy"}`}><ul className="note-tree">{tree(c.root)}</ul>{c.structureType === "architecture" && Array.isArray(c.connections) && c.connections.length > 0 && <div className="note-structure-connections"><strong>Connections</strong>{c.connections.map((edge: any, index: number) => <button type="button" key={`${edge.source}-${edge.target}-${index}`} onClick={() => setSelected(`connection-${index}`)}><span>{structureLabels.get(String(edge.source)) ?? "Component"}</span><b>{String(edge.relation)}</b><span>{structureLabels.get(String(edge.target)) ?? "Component"}</span>{selected === `connection-${index}` && edge.explanation && <small>{String(edge.explanation)}</small>}</button>)}</div>}</div>{c.whyItMatters && <p className="note-why"><strong>Why this structure matters</strong>{String(c.whyItMatters)}</p>}</>
  }
  if (c.kind === "key_definition") return <dl className="note-definition"><dt>{c.term}</dt><dd>{c.definition}</dd></dl>
  if (c.kind === "comparison") return <div className="note-table"><table><thead><tr><th>Concept</th>{(c.dimensions ?? []).map((d: string) => <th key={d}>{d}</th>)}</tr></thead><tbody>{(c.items ?? []).map((item: any) => <tr key={String(item.id ?? item.name)}><th>{String(item.name)}</th>{(c.dimensions ?? []).map((d: string) => <td key={d}>{String(item.values?.[d] ?? "—")}</td>)}</tr>)}</tbody></table></div>
  if (c.kind === "equation") {
    const variables = c.variables ?? []
    const knownValues = c.knownValues ?? []
    return <div className="note-equation-breakdown"><code className="note-equation">{c.equation}</code>{variables.length > 0 && <dl className="note-values">{variables.map((value: any, i: number) => <Fragment key={i}><dt>{String(value.symbol ?? value.name ?? "Term")}</dt><dd>{String(value.meaning ?? value.description ?? value.value ?? "")}</dd></Fragment>)}</dl>}{knownValues.length > 0 && <div className="equation-known"><span>Given</span>{knownValues.map((value: any, index: number) => <code key={index}>{String(value.symbol ?? value.name ?? "value")} = {String(value.value ?? value.meaning ?? "")}</code>)}</div>}{c.substitution && <div className="equation-step"><span>Substitute</span><code>{c.substitution}</code></div>}{c.result && <div className="equation-step equation-result"><span>Result</span><code>{c.result}</code></div>}{c.interpretation && <p className="note-why"><strong>Interpretation</strong>{c.interpretation}</p>}</div>
  }
  if (c.kind === "worked_example") {
    const steps = c.steps ?? []
    const visible = typeof selected === "number" ? Math.min(selected + 1, steps.length) : 0
    return <div className="note-example">{c.problem && <p className="note-example-problem">{c.problem}</p>}{c.equation && <code className="note-equation">{c.equation}</code>}{(c.knownValues ?? []).length > 0 && <dl className="note-values">{c.knownValues.map((value: any, i: number) => <Fragment key={i}><dt>{String(value.name ?? value.symbol ?? "Value")}</dt><dd>{String(value.value ?? value.meaning ?? value.description ?? "")}</dd></Fragment>)}</dl>}<ol>{steps.slice(0, visible).map((step: any, i: number) => <li key={String(step.order ?? i)}>{String(step.description ?? step.label ?? step)}</li>)}</ol>{steps.length > 0 && <button className="note-reveal" type="button" onClick={() => setSelected(visible >= steps.length ? null : visible)}>{visible >= steps.length ? "Start again" : visible === 0 ? "Reveal the reasoning" : "Reveal next step"}</button>}{visible >= steps.length && c.result && <p><strong>Result:</strong> {c.result}</p>}{visible >= steps.length && c.interpretation && <p><strong>Meaning:</strong> {c.interpretation}</p>}</div>
  }
  if (c.kind === "walkthrough" && c.mechanism) {
    const mechanism = c.mechanism
    const [started, setStarted] = useState(false)
    return <div className="note-walkthrough">
      <p className="note-walkthrough-goal">{String(c.learningGoal ?? mechanism.learningGoal)}</p>
      <p className="note-walkthrough-bottleneck"><strong>Focus:</strong> {String(c.bottleneck)}</p>
      {c.estimatedMinutes && <p className="note-walkthrough-time">About {String(c.estimatedMinutes)} min</p>}
      {!started ? <button className="note-walkthrough-start" type="button" onClick={() => setStarted(true)}>Start walkthrough →</button> : <StepThroughMechanism data={generatedMechanismToRendererData(mechanism)} />}
    </div>
  }
  if (c.kind === "callout") return <aside className={`note-callout note-callout-${c.calloutType ?? "important"}`}><p>{c.text}</p>{c.whyItMatters && <small>{c.whyItMatters}</small>}</aside>
  return <SupportingText text={String(c.text || c.takeaway || c.definition || "")} depth={depth} />
}

export function NoteView({ notes, depth = "balanced", images = [], learningBlocks = [] }: { notes: SectionNote[]; depth?: DepthMode; images?: PersistedImage[]; learningBlocks?: Array<{ id: string; attachedImageIds: string[] }> }) {
  const blockImages = new Map(learningBlocks.map((block) => [block.id, block.attachedImageIds]))
  const imageMap = new Map(images.map((image) => [image.id, image]))
  return <div className="notes-output">{notes.map((note) => {
    const imageIds = [...new Set(note.sourceBlockIds.flatMap((blockId) => blockImages.get(blockId) ?? []))]
    const sectionImages = imageIds.map((id) => imageMap.get(id)).filter((image): image is PersistedImage => Boolean(image && image.asset_reference))
    return <article className="note-section" id={note.id} key={note.id}><p className="note-kicker">Section</p><h2>{note.title}</h2><p className="note-big-idea">{note.bigIdea}</p>{sectionImages.length > 0 && <div className="note-source-figures" aria-label="Source figures">{sectionImages.map((image) => <figure key={image.id}><img src={image.asset_reference} alt={image.caption || "Instructional figure from source"} />{image.caption && <figcaption>{image.caption}</figcaption>}</figure>)}</div>}{note.components.filter((component: any) => !(component.kind === "explanation" && component.text === note.bigIdea)).map((component, index) => <section className={`note-component note-component-${component.kind}`} key={`${note.id}-${component.title}-${index}`}><h3>{component.title}</h3><ComponentView component={component} depth={depth} /></section>)}{note.keyTakeaways.length > 0 && <section className="note-takeaways"><h3>Remember</h3><ul>{note.keyTakeaways.slice(0, depth === "concise" ? 2 : note.keyTakeaways.length).map((item) => <li key={item}>{item}</li>)}</ul></section>}</article>
  })}</div>
}

function estimateMinutes(notes: SectionNote[], depth: DepthMode): number {
  const chars = notes.reduce((sum, note) => sum + note.bigIdea.length + note.components.reduce((n, component: any) => n + String(component.text ?? component.definition ?? component.interpretation ?? "").length, 0), 0)
  const visualWeight = notes.reduce((sum, note) => sum + note.components.filter((component: any) => ["flow", "structure", "relationship_map", "worked_example", "equation"].includes(component.kind)).length, 0)
  const multiplier = depth === "detailed" ? 1.35 : depth === "concise" ? 0.7 : 1
  return Math.max(1, Math.round(((chars / 900) + visualWeight * 0.45) * multiplier))
}

export function Notes() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [file, setFile] = useState<File | null>(null)
  const [state, setState] = useState<State>({ status: "idle" })
  const [history, setHistory] = useState<LearningNoteRecord[]>([])
  const [selectedHistory, setSelectedHistory] = useState(0)
  const [quizStatus, setQuizStatus] = useState<"idle" | "working" | "error">("idle")
  const [depth, setDepth] = useState<DepthMode>("balanced")
  const runRef = useRef(0)
  useEffect(() => {
    let cancelled = false
    api.getNotes().then((notes) => {
      if (cancelled) return
      const persisted = notes.filter((note) => note.content_type === "section_note").map(recordFromSavedNote).filter((item): item is LearningNoteRecord => item !== null).reverse()
      const requestedDocument = Number(searchParams.get("document_id"))
      const selected = persisted.find((item) => item.document_id === requestedDocument) ?? persisted[0]
      if (persisted.length) { setHistory(persisted); setSelectedHistory(Math.max(0, persisted.indexOf(selected))); setDepth(selected.teaching_depth ?? "balanced"); setState({ status: "complete", result: selected }) }
      else { setHistory([]); setState({ status: "idle" }) }
      window.setTimeout(() => { if (window.location.hash) document.querySelector(window.location.hash)?.scrollIntoView({ behavior: "smooth", block: "start" }) }, 0)
    }).catch(() => {
      const saved = sessionStorage.getItem("lucent-note-history")
      if (saved) { try { const parsed = JSON.parse(saved) as LearningNoteRecord[]; if (Array.isArray(parsed) && parsed.length) { setHistory(parsed); setState({ status: "complete", result: parsed[0] }) } } catch { sessionStorage.removeItem("lucent-note-history") } }
    })
    return () => { cancelled = true }
  }, [searchParams])
  function saveResult(result: DocumentIngestionResult, run: number) { if (run !== runRef.current) return; const record = recordFromIngestion(result); setDepth(record.teaching_depth ?? depth); setHistory((previous) => { const next = [record, ...previous.filter((item) => item.document_id ? item.document_id !== record.document_id : item.filename !== record.filename)]; sessionStorage.setItem("lucent-note-history", JSON.stringify(next)); return next }); setSelectedHistory(0); setState({ status: "complete", result: record }) }

  async function startQuiz() {
    const documentId = state.result?.document_id
    if (!documentId) { setQuizStatus("error"); return }
    setQuizStatus("working")
    try { const quiz = await api.generateQuiz(documentId); navigate(`/quizzes/${quiz.id}`) }
    catch { setQuizStatus("error") }
  }
  async function upload() {
    if (!file) return
    const run = ++runRef.current
    setState({ status: "uploading", filename: file.name })
    try {
      if (file.name.toLowerCase().endsWith(".pdf")) {
        const start = await api.startProgressiveDocument(file, depth)
        if (run !== runRef.current) return
        setState({ status: "processing", filename: start.filename, sections: start.sections })
        let poll = await api.pollProgressiveDocument(start.job_id)
        while (poll.status === "processing") { if (run !== runRef.current) return; setState({ status: "processing", filename: poll.filename, sections: poll.sections }); await new Promise((resolve) => window.setTimeout(resolve, 500)); poll = await api.pollProgressiveDocument(start.job_id) }
        if (!poll.result) throw new Error("Lucent could not finish this document")
        saveResult(poll.result, run)
      } else {
        const result = await api.ingestDocument(file, depth); saveResult(result, run)
      }
    } catch (error) { if (run === runRef.current) setState({ status: "error", message: error instanceof Error ? error.message : "Upload failed" }) }
  }
  const sections = state.sections ?? []
  const notes = state.result?.section_notes ?? []
  const estimatedMinutes = estimateMinutes(notes, depth)
  const availableHistory = history.length ? history : state.result ? [state.result] : []
  return <div className="page notes-page">
    <header className="page-header"><p className="note-kicker">Study library</p><h1>Notes</h1><p className="page-subtitle">Turn a lecture, chapter, or slide deck into a focused study guide.</p></header>
    <section className="notes-import">
      <label htmlFor="notes-file">Import learning material</label>
      <p>PDF, DOCX, or PPTX · Lucent keeps sections in source order and shows each one as it finishes.</p>
      <input id="notes-file" type="file" accept=".pdf,.docx,.pptx" onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] ?? null)} />
      <label htmlFor="notes-generation-depth">Teaching depth</label>
      <select id="notes-generation-depth" value={depth} onChange={(event) => setDepth(event.target.value as DepthMode)}>
        <option value="concise">Concise Study Guide</option><option value="balanced">Balanced</option><option value="detailed">Detailed Explanation</option>
      </select>
      <button className="btn btn-primary" type="button" disabled={!file || state.status === "uploading" || state.status === "processing"} onClick={upload}>{state.status === "uploading" ? "Uploading…" : state.status === "processing" ? "Building notes…" : "Create notes"}</button>
      {state.status === "error" && <p className="error" role="alert">{state.message}</p>}
    </section>
    {state.status === "idle" && !state.result && !history.length && <p className="empty">Import a lecture, chapter, or slide deck to begin.</p>}
    {availableHistory.length > 0 && state.status !== "processing" && <nav className="notes-history" aria-label="Saved notes"><span>Saved notes</span>{availableHistory.map((item, index) => <button key={`${item.document_id ?? item.filename}-${index}`} type="button" className={index === selectedHistory ? "active" : ""} onClick={() => { setSelectedHistory(index); setQuizStatus("idle"); setState({ status: "complete", result: item }) }}>{item.filename}</button>)}</nav>}
    {state.status === "processing" && <section aria-live="polite" className="notes-progress"><h2>{state.filename}</h2><p className="notes-progress-summary">Your study guide is taking shape. Completed sections are ready to read now.</p>{sections.map((section) => <article className={`note-skeleton status-${section.status}`} key={section.id}><div className="section-status"><span>{section.status === "complete" ? "Ready" : section.status === "failed" ? "Source-based fallback" : section.status === "generating" ? "Writing…" : "Waiting"}</span></div><h3>{section.title || "Untitled section"}</h3>{section.section_note && <NoteView notes={[section.section_note]} />}</article>)}</section>}
    {state.status === "complete" && state.result && <><header className="notes-document-heading"><div><p className="note-kicker">Study note</p><h2 className="notes-document-title">{state.result.filename}</h2><p>{notes.length} focused section{notes.length === 1 ? "" : "s"} · about {estimatedMinutes} min</p></div><div className="notes-actions"><label htmlFor="notes-depth">Learning depth</label><select id="notes-depth" value={depth} onChange={(event) => setDepth(event.target.value as DepthMode)}><option value="concise">Concise Study Guide</option><option value="balanced">Balanced</option><option value="detailed">Detailed Explanation</option></select><button className="btn btn-primary" type="button" disabled={quizStatus === "working" || !state.result.document_id} onClick={startQuiz}>{quizStatus === "working" ? "Building quiz…" : "Check your understanding"}</button></div></header>{quizStatus === "error" && <p className="error" role="alert">This note is available to study, but Lucent could not start its quiz.</p>}{notes.length ? <NoteView notes={notes} depth={depth} images={state.result.images} learningBlocks={state.result.learning_blocks} /> : <p className="empty">No sections were produced for this document.</p>}</>}
  </div>
}
