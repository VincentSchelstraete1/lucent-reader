import type { GeneratedNote } from "../api/client"

export function GeneratedNoteView({ note }: { note: GeneratedNote }) {
  return (
    <div className="generated-note">
      <p className="generated-note-summary">{note.summary}</p>

      {note.key_points.length > 0 && (
        <div className="generated-note-block">
          <h4>Key points</h4>
          <ul>
            {note.key_points.map((point, i) => (
              <li key={i}>{point}</li>
            ))}
          </ul>
        </div>
      )}

      {note.concepts.length > 0 && (
        <div className="generated-note-block">
          <h4>Concepts</h4>
          <div className="chip-row">
            {note.concepts.map((concept, i) => (
              <span className="chip" key={i}>
                {concept}
              </span>
            ))}
          </div>
        </div>
      )}

      {note.sections.length > 0 && (
        <div className="generated-note-block">
          {note.sections.map((section, i) => (
            <div className="generated-note-section" key={i}>
              <h4>{section.heading}</h4>
              <p>{section.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
