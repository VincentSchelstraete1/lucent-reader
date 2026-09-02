import { useState, type FormEvent } from "react"
import { api, ingestionEndpointFor, type DocumentIngestionResult, type RawImage, type RawPage, type SourceLocation } from "../api/client"
import styles from "./documentIngestionDemo.module.css"

type IngestionState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "error"; message: string }
  | { status: "success"; result: DocumentIngestionResult }

function formatBbox(bbox: [number, number, number, number] | null) {
  return bbox ? `[${bbox.map((value) => value.toFixed(1)).join(", ")}]` : "unavailable"
}

function formatLocation(location: SourceLocation | null) {
  if (!location) return "unavailable"
  const parts: string[] = [location.kind]
  if (location.index !== null) parts.push(`#${location.index}`)
  if (location.sequence_id) parts.push(location.sequence_id)
  return parts.join(" · ")
}

// Pages/images/events all carry `location` now that page_number is legacy
// PDF-only (DOCX/PPTX report page_number=null for every page - see
// SourceLocation's docstring). Matching a page's images/events by
// page_number equality breaks for multi-slide PPTX, where every slide's
// page_number is null, so this matches on location identity instead.
function sameLocation(a: SourceLocation | null, b: SourceLocation | null) {
  if (!a || !b) return a === b
  return a.kind === b.kind && a.index === b.index
}

function ImageInspection({ image }: { image: RawImage }) {
  return (
    <figure className={styles.imageCard}>
      {image.mime_type?.startsWith("image/") ? (
        <img src={image.asset_reference} alt={image.caption || `Extracted image ${image.id}`} />
      ) : (
        <p>Preview unavailable for {image.mime_type || "unknown image format"}</p>
      )}
      <figcaption>
        <strong>{image.id}</strong>
        <span>{image.width ?? "?"} × {image.height ?? "?"} px · {image.mime_type || "unknown MIME"}</span>
        <span>bbox {formatBbox(image.bbox)}</span>
        <span>location {formatLocation(image.location)}</span>
        <span>Caption: {image.caption || "none conservatively detected"}</span>
      </figcaption>
    </figure>
  )
}

function pageSummaryLabel(page: RawPage) {
  if (page.location?.kind === "slide") return `Slide ${page.location.index}`
  if (page.location?.kind === "document") return "Document"
  return `Page ${page.page_number ?? "?"}`
}

export function DocumentIngestionDemo() {
  const [file, setFile] = useState<File | null>(null)
  const [state, setState] = useState<IngestionState>({ status: "idle" })
  const [copied, setCopied] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    setCopied(false)
    setState({ status: "uploading" })
    try {
      setState({ status: "success", result: await api.ingestDocument(file) })
    } catch (error) {
      setState({ status: "error", message: error instanceof Error ? error.message : "Document extraction failed" })
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
        <h1>Document ingestion inspector</h1>
        <p className="page-subtitle">
          Inspect page-aware raw extraction alongside MarkItDown&apos;s global Markdown, for PDF, DOCX, and PPTX.
        </p>
      </header>

      <form className={styles.form} onSubmit={submit}>
        <label htmlFor="document-upload">PDF, DOCX, or PPTX file</label>
        <input
          id="document-upload"
          type="file"
          accept=".pdf,.docx,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation"
          onChange={(event) => {
            const nextFile = event.target.files?.[0] ?? null
            setFile(nextFile)
            setState({ status: "idle" })
          }}
        />
        {file && !ingestionEndpointFor(file.name) && (
          <p className="error" role="alert">Unsupported file type - choose a .pdf, .docx, or .pptx file.</p>
        )}
        <button type="submit" disabled={!file || !ingestionEndpointFor(file.name) || state.status === "uploading"}>
          {state.status === "uploading" ? "Extracting…" : "Upload and extract"}
        </button>
      </form>

      {state.status === "uploading" && <p role="status">Uploading and processing the document…</p>}
      {state.status === "error" && <p className="error" role="alert">{state.message}</p>}

      {state.status === "success" && (
        <section className={styles.output}>
          <section className={styles.metadata} aria-labelledby="document-metadata">
            <h2 id="document-metadata">Raw and normalized document</h2>
            <dl>
              <div><dt>Filename</dt><dd>{state.result.filename}</dd></div>
              <div><dt>Source type</dt><dd>{state.result.source_type}</dd></div>
              <div><dt>Physical pages / slides</dt><dd>{state.result.page_count}</dd></div>
              <div><dt>Images</dt><dd>{state.result.images.length}</dd></div>
              <div><dt>Markdown characters</dt><dd>{state.result.extracted_character_count.toLocaleString()}</dd></div>
            </dl>
            <pre>{JSON.stringify(state.result.extraction_metadata, null, 2)}</pre>
            <h3>Normalization summary</h3>
            <dl className={styles.counters}>
              {Object.entries(state.result.normalized.normalization_metadata.counters).map(([name, count]) => (
                <div key={name}><dt>{name.replace(/_/g, " ")}</dt><dd>{count}</dd></div>
              ))}
            </dl>
            {state.result.normalized.normalization_metadata.suppressed_artifacts.length > 0 && (
              <details>
                <summary>Suppressed page furniture</summary>
                <ul>
                  {state.result.normalized.normalization_metadata.suppressed_artifacts.map((artifact) => (
                    <li key={artifact.id}><strong>{artifact.type}</strong>: {artifact.text} · pages {artifact.page_numbers.join(", ")}</li>
                  ))}
                </ul>
              </details>
            )}
            {state.result.normalized.normalization_metadata.unresolved_artifacts.length > 0 && (
              <details>
                <summary>Unresolved suspicious artifacts</summary>
                <ul>
                  {state.result.normalized.normalization_metadata.unresolved_artifacts.map((artifact) => (
                    <li key={artifact.id}><strong>{artifact.type}</strong> on page {artifact.page_number ?? "unknown"}: {artifact.text} — {artifact.reason}</li>
                  ))}
                </ul>
              </details>
            )}
          </section>

          <section aria-labelledby="physical-pages">
            <h2 id="physical-pages">Physical pages / slides</h2>
            <div className={styles.pages}>
              {state.result.pages.map((page, pageIndex) => {
                const images = state.result.images.filter((image) => sameLocation(image.location, page.location))
                const normalizedPage = state.result.normalized.pages[pageIndex]
                const pageEvents = state.result.normalized.normalization_metadata.events.filter((event) =>
                  page.blocks.some((block) => event.raw_block_ids.includes(block.id))
                )
                return (
                  <details className={styles.pageCard} key={page.location ? formatLocation(page.location) : pageIndex} open={pageIndex === 0}>
                    <summary>{pageSummaryLabel(page)} · {page.blocks.length} blocks · {images.length} images · location {formatLocation(page.location)}</summary>
                    {page.extraction_errors.map((error) => <p className="error" key={error}>{error}</p>)}
                    <div className={styles.comparison}>
                      <section>
                        <h3>Raw</h3>
                        <pre className={styles.rawText}>{page.text || "(no text extracted)"}</pre>
                        <h4>Raw blocks</h4>
                        <ol className={styles.blocks}>
                          {page.blocks.map((block) => (
                            <li key={block.id}>
                              <code>#{block.reading_order} · {block.type} · {block.id} · bbox {formatBbox(block.bbox)} · location {formatLocation(block.location)}</code>
                              {block.text !== null && <pre>{block.text || "(empty text block)"}</pre>}
                              {block.image_id && <span>Image: {block.image_id}</span>}
                            </li>
                          ))}
                        </ol>
                      </section>
                      <section>
                        <h3>Normalized</h3>
                        <pre className={styles.rawText}>{normalizedPage?.text || "(no normalized text)"}</pre>
                        <h4>Normalized blocks</h4>
                        <ol className={styles.blocks}>
                          {normalizedPage?.blocks.map((block) => (
                            <li key={block.id}>
                              <code>{block.type} · pages {block.source.page_start ?? "—"}–{block.source.page_end ?? "—"}</code>
                              <span>Raw IDs: {block.source.raw_block_ids.join(", ")}</span>
                              <span>Source bboxes: {block.source.bboxes.map(formatBbox).join("; ") || "unavailable"}</span>
                              <span>Source locations: {block.source.locations.map(formatLocation).join("; ") || "unavailable"}</span>
                              {block.text !== null && <pre>{block.text || "(empty normalized block)"}</pre>}
                            </li>
                          ))}
                        </ol>
                      </section>
                    </div>
                    {(pageEvents.length > 0 || normalizedPage?.suppressed_artifact_ids.length) && (
                      <details className={styles.pageAudit}>
                        <summary>Page transformations</summary>
                        <ul>
                          {normalizedPage?.suppressed_artifact_ids.map((id) => <li key={id}>Suppressed: {id}</li>)}
                          {pageEvents.map((event) => (
                            <li key={event.id}>{event.stage}: {event.description} · raw blocks {event.raw_block_ids.join(", ")}</li>
                          ))}
                        </ul>
                      </details>
                    )}
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
