import type { GeneratedLearningNote } from "../../api/client"
import { LearningObjectRenderer } from "../renderers/LearningObjectRenderer"

export function GeneratedNoteRenderer({ note }: { note: GeneratedLearningNote }) {
  return <section aria-labelledby="generated-note"><h2 id="generated-note">Generated structured note</h2><p>{note.sections.length} sections · assembled in source order</p>{note.sections.map(section => <article key={section.learningBlockId} style={{ borderTop: "1px solid #ddd", padding: "1rem 0" }}><h3>{section.title || section.learningObject.title}</h3><p><small>{section.learningObject.type} · block {section.learningBlockId}{section.generationFallback ? " · plain-text fallback" : ""}</small></p><LearningObjectRenderer object={section.learningObject} /><details><summary>Source provenance</summary><pre>{JSON.stringify(section.source, null, 2)}</pre></details></article>)}</section>
}
