import { useMemo, useState } from "react"
import { buildLearningObject } from "../builders/learningObjectBuilder"
import { LearningObjectRenderer } from "../renderers/LearningObjectRenderer"
import { routeRepresentation } from "../routing/representationRouter"
import { REPRESENTATION_TYPES } from "../routing/representationTypes"
import styles from "./learningCanvasDemo.module.css"

const EXAMPLE = "The client sends SYN. Then the server responds with SYN-ACK. Finally the client sends ACK."

export function LearningCanvasDemo() {
  const [sourceText, setSourceText] = useState(EXAMPLE)
  const route = useMemo(() => routeRepresentation(sourceText), [sourceText])
  const learningObject = useMemo(() => {
    try { return buildLearningObject(route.type, sourceText) } catch { return null }
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
          <h2>LearningObject</h2>
          {learningObject ? <pre className={styles.json}>{JSON.stringify(learningObject, null, 2)}</pre> : <p>No deterministic builder exists for this representation yet.</p>}
        </article>
      </div>

      <article className={styles.diagramPanel}>
        <h2>{learningObject ? `${learningObject.type} renderer` : "Renderer"}</h2>
        {learningObject ? <LearningObjectRenderer object={learningObject} /> : <p>No renderer for the current routing result.</p>}
      </article>
    </section>
  )
}
