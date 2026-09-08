import { useEffect, useRef, useState } from "react"
import { StructuredVisual, type StructuredVisualSpec } from "../../learning/visuals/StructuredVisual"
import styles from "./marketing.module.css"

export const qualityControlVisual: StructuredVisualSpec = {
  type: "process_flow",
  title: "Control signals in intracellular quality control",
  purpose: "Follow how a damaged protein is recognized and contained before it can disrupt the cell.",
  nodes: [
    { id: "damage", label: "Damage detected", detail: "A protein no longer folds into its working shape.", role: "input" },
    { id: "signal", label: "Control signal", detail: "The cell marks the damaged protein for a response.", role: "mechanism" },
    { id: "checkpoint", label: "Checkpoint response", detail: "Repair, isolate, or remove the faulty protein.", role: "process" },
    { id: "protected", label: "Cell protected", detail: "The disruption is kept from spreading.", role: "outcome" },
  ],
  edges: [
    { source: "damage", target: "signal", label: "triggers" },
    { source: "signal", target: "checkpoint", label: "directs" },
    { source: "checkpoint", target: "protected", label: "protects" },
  ],
  stages: [
    { title: "Detect", explanation: "Begin with the damaged protein.", activeNodeIds: ["damage"] },
    { title: "Respond", explanation: "The signal directs the cell's response to the damage.", activeNodeIds: ["signal", "checkpoint"] },
    { title: "Protect", explanation: "Containment protects the wider cell.", activeNodeIds: ["checkpoint", "protected"] },
  ],
}

export function LucentProductDemo() {
  const frameRef = useRef<HTMLDivElement>(null)
  const askAnswerRef = useRef<HTMLParagraphElement>(null)
  const [answer, setAnswer] = useState<string | null>(null)
  const [asked, setAsked] = useState<"explain" | "why" | null>(null)
  const [stage, setStage] = useState(0)
  // Keep the shared renderer unchanged; contain keyboard focus within its
  // expanded visual when it is embedded in this public preview.
  useEffect(() => {
    const frame = frameRef.current
    if (!frame) return
    let dialog: HTMLElement | null = null
    let returnFocus: HTMLElement | null = null
    const observer = new MutationObserver(() => {
      const next = frame.querySelector<HTMLElement>('[role="dialog"]')
      if (next === dialog) return
      if (next) {
        returnFocus = document.activeElement as HTMLElement
        next.querySelector<HTMLButtonElement>('.structured-visual-close')?.focus({ preventScroll: true })
      } else if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true })
      dialog = next
    })
    const containFocus = (event: KeyboardEvent) => {
      if (!dialog || event.key !== "Tab") return
      const controls = Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), [tabindex="0"]'))
      const first = controls[0], last = controls[controls.length - 1]
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault(); last?.focus()
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault(); first?.focus()
      }
    }
    observer.observe(frame, { childList: true, subtree: true })
    document.addEventListener('keydown', containFocus)
    return () => { observer.disconnect(); document.removeEventListener('keydown', containFocus) }
  }, [])
  useEffect(() => {
    const frame = frameRef.current
    const response = askAnswerRef.current
    if (!asked || !frame || !response || frame.scrollHeight <= frame.clientHeight) return
    const overflow = response.getBoundingClientRect().bottom - frame.getBoundingClientRect().bottom
    if (overflow > 0) frame.scrollTop += overflow + 18
  }, [asked])
  function respond(value: string) {
    setAnswer(value)
    setStage(value === "correct" ? 2 : 1)
  }
  return (
    <div ref={frameRef} className={styles.productFrame} aria-label="Lucent Learn product demonstration">
      <header className={styles.productHeader}>
        <strong>Lucent</strong>
        <span>Cellular quality control</span>
        <small>Interactive example</small>
      </header>
      <div className={styles.productBody}>
        <aside className={styles.productSidebar} aria-label="Product navigation">
          <span>Library</span>
          <strong>Learn</strong>
          <span>Flashcards</span>
          <span>Quiz</span>
        </aside>
        <div className={styles.productMain}>
          <div className={styles.lessonTopline}>
            <div><small>BUILDING UNDERSTANDING</small><h3>From damage to response</h3></div>
            <div className={styles.productModes} aria-label="Previewing Learn mode"><span>Notes</span><strong>Learn</strong><span>Flashcards</span><span>Quiz</span></div>
          </div>
          <div className={styles.lessonGrid}>
            <section className={styles.lessonTeaching}>
              <p className={styles.productKicker}>WATCH</p>
              <p className={styles.tutorCopy}>{answer === "wrong" ? "Notice the two highlighted steps: the signal carries the message; the response handles the damage. Detecting a problem alone does not fix it." : "Finding damage is only the beginning. The control signal connects what the cell detects to a response that protects it."}</p>
              <div className={styles.productVisual}><StructuredVisual spec={qualityControlVisual} initialStage={stage} onStageChange={setStage} /></div>
              <p className={styles.visualScrollHint}>Swipe the visual to follow the signal →</p>
              <div className={styles.askStrip}>
                <span>Ask Lucent</span>
                <button type="button" aria-pressed={asked === "explain"} onClick={() => setAsked("explain")}>Explain differently</button>
                <button type="button" aria-pressed={asked === "why"} onClick={() => setAsked("why")}>Why does this matter?</button>
              </div>
              {asked && <p ref={askAnswerRef} className={styles.askAnswer} role="status">{asked === "explain" ? "Think of a smoke alarm. It detects smoke and calls for action, but it does not put out the fire. In the same way, the signal directs a response rather than doing the repair itself." : "A damaged protein can interfere with other cell processes. Connecting detection to a response lets the cell contain that disruption before it spreads."}</p>}
            </section>
            <section className={styles.lessonPractice}>
              <p className={styles.productKicker}>TRY</p>
              <h4>Why does the control signal matter?</h4>
              <p>Choose the relationship supported by the visual.</p>
              <button type="button" aria-pressed={answer === "correct"} onClick={() => respond("correct")}>It connects detection to a protective response.</button>
              <button type="button" aria-pressed={answer === "wrong"} onClick={() => respond("wrong")}>It repairs every damaged protein by itself.</button>
              {answer && <p className={answer === "correct" ? styles.correctFeedback : styles.guidedFeedback} role="status">{answer === "correct" ? "Exactly. The signal coordinates the next action." : "Look at the highlighted middle relationship: the signal directs a response; it is not the repair itself."}</p>}
              {(answer || asked) && <button type="button" className={styles.demoReset} onClick={() => { setAnswer(null); setAsked(null); setStage(0) }}>Reset example</button>}
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
