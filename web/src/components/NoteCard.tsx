import type { Note, GeneratedNote } from "../api/client"
import { GeneratedNoteView } from "./GeneratedNoteView"

const CONTENT_TYPE_LABELS: Record<string, string> = {
  highlight: "Highlight",
  explanation: "Explanation",
  simplification: "Simplification",
  generated_note: "Generated Note"
}

function parseGeneratedNote(content: string): GeneratedNote | null {
  try {
    const parsed = JSON.parse(content)
    if (parsed && Array.isArray(parsed.sections)) return parsed as GeneratedNote
    return null
  } catch {
    return null
  }
}

export function NoteCard({ note }: { note: Note }) {
  const generated = note.content_type === "generated_note" ? parseGeneratedNote(note.content) : null

  return (
    <div className="card note-card">
      <div className="card-title">
        {note.title}
        <span className={`badge badge-${note.content_type}`}>
          {CONTENT_TYPE_LABELS[note.content_type] || note.content_type}
        </span>
      </div>

      {generated ? (
        <GeneratedNoteView note={generated} />
      ) : (
        <>
          {note.source_passage && (
            <blockquote className="source-passage">
              <span>Selected passage</span>
              {note.source_passage}
            </blockquote>
          )}
          <div className="card-body">{note.content}</div>
        </>
      )}

      <div className="card-meta">Updated {new Date(note.updated_at).toLocaleString()}</div>
    </div>
  )
}
