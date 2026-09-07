import { useState } from "react"
import { api, type LearningCanvasResult } from "../../api/client"
import { LearningObjectRenderer } from "../renderers/LearningObjectRenderer"
import styles from "./learningCanvasDemo.module.css"

const EXAMPLE = "The client sends SYN. Then the server responds with SYN-ACK. Finally the client sends ACK."

export function LearningCanvasDemo() {
  const [sourceText, setSourceText] = useState(EXAMPLE)
  const [result, setResult] = useState<LearningCanvasResult | null>(null)
  const [isLoading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function analyze() {
    if (!sourceText.trim()) return
    setLoading(true); setError(null)
    try { setResult(await api.routeLearningCanvas(sourceText)) }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to route this text") }
    finally { setLoading(false) }
  }

  return (
    <section className={styles.page}>
      <header className="page-header">
        <h1>Learning Canvas prototype</h1>
        <p className="page-subtitle">Deterministic routing → semantic learning object → renderer</p>
      </header>

      <label className={styles.label} htmlFor="learning-source">Source text</label>
      <textarea id="learning-source" className={styles.input} rows={6} value={sourceText} onChange={(event) => { setSourceText(event.target.value); setResult(null) }} />
      <button type="button" onClick={analyze} disabled={isLoading || !sourceText.trim()}>{isLoading ? "Analyzing…" : "Analyze with production router"}</button>
      {error && <p className="error" role="alert">{error}</p>}

      {result && <>
      <div className={styles.grid}>
        <article className={styles.panel}>
          <h2>Router result</h2>
          <dl className={styles.resultList}>
            <div><dt>Type</dt><dd>{result.decision.type}</dd></div>
            <div><dt>Confidence</dt><dd>{result.decision.confidence?.toFixed(2) ?? "not calibrated (fallback)"}</dd></div>
            <div><dt>Method</dt><dd>{result.decision.method}</dd></div>
            <div><dt>Fallback used</dt><dd>{result.decision.fallback_used ? "yes" : "no"}</dd></div>
          </dl>
          <div className={styles.scores}>
            {Object.entries(result.decision.scores).map(([type, score]) => <span key={type}>{type}: {score.toFixed(2)}</span>)}
          </div>
          <h3>Teaching plan</h3>
          <p>{result.teaching_plan.rationale}</p>
          <p><strong>Final representation:</strong> {result.teaching_plan.finalRepresentation}{result.teaching_plan.override ? " (planner override)" : ""}</p>
          <ul>{result.teaching_plan.representationPlan.map(item => <li key={item}>{item}</li>)}</ul>
        </article>

        <article className={styles.panel}>
          <h2>LearningObject</h2>
          <pre className={styles.json}>{JSON.stringify(result.learning_object, null, 2)}</pre>
        </article>
      </div>

      <article className={styles.diagramPanel}>
        <h2>{result.learning_object.type} renderer</h2>
        <LearningObjectRenderer object={result.learning_object} />
      </article>
      </>}
    </section>
  )
}
