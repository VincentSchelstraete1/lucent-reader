import { Fragment, useEffect, useRef, useState, type ChangeEvent } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { api, type DocumentIngestionResult, type LearnFamiliarity, type LearnGoal, type LearnSession, type ProgressiveSection, type SectionNote } from "../api/client"
import { generatedMechanismToRendererData, StepThroughMechanism } from "../learning/experiences/StepThroughMechanism"
import { StructuredVisual } from "../learning/visuals/StructuredVisual"

type LearningNoteRecord = { filename: string; section_notes: SectionNote[]; document_id?: number | null; note_id?: number | null; source_type?: string; teaching_depth?: DepthMode }
type State = { status: "idle" | "uploading" | "processing" | "complete" | "error"; filename?: string; sections?: ProgressiveSection[]; result?: LearningNoteRecord; message?: string }
type DepthMode = "concise" | "balanced" | "detailed"
type StudyMode = "notes" | "learn" | "flashcards"

function SupportingText({ text, depth = "balanced" }: { text: string; depth?: DepthMode }) {
  const sentences = text.split(/(?<=[.!?])\s+/).filter(Boolean)
  if (text.length < 220 || sentences.length < 2) return <p>{text}</p>
  const lead = sentences[0]
  if (depth === "concise") return <p>{lead}</p>
  return <details className="note-supporting" open={depth === "detailed"}><summary>{lead}</summary><p>{sentences.slice(1).join(" ")}</p></details>
}

function recordFromIngestion(result: DocumentIngestionResult): LearningNoteRecord {
  return { filename: result.filename, section_notes: result.section_notes ?? [], document_id: result.document_id, note_id: result.note_id, source_type: result.source_type, teaching_depth: result.teaching_depth }
}

function recordFromSavedNote(note: { id: number; title: string; document_id: number | null; content: string }): LearningNoteRecord | null {
  try {
    const payload = JSON.parse(note.content) as { filename?: string; sourceType?: string; teachingDepth?: DepthMode; sectionNotes?: SectionNote[] }
    if (!Array.isArray(payload.sectionNotes)) return null
    return { filename: payload.filename || note.title, source_type: payload.sourceType, teaching_depth: payload.teachingDepth, section_notes: payload.sectionNotes, document_id: note.document_id, note_id: note.id }
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

export function NoteView({ notes, depth = "balanced" }: { notes: SectionNote[]; depth?: DepthMode }) {
  return <div className="notes-output">{notes.map((note) => <article className="note-section" id={note.id} key={note.id}><p className="note-kicker">Section</p><h2>{note.title}</h2><p className="note-big-idea">{note.bigIdea}</p>{note.components.filter((component: any) => !(component.kind === "explanation" && component.text === note.bigIdea)).map((component, index) => <section className={`note-component note-component-${component.kind}`} key={`${note.id}-${component.title}-${index}`}><h3>{component.title}</h3><ComponentView component={component} depth={depth} /></section>)}{note.keyTakeaways.length > 0 && <section className="note-takeaways"><h3>Remember</h3><ul>{note.keyTakeaways.slice(0, depth === "concise" ? 2 : note.keyTakeaways.length).map((item) => <li key={item}>{item}</li>)}</ul></section>}</article>)}</div>
}

function LearnView({ note, documentId, onBack }: { note: SectionNote; documentId: number | null | undefined; onBack: () => void }) {
  const [goal, setGoal] = useState<LearnGoal>("understand")
  const [familiarity, setFamiliarity] = useState<LearnFamiliarity>("new")
  const [session, setSession] = useState<LearnSession | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [answer, setAnswer] = useState("")
  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [orderedIds, setOrderedIds] = useState<string[]>([])
  const [structuredAnswers, setStructuredAnswers] = useState<Record<string, string>>({})
  const [hint, setHint] = useState<string | null>(null)
  const [focusMode, setFocusMode] = useState(false)
  const sessionRef = useRef<LearnSession | null>(null)

  useEffect(() => {
    if (!focusMode) return
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setFocusMode(false) }
    document.addEventListener("keydown", onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => { document.removeEventListener("keydown", onKeyDown); document.body.style.overflow = previousOverflow }
  }, [focusMode])

  useEffect(() => {
    if (!documentId) return
    let cancelled = false
    api.getActiveLearnSession(documentId).then((active) => { if (!cancelled && active && !sessionRef.current) { sessionRef.current = active; setSession(active) } }).catch(() => undefined)
    return () => { cancelled = true }
  }, [documentId])

  async function start() {
    if (!documentId) return
    setLoading(true); setError(null)
    try { const created = await api.createLearnSession(documentId, { goal, familiarity }); sessionRef.current = created; setSession(created); setAnswer(""); setSelectedOption(null); setOrderedIds(created.step?.items?.map((item) => item.id) ?? []); setStructuredAnswers({}); setHint(null) }
    catch (e) { setError(e instanceof Error ? e.message : "Lucent could not start this learning session.") }
    finally { setLoading(false) }
  }
  async function respond(response?: string, optionId?: string) {
    if (!session) return
    setLoading(true); setError(null)
    try { const updated = await api.submitLearnResponse(session.id, { response, optionId, orderedIds: orderedIds.length ? orderedIds : undefined }); sessionRef.current = updated; setSession(updated); setAnswer(""); setSelectedOption(null); setOrderedIds(updated.step?.items?.map((item) => item.id) ?? []); setStructuredAnswers({}); setHint(null) }
    catch (e) { setError(e instanceof Error ? e.message : "Your response could not be saved.") }
    finally { setLoading(false) }
  }
  async function stop() {
    if (!session) return
    try { const stopped = await api.stopLearnSession(session.id); sessionRef.current = stopped; setSession(stopped) }
    catch (e) { setError(e instanceof Error ? e.message : "This session could not be saved.") }
  }
  async function requestHint() {
    if (!session) return
    try { const result = await api.getLearnHint(session.id); setHint(result.hint); setSession((current) => current ? { ...current, hintsUsed: result.hintsUsed } : current) }
    catch (e) { setError(e instanceof Error ? e.message : "No hint is available right now.") }
  }

  if (!session) return <section className="learn-workspace learn-onboarding" aria-labelledby="learn-heading">
    <button className="learn-back" type="button" onClick={onBack}>← Back to notes</button>
    <p className="note-kicker">Focused learning</p>
    <h2 id="learn-heading">What do you want to get out of this?</h2>
    <p className="learn-context">{note.title}</p>
    <div className="learn-choice-group"><p className="learn-choice-label">Choose a goal</p><div className="learn-choice-grid">{([['understand', 'Understand the concepts', 'Build intuition and see how ideas connect.'], ['solve', 'Learn to solve problems', 'Practice methods and apply them step by step.'], ['memorize', 'Memorize the content', 'Practice important facts, terms, and formulas.'], ['exam', 'Prepare for an exam', 'Mix understanding, recall, and application.']] as const).map(([value, label, description]) => <button type="button" key={value} className={goal === value ? "learn-choice selected" : "learn-choice"} onClick={() => setGoal(value)}><strong>{label}</strong><span>{description}</span></button>)}</div></div>
    <div className="learn-choice-group"><p className="learn-choice-label">How familiar are you with this already?</p><div className="learn-familiarity-row">{([['new', 'New to this'], ['somewhat_familiar', 'Somewhat familiar'], ['reviewing', 'Mostly reviewing']] as const).map(([value, label]) => <button type="button" key={value} className={familiarity === value ? "learn-familiarity selected" : "learn-familiarity"} onClick={() => setFamiliarity(value)}>{label}</button>)}</div></div>
    {error && <p className="error" role="alert">{error}</p>}
    <button className="btn btn-primary" type="button" disabled={loading || !documentId} onClick={start}>{loading ? "Preparing your session…" : "Start learning"}</button>
  </section>

  if (session.status !== "active" || !session.step) return <section className="learn-workspace learn-complete" aria-labelledby="learn-heading"><button className="learn-back" type="button" onClick={onBack}>← Back to notes</button><p className="note-kicker">{session.status === "stopped" ? "Session paused" : "Session complete"}</p><h2 id="learn-heading">{session.status === "stopped" ? "Your progress is saved." : `You worked through ${session.completedObjectives} objective${session.completedObjectives === 1 ? "" : "s"}.`}</h2>{session.report && <div className="learn-report"><p><strong>Next focus:</strong> {session.report.nextFocus.join(", ") || "Continue with a new concept."}</p>{session.report.demonstrated.length > 0 && <p><strong>Demonstrated:</strong> {session.report.demonstrated.join(", ")}</p>}{session.report.developing.length > 0 && <p><strong>Still developing:</strong> {session.report.developing.join(", ")}</p>}{session.report.struggles.length > 0 && <p><strong>Needs attention:</strong> {session.report.struggles.join(" ")}</p>}{session.report.misconceptions?.length ? <p><strong>Misconceptions:</strong> {session.report.misconceptions.join(" ")}</p> : null}{session.report.notCovered.length > 0 && <p><strong>Not covered yet:</strong> {session.report.notCovered.join(", ")}</p>}</div>}<div className="learn-result-actions"><button className="btn" type="button" onClick={onBack}>Review notes</button>{documentId && <button className="btn btn-primary" type="button" onClick={() => window.location.assign(`/quizzes/generating?document_id=${documentId}`)}>Take the quiz</button>}</div></section>

  const step = session.step
  const visualRef = step.visualRef
  const visualComponent = visualRef && typeof visualRef.componentIndex === "number" ? note.components[visualRef.componentIndex] as any : null
  const requiresResponse = ["multiple_choice", "short_answer", "numeric", "problem", "prediction", "ordering", "matching", "labeling", "fill_blank", "worked_step", "teach_back"].includes(step.type)
  const isStructured = step.type === "matching" || step.type === "labeling"
  const submitResponse = isStructured ? JSON.stringify(structuredAnswers) : answer
  const canSubmit = isStructured ? step.items.length > 0 && step.items.every((item) => Boolean(structuredAnswers[item.id])) : step.type === "ordering" ? orderedIds.length === step.items.length : step.options.length > 0 ? Boolean(selectedOption) : Boolean(submitResponse.trim())
  const learningState: Record<string, string> = { teach: "Watch", walkthrough: "Watch", prediction: "Predict", short_answer: "Explain", teach_back: "Reflect", multiple_choice: "Choose", matching: "Compare", labeling: "Label", ordering: "Order", fill_blank: "Recall", worked_step: "Solve", problem: "Solve", numeric: "Solve" }
  const stateLabel = learningState[step.type] || "Learn"
  const adaptationMessage = session.feedback ? (session.feedbackKind === "correct" ? "Lucent is moving you forward based on that evidence." : session.feedbackKind === "incorrect" ? "This concept is still developing. Lucent is changing the approach." : null) : null
  return <section className={`learn-workspace learn-session ${focusMode ? "learn-focus-mode" : ""}`} aria-labelledby="learn-heading">{focusMode && <div className="learn-focus-backdrop" aria-hidden="true" />}
    <div className="learn-session-top"><button className="learn-back" type="button" onClick={onBack}>← Back to notes</button><span aria-live="polite">Objective {session.objectiveIndex + 1} of {session.objectiveCount}</span><button className="learn-focus-toggle" type="button" onClick={() => setFocusMode((value) => !value)} aria-pressed={focusMode}>{focusMode ? "Exit focus" : "Focus learning"}</button></div>
    <p className="note-kicker">{session.goal === "solve" ? "Problem solving" : session.goal === "memorize" ? "Retrieval practice" : "Focused learning"}</p>
    <h2 id="learn-heading">{session.objectiveTitle ?? note.title}</h2>
    <div className="learn-progress" role="progressbar" aria-valuemin={0} aria-valuemax={session.objectiveCount} aria-valuenow={session.objectiveIndex + 1}><span style={{ width: `${((session.objectiveIndex + 1) / Math.max(1, session.objectiveCount)) * 100}%` }} /></div>
    <article className="learn-step"><div className="learn-action-kicker">{stateLabel}</div><h3>{step.title}</h3>{adaptationMessage && <p className="learn-adaptation" role="status">{adaptationMessage}</p>}{step.content && <p className="learn-step-content">{step.content}</p>}{step.visualSpec && <div className="learn-teaching-visual"><StructuredVisual spec={step.visualSpec} /></div>}{visualComponent?.mechanism && <div className="learn-teaching-visual"><StepThroughMechanism data={generatedMechanismToRendererData(visualComponent.mechanism)} /></div>}{step.prompt && <p className="learn-question">{step.prompt}</p>}{step.options.length > 0 && !isStructured && <div className="learn-options">{step.options.map((option) => <button type="button" key={option.id} className={selectedOption === option.id ? "learn-option selected" : "learn-option"} onClick={() => setSelectedOption(option.id)}>{option.label}</button>)}</div>}{isStructured && <div className="learn-structured-response">{step.items.map((item) => <label key={item.id}>{item.label}<select aria-label={item.label} value={structuredAnswers[item.id] ?? ""} onChange={(event) => setStructuredAnswers((current) => ({ ...current, [item.id]: event.target.value }))}><option value="">Choose a match…</option>{step.options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>)}</div>}{step.items.length > 0 && step.type === "ordering" && <div className="learn-ordering">{orderedIds.map((id, index) => { const item = step.items.find((candidate) => candidate.id === id); return <div className="learn-ordering-item" key={id}><span>{index + 1}. {item?.label ?? id}</span><button type="button" disabled={index === 0} onClick={() => setOrderedIds((ids) => { const next = [...ids]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next })} aria-label="Move up">↑</button><button type="button" disabled={index === orderedIds.length - 1} onClick={() => setOrderedIds((ids) => { const next = [...ids]; [next[index], next[index + 1]] = [next[index + 1], next[index]]; return next })} aria-label="Move down">↓</button></div>})}</div>}{requiresResponse && !isStructured && step.options.length === 0 && step.items.length === 0 && <input className="learn-answer" aria-label="Your answer" value={answer} onChange={(event) => setAnswer(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && answer.trim()) respond(submitResponse) }} placeholder="Type your response" />}{hint && <p className="learn-hint" role="status"><strong>Hint {session.hintsUsed}:</strong> {hint}</p>}{session.feedback && <p className={`learn-feedback ${session.feedbackKind ?? "info"}`} role="status">{session.feedback}</p>}<div className="learn-step-actions">{step.hintsAvailable > 0 && <button className="btn" type="button" onClick={requestHint}>Hint</button>}<button className="btn" type="button" onClick={stop}>Stop for now</button>{requiresResponse ? <button className="btn btn-primary" type="button" disabled={loading || !canSubmit} onClick={() => respond(submitResponse, selectedOption ?? undefined)}>{loading ? "Checking…" : "Submit"}</button> : <button className="btn btn-primary" type="button" disabled={loading} onClick={() => respond()}>{loading ? "Saving…" : "Continue"}</button>}</div></article>
    {error && <p className="error" role="alert">{error}</p>}
  </section>
}

function FlashcardsView({ notes, onBack }: { notes: SectionNote[]; onBack: () => void }) {
  const cards = notes.flatMap((note) => {
    const definitions = note.components.filter((component: any) => component.kind === "key_definition" && component.term && component.definition).map((component: any) => ({ prompt: `What is ${component.term}?`, answer: component.definition, section: note.title }))
    const takeaways = note.keyTakeaways.slice(0, 2).map((takeaway) => ({ prompt: `What should you remember about ${note.title}?`, answer: takeaway, section: note.title }))
    return [...definitions, ...takeaways]
  }).slice(0, 24)
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const card = cards[index]
  if (!card) return <section className="learn-workspace"><button className="learn-back" type="button" onClick={onBack}>← Back to notes</button><p className="learn-empty">This note has no definition or takeaway cards yet.</p></section>
  return <section className="learn-workspace flashcards-workspace" aria-labelledby="flashcards-heading"><button className="learn-back" type="button" onClick={onBack}>← Back to notes</button><p className="note-kicker">Recall practice</p><h2 id="flashcards-heading">Flashcards</h2><p className="learn-context">{index + 1} of {cards.length} · {card.section}</p><article className="flashcard" aria-live="polite"><p>{card.prompt}</p>{revealed && <div className="flashcard-answer"><span>Answer</span><strong>{card.answer}</strong></div>}</article><div className="step-controls"><button type="button" onClick={() => setRevealed(true)} disabled={revealed}>Reveal answer</button><button type="button" onClick={() => { setIndex((value) => (value + 1) % cards.length); setRevealed(false) }} disabled={!revealed}>Next card</button></div></section>
}

function estimateMinutes(notes: SectionNote[], depth: DepthMode): number {
  const chars = notes.reduce((sum, note) => sum + note.bigIdea.length + note.components.reduce((n, component: any) => n + String(component.text ?? component.definition ?? component.interpretation ?? "").length, 0), 0)
  const visualWeight = notes.reduce((sum, note) => sum + note.components.filter((component: any) => ["flow", "structure", "relationship_map", "worked_example", "equation"].includes(component.kind)).length, 0)
  const multiplier = depth === "detailed" ? 1.35 : depth === "concise" ? 0.7 : 1
  return Math.max(1, Math.round(((chars / 900) + visualWeight * 0.45) * multiplier))
}

export function Notes() {
  const navigate = useNavigate()
  const { documentId: routeDocumentId } = useParams()
  const [searchParams] = useSearchParams()
  const mode: StudyMode = searchParams.get("mode") === "learn" ? "learn" : searchParams.get("mode") === "flashcards" ? "flashcards" : "notes"
  const requestedSection = searchParams.get("section")
  const [file, setFile] = useState<File | null>(null)
  const [state, setState] = useState<State>({ status: "idle" })
  const [history, setHistory] = useState<LearningNoteRecord[]>([])
  const [materialTitle, setMaterialTitle] = useState<string | null>(null)
  const [selectedHistory, setSelectedHistory] = useState(0)
  const [quizStatus, setQuizStatus] = useState<"idle" | "working" | "error">("idle")
  const [depth, setDepth] = useState<DepthMode>("balanced")
  const runRef = useRef(0)
  useEffect(() => {
    let cancelled = false
    const requestedDocument = Number(searchParams.get("document_id") ?? routeDocumentId)
    if (Number.isFinite(requestedDocument) && requestedDocument > 0) {
      api.getDocument(requestedDocument).then((document) => { if (!cancelled) setMaterialTitle(document.title.replace(/\.(pdf|docx|pptx)$/i, "") || "Untitled material") }).catch(() => { if (!cancelled) setMaterialTitle(null) })
    }
    api.getNotes().then((notes) => {
      if (cancelled) return
      const persisted = notes.filter((note) => note.content_type === "section_note").map(recordFromSavedNote).filter((item): item is LearningNoteRecord => item !== null).reverse()
      const selected = Number.isFinite(requestedDocument) && requestedDocument > 0 ? persisted.find((item) => item.document_id === requestedDocument) : persisted[0]
      if (selected) { setHistory(persisted); setSelectedHistory(Math.max(0, persisted.indexOf(selected))); setDepth(selected.teaching_depth ?? "balanced"); setState({ status: "complete", result: selected }) }
      else if (Number.isFinite(requestedDocument) && requestedDocument > 0) { setHistory([]); setState({ status: "idle", filename: materialTitle ?? undefined }) }
      else { setHistory([]); setState({ status: "idle" }) }
      window.setTimeout(() => { if (window.location.hash) document.querySelector(window.location.hash)?.scrollIntoView({ behavior: "smooth", block: "start" }) }, 0)
    }).catch(() => {
      const saved = sessionStorage.getItem("lucent-note-history")
      if (saved) { try { const parsed = JSON.parse(saved) as LearningNoteRecord[]; if (Array.isArray(parsed) && parsed.length) { setHistory(parsed); setState({ status: "complete", result: parsed[0] }) } } catch { sessionStorage.removeItem("lucent-note-history") } }
    })
    return () => { cancelled = true }
  }, [routeDocumentId, searchParams])
  function saveResult(result: DocumentIngestionResult, run: number) { if (run !== runRef.current) return; const record = recordFromIngestion(result); setDepth(record.teaching_depth ?? depth); setHistory((previous) => { const next = [record, ...previous.filter((item) => item.document_id ? item.document_id !== record.document_id : item.filename !== record.filename)]; sessionStorage.setItem("lucent-note-history", JSON.stringify(next)); return next }); setSelectedHistory(0); setState({ status: "complete", result: record }); if (record.document_id) navigate(`/app/material/${record.document_id}?mode=notes`) }

  async function startQuiz() {
    const documentId = state.result?.document_id
    if (!documentId) { setQuizStatus("error"); return }
    navigate(`/quizzes/generating?document_id=${documentId}`)
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
  const activeNote = notes.find((note) => note.id === requestedSection) ?? notes[0]
  const setMode = (nextMode: StudyMode, sectionId?: string) => {
    const params = new URLSearchParams(searchParams)
    params.set("mode", nextMode)
    if (sectionId) params.set("section", sectionId)
    navigate(`${routeDocumentId ? `/app/material/${routeDocumentId}` : "/app/notes"}?${params.toString()}`)
  }
  return <div className="page notes-page">
    <header className="page-header"><p className="note-kicker">{routeDocumentId ? <Link to="/app">← Back to library</Link> : "Study library"}</p><h1>{routeDocumentId && materialTitle ? materialTitle : "Notes"}</h1><p className="page-subtitle">{routeDocumentId ? "Turn this material into a focused study guide." : "Turn a lecture, chapter, or slide deck into a focused study guide."}</p></header>
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
    {state.status === "complete" && state.result && <><header className="notes-document-heading"><div><p className="note-kicker">Study note</p><h2 className="notes-document-title">{state.result.filename}</h2><p>{notes.length} focused section{notes.length === 1 ? "" : "s"} · about {estimatedMinutes} min · {mode === "learn" ? "focused learning" : mode === "flashcards" ? "recall practice" : "ready to review"}</p></div><div className="notes-actions"><div className="study-mode-tabs" role="tablist" aria-label="Study mode"><button type="button" role="tab" aria-selected={mode === "notes"} className={mode === "notes" ? "active" : ""} onClick={() => setMode("notes")}>Notes</button><button type="button" role="tab" aria-selected={mode === "learn"} className={mode === "learn" ? "active" : ""} onClick={() => setMode("learn", activeNote?.id)}>Learn</button><button type="button" role="tab" aria-selected={mode === "flashcards"} className={mode === "flashcards" ? "active" : ""} onClick={() => setMode("flashcards")}>Flashcards</button><button type="button" role="tab" aria-selected={false} onClick={startQuiz}>Quiz</button></div><label htmlFor="notes-depth">Learning depth</label><select id="notes-depth" value={depth} onChange={(event) => setDepth(event.target.value as DepthMode)}><option value="concise">Concise Study Guide</option><option value="balanced">Balanced</option><option value="detailed">Detailed Explanation</option></select><button className="btn btn-primary" type="button" disabled={quizStatus === "working" || !state.result.document_id} onClick={startQuiz}>{quizStatus === "working" ? "Building quiz…" : "Check your understanding"}</button></div></header>{quizStatus === "error" && <p className="error" role="alert">This note is available to study, but Lucent could not start its quiz.</p>}{mode === "learn" && activeNote ? <LearnView note={activeNote} documentId={state.result.document_id} onBack={() => setMode("notes", activeNote.id)} /> : mode === "flashcards" ? <FlashcardsView notes={notes} onBack={() => setMode("notes")} /> : <><nav className="section-index" aria-label="Note sections"><span>Sections</span>{notes.map((note, index) => { const hasWalkthrough = note.components.some((component: any) => component.kind === "walkthrough" && component.mechanism); return <span className="section-index-item" key={note.id}><a className={note.id === activeNote?.id ? "active" : ""} href={`#${note.id}`}>{index + 1}. {note.title}</a>{hasWalkthrough && <button type="button" onClick={() => setMode("learn", note.id)} aria-label={`Learn ${note.title}`}>Learn</button>}</span>})}</nav>{notes.length ? <NoteView notes={notes} depth={depth} /> : <p className="empty">No sections were produced for this document.</p>}</>}</>}
  </div>
}
