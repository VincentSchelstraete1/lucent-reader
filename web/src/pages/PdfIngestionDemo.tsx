import { useState, type FormEvent } from "react"
import { api, type PdfIngestionResult } from "../api/client"
import styles from "./pdfIngestionDemo.module.css"

type IngestionState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "error"; message: string }
  | { status: "success"; result: PdfIngestionResult }

export function PdfIngestionDemo() {
  const [file, setFile] = useState<File | null>(null)
  const [state, setState] = useState<IngestionState>({ status: "idle" })
  const [copied, setCopied] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    setCopied(false)
    setState({ status: "uploading" })
    try {
      setState({ status: "success", result: await api.ingestPdf(file) })
    } catch (error) {
      setState({ status: "error", message: error instanceof Error ? error.message : "PDF extraction failed" })
    }
  }

  async function copyMarkdown(markdown: string) {
    try {
      await navigator.clipboard.writeText(markdown)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className={styles.page}>
      <header className="page-header">
        <p className={styles.devLabel}>Development tool</p>
        <h1>PDF ingestion inspector</h1>
        <p className="page-subtitle">Upload a PDF and inspect MarkItDown&apos;s unmodified extraction output.</p>
      </header>

      <form className={styles.form} onSubmit={submit}>
        <label htmlFor="pdf-upload">PDF file</label>
        <input
          id="pdf-upload"
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null)
            setState({ status: "idle" })
          }}
        />
        <button type="submit" disabled={!file || state.status === "uploading"}>
          {state.status === "uploading" ? "Extracting…" : "Upload and extract"}
        </button>
      </form>

      {state.status === "uploading" && <p role="status">Uploading and processing the PDF…</p>}
      {state.status === "error" && <p className="error" role="alert">{state.message}</p>}

      {state.status === "success" && (
        <section className={styles.output}>
          <div className={styles.outputHeader}>
            <div>
              <h2>Raw MarkItDown output</h2>
              <p>{state.result.original_filename} · {state.result.extracted_character_count.toLocaleString()} characters</p>
            </div>
            <button type="button" onClick={() => copyMarkdown(state.result.markdown)}>
              {copied ? "Copied" : "Copy Markdown"}
            </button>
          </div>
          <textarea
            className={styles.markdown}
            aria-label="Raw extracted Markdown"
            readOnly
            value={state.result.markdown}
            spellCheck={false}
          />
        </section>
      )}
    </section>
  )
}
