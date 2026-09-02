// Single place the backend's base URL is defined, mirroring lib/config.ts
// in the Chrome extension - one line to change instead of scattering
// backend URLs through components.
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
let csrfToken: string | null = null
export function setCsrfToken(token: string | null) { csrfToken = token }

export type Source = {
  id: number
  type: string
  url: string | null
  created_at: string
}

export type Document = {
  id: number
  source_id: number
  title: string
  content: string
  created_at: string
  updated_at: string
}

export type Note = {
  id: number
  title: string
  content: string
  source_passage: string | null
  content_type: string
  source_url: string | null
  document_id: number | null
  created_at: string
  updated_at: string
}

export type NoteSection = {
  heading: string
  content: string
}

export type GeneratedNote = {
  title: string
  summary: string
  key_points: string[]
  concepts: string[]
  sections: NoteSection[]
}

export type QuizQuestion = {
  question: string
  choices: string[]
  correct_index: number
  explanation: string
}

export type Quiz = {
  id: number
  document_id: number
  title: string
  questions: QuizQuestion[]
  created_at: string
}

export type QuizAttempt = {
  id: number
  quiz_id: number
  score: number
  total: number
  created_at: string
}

export class ApiError extends Error {
  status: number
  code: string | null
  constructor(path: string, status: number, message?: string, code?: string) {
    super(message || `${path} failed: ${status}`)
    this.status = status
    this.code = code ?? null
  }
}

async function apiError(path: string, response: Response): Promise<ApiError> {
  try {
    const payload = await response.json() as { detail?: string | { code?: string; message?: string } }
    if (typeof payload.detail === "string") return new ApiError(path, response.status, payload.detail)
    if (payload.detail?.message) return new ApiError(path, response.status, payload.detail.message, payload.detail.code)
  } catch {
    // Some existing endpoints intentionally return no JSON error body.
  }
  return new ApiError(path, response.status)
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { credentials: "include" })
  if (!response.ok) {
    throw await apiError(path, response)
  }
  return response.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}) },
    body: body ? JSON.stringify(body) : undefined
  })
  if (!response.ok) {
    throw await apiError(path, response)
  }
  return response.json()
}

async function postForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
    body
  })
  if (!response.ok) throw await apiError(path, response)
  return response.json()
}

// Format-neutral provenance pointer, mirroring backend SourceLocation.
// kind="page" (PDF): index is the physical page number.
// kind="slide" (PPTX): index is the slide number - never page_number, which
// stays a PDF-only legacy field so "page" never silently means "slide".
// kind="document" (DOCX): index is null; sequence_id identifies position
// within the document's ordered structure (DOCX has no physical pages).
export type SourceLocation = {
  kind: "page" | "slide" | "document"
  index: number | null
  sequence_id: string | null
}

export type RawContentBlock = {
  id: string
  page_number: number | null
  type: "text" | "image" | "table" | "unknown"
  text: string | null
  bbox: [number, number, number, number] | null
  reading_order: number
  image_id: string | null
  location: SourceLocation | null
}

export type RawImage = {
  id: string
  page_number: number | null
  bbox: [number, number, number, number] | null
  width: number | null
  height: number | null
  mime_type: string | null
  caption: string | null
  asset_reference: string
  location: SourceLocation | null
}

export type RawPage = {
  page_number: number | null
  text: string
  blocks: RawContentBlock[]
  extraction_errors: string[]
  location: SourceLocation | null
}

export type SourceReference = {
  page_start: number | null
  page_end: number | null
  raw_block_ids: string[]
  bboxes: [number, number, number, number][]
  locations: SourceLocation[]
}

export type NormalizedBlock = {
  id: string
  type: "heading" | "paragraph" | "list" | "table" | "caption" | "image" | "unknown"
  text: string | null
  source: SourceReference
  source_image_id: string | null
}

export type NormalizedPage = {
  page_number: number | null
  text: string
  blocks: NormalizedBlock[]
  transformation_ids: string[]
  suppressed_artifact_ids: string[]
  location: SourceLocation | null
}

export type NormalizationEvent = {
  id: string
  stage: string
  page_number: number | null
  raw_block_ids: string[]
  description: string
  before: string | null
  after: string | null
}

export type SuppressedArtifact = {
  id: string
  type: "header" | "footer" | "page_number"
  text: string
  page_numbers: number[]
  raw_block_ids: string[]
}

export type UnresolvedArtifact = {
  id: string
  type: string
  page_number: number | null
  raw_block_ids: string[]
  text: string
  reason: string
}

export type NormalizedDocument = {
  source_type: string
  filename: string
  page_count: number
  pages: NormalizedPage[]
  images: Array<{
    id: string
    source_page: number | null
    source_bbox: [number, number, number, number] | null
    width: number | null
    height: number | null
    mime_type: string | null
    caption: string | null
    asset_reference: string
    source_image_ids: string[]
    location: SourceLocation | null
  }>
  normalization_metadata: {
    version: string
    suppressed_artifacts: SuppressedArtifact[]
    events: NormalizationEvent[]
    unresolved_artifacts: UnresolvedArtifact[]
    counters: Record<string, number>
  }
}

export type DocumentSourceType = "pdf" | "docx" | "pptx"

export type RepresentationType = "plain_text" | "process" | "comparison" | "causal" | "concept_map" | "hierarchy" | "quantitative"

export type RepresentationDecision = {
  learning_block_id: string
  type: RepresentationType
  confidence: number | null
  method: "deterministic" | "fallback_classifier"
  scores: Record<string, number>
  fallback_used: boolean
}

export type LearningBlockType = "section" | "list" | "table" | "figure" | "mixed"

export type LearningBlock = {
  id: string
  block_type: LearningBlockType
  title: string | null
  text: string
  character_count: number
  normalized_block_ids: string[]
  source: SourceReference
  heading_ancestry: string[]
  attached_table_ids: string[]
  attached_image_ids: string[]
  token_count: number | null
  segmentation_method: string
  segmentation_boundary_reason: string
  segmentation_confidence: number | null
  representation: RepresentationDecision
}

export type DocumentIngestionResult = {
  status: "success"
  filename: string
  source_type: DocumentSourceType
  page_count: number
  markdown: string
  extracted_character_count: number
  pages: RawPage[]
  images: RawImage[]
  extraction_metadata: Record<string, string | number | boolean | null>
  normalized: NormalizedDocument
  learning_blocks: LearningBlock[]
}

// Legacy alias kept because it was the original (PDF-only) name for this shape.
export type PdfIngestionResult = DocumentIngestionResult

const INGESTION_ENDPOINT_BY_EXTENSION: Record<string, string> = {
  pdf: "/ingestion/pdf",
  docx: "/ingestion/docx",
  pptx: "/ingestion/pptx"
}

export function ingestionEndpointFor(filename: string): string | null {
  const extension = filename.split(".").pop()?.toLowerCase()
  return extension ? INGESTION_ENDPOINT_BY_EXTENSION[extension] ?? null : null
}

export const api = {
  getSources: () => get<Source[]>("/sources"),
  getSource: (id: number) => get<Source>(`/sources/${id}`),
  getDocuments: () => get<Document[]>("/documents"),
  getDocument: (id: number) => get<Document>(`/documents/${id}`),
  getNotes: () => get<Note[]>("/notes"),
  generateNote: (documentId: number) => post<Note>(`/documents/${documentId}/generate-note`),
  generateQuiz: (documentId: number) => post<Quiz>(`/documents/${documentId}/quizzes`),
  getQuizzesForDocument: (documentId: number) => get<Quiz[]>(`/documents/${documentId}/quizzes`),
  getQuiz: (id: number) => get<Quiz>(`/quizzes/${id}`),
  submitQuizAttempt: (quizId: number, attempt: { score: number; total: number }) =>
    post<QuizAttempt>(`/quizzes/${quizId}/attempts`, attempt),
  ingestPdf: (file: File) => {
    const form = new FormData()
    form.append("file", file)
    return postForm<DocumentIngestionResult>("/ingestion/pdf", form)
  },
  ingestDocument: (file: File) => {
    const endpoint = ingestionEndpointFor(file.name)
    if (!endpoint) return Promise.reject(new Error(`Unsupported file type: ${file.name}`))
    const form = new FormData()
    form.append("file", file)
    return postForm<DocumentIngestionResult>(endpoint, form)
  }
}
