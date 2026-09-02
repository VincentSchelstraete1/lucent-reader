import { useState, type FormEvent } from "react"
import { api, type PdfIngestionResult, type RawImage } from "../api/client"
import styles from "./pdfIngestionDemo.module.css"

type IngestionState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "error"; message: string }
  | { status: "success"; result: PdfIngestionResult }

function formatBbox(bbox: [number, number, number, number] | null) {
  return bbox ? `[${bbox.map((value) => value.toFixed(1)).join(", ")}]` : "unavailable"
}

function ImageInspection({ image }: { image: RawImage }) {
  return (
    <figure className={styles.imageCard}>
      {image.mime_type?.startsWith("image/") ? (
        <img src={image.asset_reference} alt={image.caption || `Extracted PDF image ${image.id}`} />
      ) : (
        <p>Preview unavailable for {image.mime_type || "unknown image format"}</p>
      )}
      <figcaption>
        <strong>{image.id}</strong>
        <span>{image.width ?? "?"} × {image.height ?? "?"} px · {image.mime_type || "unknown MIME"}</span>
        <span>bbox {formatBbox(image.bbox)}</span>
        <span>Caption: {image.caption || "none conservatively detected"}</span>
      </figcaption>
    </figure>
  )
}

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
        <p className="page-subtitle">Inspect page-aware raw extraction alongside MarkItDown&apos;s global Markdown.</p>
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
          <section className={styles.metadata} aria-labelledby="document-metadata">
            <h2 id="document-metadata">Raw document</h2>
            <dl>
              <div><dt>Filename</dt><dd>{state.result.filename}</dd></div>
              <div><dt>Physical pages</dt><dd>{state.result.page_count}</dd></div>
              <div><dt>Images</dt><dd>{state.result.images.length}</dd></div>
              <div><dt>Markdown characters</dt><dd>{state.result.extracted_character_count.toLocaleString()}</dd></div>
            </dl>
            <pre>{JSON.stringify(state.result.extraction_metadata, null, 2)}</pre>
          </section>

          <section aria-labelledby="physical-pages">
            <h2 id="physical-pages">Physical pages</h2>
            <div className={styles.pages}>
              {state.result.pages.map((page) => {
                const images = state.result.images.filter((image) => image.page_number === page.page_number)
                return (
                  <details className={styles.pageCard} key={page.page_number} open={page.page_number === 1}>
                    <summary>Page {page.page_number} · {page.blocks.length} blocks · {images.length} images</summary>
                    {page.extraction_errors.map((error) => <p className="error" key={error}>{error}</p>)}
                    <h3>Page text</h3>
                    <pre className={styles.rawText}>{page.text || "(no text extracted)"}</pre>
                    <h3>Raw blocks</h3>
                    <ol className={styles.blocks}>
                      {page.blocks.map((block) => (
                        <li key={block.id}>
                          <code>#{block.reading_order} · {block.type} · bbox {formatBbox(block.bbox)}</code>
                          {block.text !== null && <pre>{block.text || "(empty text block)"}</pre>}
                          {block.image_id && <span>Image: {block.image_id}</span>}
                        </li>
                      ))}
                    </ol>
                    {images.length > 0 && (
                      <>
                        <h3>Images and figures</h3>
                        <div className={styles.images}>{images.map((image) => <ImageInspection key={image.id} image={image} />)}</div>
                      </>
                    )}
                  </details>
                )
              })}
            </div>
          </section>

          <details className={styles.markdownSection}>
            <summary>Global raw MarkItDown output</summary>
            <div className={styles.outputHeader}>
              <p>{state.result.extracted_character_count.toLocaleString()} characters</p>
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
          </details>
        </section>
      )}
    </section>
  )
}
