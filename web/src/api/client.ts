// Single place the backend's base URL is defined, mirroring lib/config.ts
// in the Chrome extension - one line to change instead of scattering
// backend URLs through components.
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"

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

class ApiError extends Error {
  status: number
  constructor(path: string, status: number) {
    super(`${path} failed: ${status}`)
    this.status = status
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`)
  if (!response.ok) {
    throw new ApiError(path, response.status)
  }
  return response.json()
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  })
  if (!response.ok) {
    throw new ApiError(path, response.status)
  }
  return response.json()
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
    post<QuizAttempt>(`/quizzes/${quizId}/attempts`, attempt)
}
