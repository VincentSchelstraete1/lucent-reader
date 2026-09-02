import { useMemo, useState } from "react"
import { buildProcessLearningObject } from "../builders/processBuilder"
import { ProcessRenderer } from "../renderers/ProcessRenderer"
import { routeRepresentation } from "../routing/representationRouter"
import { REPRESENTATION_TYPES } from "../routing/representationTypes"
import styles from "./learningCanvasDemo.module.css"

const EXAMPLE = "The client sends SYN. Then the server responds with SYN-ACK. Finally the client sends ACK."

export function LearningCanvasDemo() {
  const [sourceText, setSourceText] = useState(EXAMPLE)
  const route = useMemo(() => routeRepresentation(sourceText), [sourceText])
  const processObject = useMemo(() => {
    if (route.type !== "process") return null
    try { return buildProcessLearningObject(sourceText) } catch { return null }
  }, [route.type, sourceText])

  return (
    <section className={styles.page}>
      <header className="page-header">
        <h1>Learning Canvas prototype</h1>
        <p className="page-subtitle">Deterministic routing → semantic learning object → renderer</p>
      </header>

      <label className={styles.label} htmlFor="learning-source">Source text</label>
      <textarea id="learning-source" className={styles.input} rows={6} value={sourceText} onChange={(event) => setSourceText(event.target.value)} />

      <div className={styles.grid}>
        <article className={styles.panel}>
          <h2>Router result</h2>
          <dl className={styles.resultList}>
            <div><dt>Type</dt><dd>{route.type}</dd></div>
            <div><dt>Confidence</dt><dd>{route.confidence.toFixed(2)}</dd></div>
          </dl>
          <ul>{route.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          <div className={styles.scores}>
            {REPRESENTATION_TYPES.map((type) => <span key={type}>{type}: {route.scores[type].toFixed(2)}</span>)}
          </div>
        </article>

        <article className={styles.panel}>
          <h2>Process LearningObject</h2>
          {processObject ? <pre className={styles.json}>{JSON.stringify(processObject, null, 2)}</pre> : <p>This first slice renders only text routed as a process.</p>}
        </article>
      </div>

      <article className={styles.diagramPanel}>
        <h2>Process renderer</h2>
        {processObject ? <ProcessRenderer object={processObject} /> : <p>No process diagram for the current routing result.</p>}
      </article>
    </section>
  )
}
