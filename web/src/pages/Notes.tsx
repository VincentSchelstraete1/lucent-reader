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
  return { filename: result.filename, section_notes: usableSections(result.section_notes ?? []), document_id: result.document_id, note_id: result.note_id, source_type: result.source_type, teaching_depth: result.teaching_depth }
}

// Extraction diagnostics are operational metadata, never learner-facing note
// sections. Keep this boundary in the client as defense in depth for older
// persisted notes that predate backend source filtering.
function usableSections(sections: SectionNote[]): SectionNote[] {
  const diagnostic = /insufficient source|unable to design|extraction error|no substantive content|bibliographic references alone|source material unavailable/i
  return sections.filter((section) => !diagnostic.test(`${section.title} ${section.bigIdea}`))
}

function recordFromSavedNote(note: { id: number; title: string; document_id: number | null; content: string }): LearningNoteRecord | null {
  try {
    const payload = JSON.parse(note.content) as { filename?: string; sourceType?: string; teachingDepth?: DepthMode; sectionNotes?: SectionNote[] }
    if (!Array.isArray(payload.sectionNotes)) return null
    return { filename: payload.filename || note.title, source_type: payload.sourceType, teaching_depth: payload.teachingDepth, section_notes: usableSections(payload.sectionNotes), document_id: note.document_id, note_id: note.id }
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

function LearningSceneView({ session, note, onVisualStageChange }: { session: LearnSession; note: SectionNote; onVisualStageChange?: (stage: number) => void }) {
  const rawBlocks = (session.scene?.blocks ?? []).filter((block) => block.kind !== "practice")
  // Keep the teaching surface focused: repeated tutor status cards are
  // orchestration history, not separate lessons. Preserve the latest natural
  // intervention alongside explanation/visual/feedback blocks.
  const latestTutorId = [...rawBlocks].reverse().find((block) => block.kind === "tutor_message")?.id
  const latestExplanationId = [...rawBlocks].reverse().find((block) => block.kind === "explanation")?.id
  const latestNarrativeByLabel = new Map<string, string>()
  rawBlocks.forEach((block) => {
    if (["tutor_message", "explanation", "analogy"].includes(block.kind)) {
      latestNarrativeByLabel.set(String(block.label || block.kind).trim().toLowerCase(), block.id)
    }
  })
  const latestReframeId = [...rawBlocks].reverse().find((block) =>
    ["tutor_message", "explanation", "analogy"].includes(block.kind) && /another way|reframe|ask lucent/i.test(`${String(block.label ?? "")} ${String(block.title ?? "")}`),
  )?.id
  const blocks = rawBlocks.filter((block) =>
    (block.kind !== "tutor_message" || block.id === latestTutorId) &&
    (block.kind !== "explanation" || block.id === latestExplanationId) &&
    (!["tutor_message", "explanation", "analogy"].includes(block.kind) || latestNarrativeByLabel.get(String(block.label || block.kind).trim().toLowerCase()) === block.id) &&
    (!(["tutor_message", "explanation", "analogy"].includes(block.kind) && /another way|reframe|ask lucent/i.test(`${String(block.label ?? "")} ${String(block.title ?? "")}`)) || block.id === latestReframeId),
  )
  const visualBlocks = blocks.filter((block) => block.kind === "visual" && (block.visualSpec || block.visualRef))
  const primaryVisual = visualBlocks.at(-1)
  let visualRendered = false
  if (!blocks.length) return null
  const fallbackBlocks = blocks
  const learnerTutorText = (content: string) => {
    const lowered = content.toLowerCase()
    if (lowered.includes("related prerequisite") || lowered.includes("saved material does not fully explain")) return "Let's build the supporting idea first, then bring it back to this concept."
    if (lowered.includes("need to know which visual") || lowered.includes("what specifically you're confused")) return "Let's focus on the part of the visual that matters for this idea."
    if (lowered.includes("let me retrieve") || lowered.includes("available sources")) return "Let's use a concrete example from the material."
    // Provider answers occasionally contain Markdown emphasis even though
    // scene blocks render as plain learner-facing text. Strip presentation
    // markers at this boundary so raw `**bold**`/`__bold__` never reaches the
    // learner UI, while preserving the words themselves.
    const narratedVisual = /^(?:I'll|I will) show you (?:a|the) visual/i.test(content)
    return content
      .replace(/^(?:I'll|I will) show you (?:a|the) visual[^.!?]*[.!?]\s*/i, "")
      .replace(/^This will help you see[^.!?]*[.!?]\s*/i, "")
      .replace(/I'd be happy to (show you|help with)[^.!?]*[.!?]\s*/i, "")
      .replace(/Let me (display|show) (that|this|a visual)[^.!?]*[.!?]\s*/i, "")
      .replace(/^(Great!\s*)?Let me check your understanding[^:]*:\s*/i, "")
      .replace(/^Here's a question for you:\s*/i, "")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/__(.*?)__/g, "$1")
      .replace(/(?<!\w)\*([^*\n]+)\*(?!\w)/g, "$1")
      .replace(/(?<!\w)_([^_\n]+)_(?!\w)/g, "$1")
      .replace(/\s{2,}/g, " ")
      .trim() || (narratedVisual ? "Follow the highlighted relationship in the visual as you connect it to the idea." : "")
  }
  const polishLearnerText = (content: string) => content
    .replace(/^(Great!\s*)?Let me check your understanding[^:]*:\s*/i, "")
    .replace(/^Here's a question for you:\s*/i, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/__(.*?)__/g, "$1")
    .replace(/(?<!\w)\*([^*\n]+)\*(?!\w)/g, "$1")
    .replace(/(?<!\w)_([^_\n]+)_(?!\w)/g, "$1")
    .replace(/\s{2,}/g, " ")
    .trim()
  return <div className="learn-scene-support" aria-label="Tutor teaching">
    {fallbackBlocks.map((block) => {
      if (block.kind === "visual") {
        if (visualRendered || !primaryVisual || block.id !== visualBlocks[0]?.id) return null
        visualRendered = true
        block = primaryVisual
      }
      const referenced = block.visualRef && typeof block.visualRef.componentIndex === "number" ? note.components[block.visualRef.componentIndex] : null
      const polishedContent = block.content ? polishLearnerText(block.kind === "tutor_message" ? learnerTutorText(block.content) : block.content) : ""
      if (!polishedContent && !block.title && !block.visualSpec && !referenced) return null
      return <section className={`learn-scene-block learn-scene-block-${block.kind}`} key={block.id}>
        <p className="learn-scene-block-label">{block.kind === "tutor_message" || block.label?.toLowerCase() === "try" ? (block.label?.toLowerCase() === "try" ? "Tutor prompt" : "Tutor") : block.kind === "feedback" ? "Feedback" : block.label}</p>
        {block.title && !(block.visualSpec || referenced) && <h3>{block.title}</h3>}
        {polishedContent && <p className="learn-scene-block-content">{polishedContent}</p>}
        {block.visualSpec && <div className="learn-teaching-visual"><StructuredVisual spec={block.visualSpec} initialStage={session.scene?.visualState?.stage ?? 0} onStageChange={onVisualStageChange} /></div>}
        {referenced && <div className="learn-teaching-visual"><ComponentView component={referenced as any} /></div>}
      </section>
    })}
  </div>
}

function AskLucentInline({ askOpen, setAskOpen, askMessage, setAskMessage, askLoading, askAnswer, onAsk, onHint, practiceAvailable }: { askOpen: boolean; setAskOpen: (value: boolean) => void; askMessage: string; setAskMessage: (value: string) => void; askLoading: boolean; askAnswer: any; onAsk: (message?: string) => void; onHint?: () => void; practiceAvailable?: boolean }) {
  const quickActions = practiceAvailable ? ["Give me a hint", "Walk me through it", "Ask me a simpler question", "Ask me a harder question"] : ["Explain differently", "Show me visually", "Give me an example", "Why does this matter?"]
  return <div className="learn-ask-lucent"><button type="button" className="learn-ask-toggle" onClick={() => setAskOpen(!askOpen)} aria-expanded={askOpen}>Ask Lucent</button>{askOpen && <div className="learn-ask-panel"><p className="learn-ask-context">Ask the tutor about what you are seeing.</p><div className="learn-ask-quick-actions">{quickActions.map((action) => <button key={action} type="button" className="learn-ask-quick" onClick={() => action === "Give me a hint" ? onHint?.() : onAsk(action)}>{action}</button>)}</div><div className="learn-ask-row"><input aria-label="Ask Lucent a question" value={askMessage} onChange={(event) => setAskMessage(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") onAsk() }} placeholder="Ask about this idea…" /><button className="btn btn-primary" type="button" onClick={() => onAsk()} disabled={askLoading || !askMessage.trim()}>{askLoading ? "Thinking…" : "Ask"}</button></div>{askLoading && <div className="learn-ask-loading" role="status" aria-label="Lucent is thinking"><span /><span /><span /></div>}{askAnswer && !askAnswer.scene && <div className="learn-ask-answer" role="status"><p>{askAnswer.answer}</p></div>}</div>}</div>
}

export function LearnView({ note, documentId, onBack }: { note: SectionNote; documentId: number | null | undefined; onBack: () => void }) {
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
  const [askOpen, setAskOpen] = useState(false)
  const [askMessage, setAskMessage] = useState("")
  const [askAnswer, setAskAnswer] = useState<{ answer: string; scope: string; tool?: string } | null>(null)
  const [askLoading, setAskLoading] = useState(false)
  const [restartRequested, setRestartRequested] = useState(false)
  const sessionRef = useRef<LearnSession | null>(null)
  const headingRef = useRef<HTMLHeadingElement | null>(null)
  const focusedSceneId = useRef<string | null>(null)

  useEffect(() => {
    // Focus the heading when entering a new scene, but not when Ask Lucent
    // mutates the current scene in place. Refocusing on every revision reset
    // the learner's scroll position to the top after each Ask response.
    if (session?.status === "active" && session.scene && focusedSceneId.current !== session.scene.id) {
      focusedSceneId.current = session.scene.id
      headingRef.current?.focus()
    }
  }, [session?.scene?.id, session?.scene?.revision])

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
    // LearnView can remain mounted while the learner switches between saved
    // documents.  Do not let the previous document's sessionRef keep the old
    // scene authoritative for the newly selected material.
    sessionRef.current = null
    setSession(null)
    setFocusMode(false)
    setAskAnswer(null)
    setAskMessage("")
    setAnswer("")
    setSelectedOption(null)
    setOrderedIds([])
    setStructuredAnswers({})
    setHint(null)
    let cancelled = false
    api.getActiveLearnSession(documentId).then((active) => {
      if (!cancelled && active && !sessionRef.current) {
        sessionRef.current = active
        setSession(active)
        setFocusMode(true)
        // Rehydrate interaction-local controls from the authoritative scene on
        // resume.  Previously an ordering/matching interaction loaded after a
        // refresh with an empty local selection, making the visible practice
        // surface appear blank and impossible to submit.
        const activeId = active.scene?.responseInteractionId
        const practice = active.scene?.blocks.find((block) => block.kind === "practice" && block.step?.id === activeId)?.step
        setOrderedIds(practice?.items?.map((item) => item.id) ?? [])
        setStructuredAnswers({})
      }
    }).catch(() => undefined)
    return () => { cancelled = true }
  }, [documentId])

  async function start() {
    if (!documentId) return
    setLoading(true); setError(null)
    try { const created = await api.createLearnSession(documentId, { goal, familiarity, restart: restartRequested }); sessionRef.current = created; setSession(created); setRestartRequested(false); setFocusMode(true); setAskOpen(false); setAskAnswer(null); setAskMessage(""); setAnswer(""); setSelectedOption(null); const active = created.scene?.responseInteractionId; setOrderedIds(created.scene?.blocks.find((block) => block.kind === "practice" && block.step?.id === active)?.step?.items?.map((item) => item.id) ?? []); setStructuredAnswers({}); setHint(null) }
    catch (e) { setError(e instanceof Error ? e.message : "Lucent could not start this learning session.") }
    finally { setLoading(false) }
  }
  async function startFresh() {
    if (!documentId) return
    setLoading(true); setError(null)
    try {
      const created = await api.createLearnSession(documentId, { goal, familiarity, restart: true })
      sessionRef.current = created
      setSession(created)
      setFocusMode(true)
      setAskOpen(false); setAskAnswer(null); setAskMessage("")
      setAnswer(""); setSelectedOption(null); setStructuredAnswers({}); setHint(null)
      const active = created.scene?.responseInteractionId
      setOrderedIds(created.scene?.blocks.find((block) => block.kind === "practice" && block.step?.id === active)?.step?.items?.map((item) => item.id) ?? [])
    } catch (e) { setError(e instanceof Error ? e.message : "Lucent could not start a new learning session.") }
    finally { setLoading(false) }
  }
  async function respond(response?: string, optionId?: string) {
    if (!session) return
    setLoading(true); setError(null)
    try { const active = session.scene?.responseInteractionId; const practice = session.scene?.blocks.find((block) => block.kind === "practice" && block.step?.id === active)?.step; const updated = await api.submitLearnResponse(session.id, { sceneId: session.scene?.id, sceneRevision: session.scene?.revision, interactionId: practice?.id, eventType: practice ? "RESPONSE" : "CONTINUE", response, optionId, orderedIds: orderedIds.length ? orderedIds : undefined }); sessionRef.current = updated; setSession(updated); setAnswer(""); setSelectedOption(null); const nextActive = updated.scene?.responseInteractionId; setOrderedIds(updated.scene?.blocks.find((block) => block.kind === "practice" && block.step?.id === nextActive)?.step?.items?.map((item) => item.id) ?? []); setStructuredAnswers({}); setHint(null) }
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
  async function askLucent(messageOverride?: string) {
    const message = messageOverride?.trim() || askMessage.trim()
    if (!session || !message) return
    setAskLoading(true); setError(null)
    try { const result = await api.askLucent(session.id, message); setAskAnswer(result); if (result.scene) setSession((current) => current ? { ...current, scene: result.scene } : current); setAskMessage("") }
    catch (e) { setError(e instanceof Error ? e.message : "Ask Lucent could not respond right now.") }
    finally { setAskLoading(false) }
  }
  async function setVisualStage(stage: number) {
    if (!session?.scene) return
    try { const updated = await api.learnVisualEvent(session.id, { sceneId: session.scene.id, sceneRevision: session.scene.revision, event: "set_stage", stage }); setSession(updated) }
    catch { /* the local stage still advanced optimistically; a stale scene will resync on the next response or refresh */ }
  }

  if (!session) return <section className="learn-workspace learn-onboarding" aria-labelledby="learn-heading">
    <button className="learn-back" type="button" onClick={onBack}>← Back to notes</button>
    <p className="note-kicker">Focused learning</p>
    <h2 id="learn-heading">What do you want to get out of this?</h2>
    <p className="learn-context">{note.title}</p>
    <div className="learn-choice-group"><p className="learn-choice-label">Choose a goal</p><div className="learn-choice-grid">{([['understand', 'Understand the concepts', 'Build intuition and see how ideas connect.'], ['solve', 'Learn to solve problems', 'Practice methods and apply them step by step.'], ['memorize', 'Memorize the content', 'Practice important facts, terms, and formulas.'], ['exam', 'Prepare for an exam', 'Mix understanding, recall, and application.']] as const).map(([value, label, description]) => <button type="button" key={value} className={goal === value ? "learn-choice selected" : "learn-choice"} onClick={() => setGoal(value)}><strong>{label}</strong><span>{description}</span></button>)}</div></div>
    <div className="learn-choice-group"><p className="learn-choice-label">How familiar are you with this already?</p><div className="learn-familiarity-row">{([['new', 'New to this'], ['somewhat_familiar', 'Somewhat familiar'], ['reviewing', 'Mostly reviewing']] as const).map(([value, label]) => <button type="button" key={value} className={familiarity === value ? "learn-familiarity selected" : "learn-familiarity"} onClick={() => setFamiliarity(value)}>{label}</button>)}</div></div>
    {error && <p className="error learn-onboarding-error" role="alert">{error}</p>}
    <button className="btn btn-primary" type="button" disabled={loading || !documentId} onClick={start}>{loading ? "Preparing your session…" : "Start learning"}</button>
  </section>

  if (session.status !== "active") return <section className="learn-workspace learn-complete" aria-labelledby="learn-heading"><button className="learn-back" type="button" onClick={onBack}>← Back to notes</button><p className="note-kicker">{session.status === "stopped" ? "Session paused" : "Session complete"}</p><h2 id="learn-heading">{session.status === "stopped" ? "Your progress is saved." : `You worked through ${session.completedObjectives} objective${session.completedObjectives === 1 ? "" : "s"}.`}</h2>{session.report && <div className="learn-report"><p><strong>Next focus:</strong> {session.report.nextFocus.join(", ") || "Continue with a new concept."}</p>{session.report.demonstrated.length > 0 && <p><strong>Demonstrated:</strong> {session.report.demonstrated.join(", ")}</p>}{session.report.developing.length > 0 && <p><strong>Still developing:</strong> {session.report.developing.join(", ")}</p>}{session.report.struggles.length > 0 && <p><strong>Needs attention:</strong> {session.report.struggles.join(" ")}</p>}{session.report.misconceptions?.length ? <p><strong>Misconceptions:</strong> {session.report.misconceptions.join(" ")}</p> : null}{session.report.notCovered.length > 0 && <p><strong>Not covered yet:</strong> {session.report.notCovered.join(", ")}</p>}</div>}<div className="learn-result-actions"><button className="btn" type="button" onClick={onBack}>Review notes</button>{session.status === "stopped" && documentId && <button className="btn btn-primary" type="button" onClick={() => { sessionRef.current = null; setSession(null); setRestartRequested(true); setFocusMode(false); setError(null) }}>Start a new learning session</button>}{documentId && <button className="btn" type="button" onClick={() => window.location.assign(`/quizzes/generating?document_id=${documentId}`)}>Take the quiz</button>}</div></section>

  const activeInteractionId = session.scene?.responseInteractionId
  const step = activeInteractionId ? session.scene?.blocks.find((block) => block.kind === "practice" && block.step?.id === activeInteractionId)?.step : undefined
  const sceneTeaching = session.scene?.blocks.filter((block) => block.kind !== "practice") ?? []
  if (!step) return <section className={`learn-workspace learn-session ${focusMode ? "learn-focus-mode" : ""}`} aria-labelledby="learn-heading">
    <div className="learn-session-top"><button className="learn-back" type="button" onClick={onBack}>← Back to notes</button><span>Objective {session.objectiveIndex + 1} of {session.objectiveCount}</span><button className="learn-focus-toggle" type="button" onClick={() => setFocusMode((value) => !value)}>{focusMode ? "Exit focus" : "Focus learning"}</button><button className="learn-restart" type="button" onClick={startFresh} disabled={loading}>Start over</button></div>
    <p className="note-kicker">Watch</p><h2 id="learn-heading" ref={headingRef} tabIndex={-1}>{session.scene?.objective ?? note.title}</h2>
    <div className="learn-scene-shell">
      <article className="learn-step"><LearningSceneView session={session} note={note} onVisualStageChange={setVisualStage} /><div className="learn-step-actions"><button className="btn" type="button" onClick={stop}>Stop for now</button><button className="btn btn-primary" type="button" onClick={() => respond()}>{loading ? "Saving…" : "Continue"}</button></div></article>
      <AskLucentInline askOpen={askOpen} setAskOpen={setAskOpen} askMessage={askMessage} setAskMessage={setAskMessage} askLoading={askLoading} askAnswer={askAnswer} onAsk={askLucent} onHint={requestHint} />
    </div>
    {error && <p className="error" role="alert">{error}</p>}
  </section>
  const visualRef = step.visualRef
  const visualComponent = visualRef && typeof visualRef.componentIndex === "number" ? note.components[visualRef.componentIndex] as any : null
  const requiresResponse = ["multiple_choice", "short_answer", "numeric", "problem", "prediction", "ordering", "matching", "labeling", "fill_blank", "worked_step", "teach_back"].includes(step.type)
  const isStructured = step.type === "matching" || step.type === "labeling"
  const submitResponse = isStructured ? JSON.stringify(structuredAnswers) : answer
  const canSubmit = isStructured ? step.items.length > 0 && step.items.every((item) => Boolean(structuredAnswers[item.id])) : step.type === "ordering" ? orderedIds.length === step.items.length : step.options.length > 0 ? Boolean(selectedOption) : Boolean(submitResponse.trim())
  const learningState: Record<string, string> = { teach: "Watch", walkthrough: "Watch", prediction: "Predict", short_answer: "Explain", teach_back: "Reflect", multiple_choice: "Choose", matching: "Compare", labeling: "Label", ordering: "Order", fill_blank: "Recall", worked_step: "Solve", problem: "Solve", numeric: "Solve" }
  const stateLabel = learningState[step.type] || "Learn"
  const teachingOnly = step.type === "teach" || step.type === "walkthrough"
  const sceneHasFeedback = Boolean(session.scene?.blocks.some((block) => block.kind === "feedback"))
  return <section className={`learn-workspace learn-session ${focusMode ? "learn-focus-mode" : ""}`} aria-labelledby="learn-heading">{focusMode && <div className="learn-focus-backdrop" aria-hidden="true" />}
    <div className="learn-session-top"><button className="learn-back" type="button" onClick={onBack}>← Back to notes</button><span aria-live="polite">Objective {session.objectiveIndex + 1} of {session.objectiveCount}</span><button className="learn-focus-toggle" type="button" onClick={() => setFocusMode((value) => !value)} aria-pressed={focusMode}>{focusMode ? "Exit focus" : "Focus learning"}</button><button className="learn-restart" type="button" onClick={startFresh} disabled={loading}>Start over</button></div>
    <p className="note-kicker">{session.goal === "solve" ? "Problem solving" : session.goal === "memorize" ? "Retrieval practice" : "Focused learning"}</p>
    <h2 id="learn-heading" ref={headingRef} tabIndex={-1}>{session.objectiveTitle ?? note.title}</h2>
    <div className="learn-progress" role="progressbar" aria-valuemin={0} aria-valuemax={session.objectiveCount} aria-valuenow={session.objectiveIndex + 1}><span style={{ width: `${((session.objectiveIndex + 1) / Math.max(1, session.objectiveCount)) * 100}%` }} /></div>
    <div className="learn-scene-shell"><article className="learn-step"><LearningSceneView session={session} note={note} onVisualStageChange={setVisualStage} /><div className={`learn-scene-practice${teachingOnly ? " teaching-only" : ""}`}><div className="learn-action-kicker">{stateLabel}</div><h3>{step.title}</h3>{step.prompt && <p className="learn-question">{step.prompt}</p>}{step.options.length > 0 && !isStructured && <div className="learn-options">{step.options.map((option) => <button type="button" key={option.id} className={selectedOption === option.id ? "learn-option selected" : "learn-option"} onClick={() => setSelectedOption(option.id)}>{option.label}</button>)}</div>}{isStructured && <div className="learn-structured-response">{step.items.map((item) => <label key={item.id}>{item.label}<select aria-label={item.label} value={structuredAnswers[item.id] ?? ""} onChange={(event) => setStructuredAnswers((current) => ({ ...current, [item.id]: event.target.value }))}><option value="">Choose a match…</option>{step.options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>)}</div>}{step.items.length > 0 && step.type === "ordering" && <div className="learn-ordering">{orderedIds.map((id, index) => { const item = step.items.find((candidate) => candidate.id === id); return <div className="learn-ordering-item" key={id}><span>{index + 1}. {item?.label ?? id}</span><button type="button" disabled={index === 0} onClick={() => setOrderedIds((ids) => { const next = [...ids]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next })} aria-label="Move up">↑</button><button type="button" disabled={index === orderedIds.length - 1} onClick={() => setOrderedIds((ids) => { const next = [...ids]; [next[index], next[index + 1]] = [next[index + 1], next[index],] ; return next })} aria-label="Move down">↓</button></div>})}</div>}{requiresResponse && !isStructured && step.options.length === 0 && step.items.length === 0 && <input className="learn-answer" aria-label="Your answer" value={answer} onChange={(event) => setAnswer(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && answer.trim()) respond(submitResponse) }} placeholder="Type your response" />}{hint && <p className="learn-hint" role="status"><strong>Hint {session.hintsUsed}:</strong> {hint}</p>}{session.feedback && !sceneHasFeedback && <p className={`learn-feedback ${session.feedbackKind ?? "info"}`} role="status">{session.feedback}</p>}<div className="learn-step-actions">{step.hintsAvailable > 0 && <button className="btn" type="button" onClick={requestHint}>Hint</button>}<button className="btn" type="button" onClick={stop}>Stop for now</button>{requiresResponse ? <button className="btn btn-primary" type="button" disabled={loading || !canSubmit} onClick={() => respond(submitResponse, selectedOption ?? undefined)}>{loading ? "Checking…" : "Submit"}</button> : <button className="btn btn-primary" type="button" disabled={loading} onClick={() => respond()}>{loading ? "Saving…" : "Continue"}</button>}</div></div></article>
    <AskLucentInline askOpen={askOpen} setAskOpen={setAskOpen} askMessage={askMessage} setAskMessage={setAskMessage} askLoading={askLoading} askAnswer={askAnswer} onAsk={askLucent} onHint={requestHint} practiceAvailable={Boolean(step)} />
    </div>
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
  // Re-fetching notes when only the study mode changes would overwrite a
  // saved-note selection with the document encoded in the URL (which may be
  // an older material).  The selected record is React state; only a document
  // route change should reload it.
  }, [routeDocumentId, Number(searchParams.get("document_id") ?? routeDocumentId)])
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
    {state.status === "complete" && state.result && <><header className="notes-document-heading"><div><p className="note-kicker">Study note</p><h2 className="notes-document-title">{state.result.filename}</h2><p>{notes.length} focused section{notes.length === 1 ? "" : "s"} · about {estimatedMinutes} min · {mode === "learn" ? "focused learning" : mode === "flashcards" ? "recall practice" : "ready to review"}</p></div><div className="notes-actions"><div className="study-mode-tabs" role="tablist" aria-label="Study mode"><button type="button" role="tab" aria-selected={mode === "notes"} className={mode === "notes" ? "active" : ""} onClick={() => setMode("notes")}>Notes</button><button type="button" role="tab" aria-selected={mode === "learn"} className={mode === "learn" ? "active" : ""} onClick={() => setMode("learn", activeNote?.id)}>Learn</button><button type="button" role="tab" aria-selected={mode === "flashcards"} className={mode === "flashcards" ? "active" : ""} onClick={() => setMode("flashcards")}>Flashcards</button><button type="button" role="tab" aria-selected={false} onClick={startQuiz}>Quiz</button></div><label htmlFor="notes-depth">Learning depth</label><select id="notes-depth" value={depth} onChange={(event) => setDepth(event.target.value as DepthMode)}><option value="concise">Concise Study Guide</option><option value="balanced">Balanced</option><option value="detailed">Detailed Explanation</option></select><button className="btn btn-primary" type="button" disabled={quizStatus === "working" || !state.result.document_id} onClick={mode === "learn" ? () => setMode("learn", activeNote?.id) : startQuiz}>{mode === "learn" ? "Start learning" : quizStatus === "working" ? "Building quiz…" : "Check your understanding"}</button></div></header>{quizStatus === "error" && <p className="error" role="alert">This note is available to study, but Lucent could not start its quiz.</p>}{mode === "learn" && activeNote ? <LearnView note={activeNote} documentId={state.result.document_id} onBack={() => setMode("notes", activeNote.id)} /> : mode === "flashcards" ? <FlashcardsView notes={notes} onBack={() => setMode("notes")} /> : <><nav className="section-index" aria-label="Note sections"><span>Sections</span>{notes.map((note, index) => { const hasWalkthrough = note.components.some((component: any) => component.kind === "walkthrough" && component.mechanism); return <span className="section-index-item" key={note.id}><a className={note.id === activeNote?.id ? "active" : ""} href={`#${note.id}`}>{index + 1}. {note.title}</a>{hasWalkthrough && <button type="button" onClick={() => setMode("learn", note.id)} aria-label={`Learn ${note.title}`}>Learn</button>}</span>})}</nav>{notes.length ? <NoteView notes={notes} depth={depth} /> : <p className="empty">No sections were produced for this document.</p>}</>}</>}
  </div>
}
