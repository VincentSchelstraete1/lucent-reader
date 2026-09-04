import type { LearningObject } from "../learning/schema/learningObject"
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
  section_id?: string | null
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
  details: Array<{ location: string; message: string; type: string }>
  diagnostics: GenerationDiagnostics | null
  constructor(path: string, status: number, message?: string, code?: string, details: Array<{ location: string; message: string; type: string }> = [], diagnostics: GenerationDiagnostics | null = null) {
    super(message || `${path} failed: ${status}`)
    this.status = status
    this.code = code ?? null
    this.details = details
    this.diagnostics = diagnostics
  }
}

export type GenerationDiagnostics = { stop_reason?: string | null; input_tokens?: number | null; output_tokens?: number | null; max_tokens?: number | null; parsed?: boolean; truncated?: boolean; top_level_keys?: string[] }

async function apiError(path: string, response: Response): Promise<ApiError> {
  try {
    const payload = await response.json() as { detail?: string | { code?: string; message?: string; validation_errors?: Array<{ location: string; message: string; type: string }>; diagnostics?: GenerationDiagnostics } }
    if (typeof payload.detail === "string") return new ApiError(path, response.status, payload.detail)
    if (payload.detail?.message) return new ApiError(path, response.status, payload.detail.message, payload.detail.code, payload.detail.validation_errors, payload.detail.diagnostics ?? null)
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

export type LearningCanvasResult = { decision: RepresentationDecision; learning_object: LearningObject; teaching_plan: TeachingPlan }

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
  generated_note: GeneratedLearningNote | null
  section_notes?: SectionNote[]
  source_id?: number | null
  document_id?: number | null
  note_id?: number | null
}

export type TeachingPlan = { learningGoal: string; recommendedRepresentation: RepresentationType; finalRepresentation: RepresentationType; rationale: string; coreIdeas: string[]; usefulContext: string[]; omittedNoise: string[]; representationPlan: string[]; contextPacket: Record<string, unknown> | null; override: boolean }
export type GeneratedLearningNote = { sourceDocument: { filename: string; sourceType: string; pageCount: number }; title: string; sections: Array<{ learningBlockId: string; title: string | null; source: Record<string, unknown>; representationDecision: RepresentationDecision; teachingPlan: TeachingPlan | null; learningObject: LearningObject; generationFallback: boolean }> }
export type SectionNote = { id: string; title: string; bigIdea: string; learningGoals: string[]; components: Array<{ kind: string; title: string; text?: string; sourceBlockIds: string[]; learningObject?: LearningObject | null; term?: string | null; definition?: string | null; nodes: Array<Record<string, unknown>>; edges: Array<Record<string, unknown>>; root?: Record<string, unknown> | null; items: Array<Record<string, unknown>>; dimensions: string[]; problem?: string | null; steps: Array<Record<string, unknown>>; result?: string | null; interpretation?: string | null; equation?: string | null; takeaway?: string | null }>; keyTakeaways: string[]; sourceBlockIds: string[]; omittedNoise: string[] }
export type ProgressiveSection = { id: string; title: string | null; learning_block_ids: string[]; status: "pending" | "generating" | "complete" | "failed"; section_note: SectionNote | null; error: string | null }
export type ProgressiveStart = { job_id: string; filename: string; sections: ProgressiveSection[] }
export type ProgressivePoll = { job_id: string; filename: string; status: "processing" | "complete" | "failed"; sections: ProgressiveSection[]; result: DocumentIngestionResult | null }

export type StepThroughMechanism = {
  type: "step_through_mechanism"
  sceneType: "vector_scene" | "sequence_exchange_scene" | "ordered_items_scene"
  title: string
  learningGoal: string
  entities: Array<{ id: string; kind: "item" | "actor" | "vector" | "node" | "quantity"; label: string; description?: string | null }>
  stages: Array<{ title: string; explanation: string; stateChanges: Array<{ entityId: string; change: string; why?: string | null }>; equation?: string | null; activeEntityIds: string[]; notice?: string | null; insight?: string | null; visual?: unknown }>
  prediction?: { prompt: string; options: string[]; answer: number; reveal: string } | null
  conclusion: string
}
export type StepThroughFixture = { name: string; source_text: string; source_hash: string; replay_available: boolean }
export type StepThroughMetadata = { fixture_name: string; source_hash: string; mode: "replay" | "live"; fixture_kind: "golden_manual" | "sample_manual" | "recorded_live"; cache_hit: boolean; model_call_count: 0 | 1; model?: string | null; latency_ms: number; input_tokens?: number | null; output_tokens?: number | null; max_tokens?: number | null; stop_reason?: string | null; parsed: boolean; truncated: boolean; validation: "passed" | "failed"; error?: string | null }
export type StepThroughResponse = { mechanism: StepThroughMechanism; metadata: StepThroughMetadata }

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
  getNote: (id: number) => get<Note>(`/notes/${id}`),
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
  },
  startProgressiveDocument: (file: File, depth: "concise" | "balanced" | "detailed" = "balanced") => {
    const form = new FormData(); form.append("file", file)
    return postForm<ProgressiveStart>(`/ingestion/progressive?depth=${depth}`, form)
  },
  pollProgressiveDocument: (jobId: string) => get<ProgressivePoll>(`/ingestion/progressive/${jobId}`),
  routeLearningCanvas: (text: string) => post<LearningCanvasResult>("/routing/representation", { text }),
  getStepThroughFixtures: () => get<StepThroughFixture[]>("/dev/step-through/fixtures"),
  generateStepThrough: (request: { fixture_name: string; source_text: string; mode: "replay" | "live"; save_fixture?: boolean }) => post<StepThroughResponse>("/dev/step-through/generate", request)
}
