// Message contract between content scripts and the background service
// worker for the /simplify call. The actual fetch to the backend has to
// happen in the background worker, not a content script - a content
// script's fetch() reports the Origin header of the page it's injected
// into (e.g. https://en.wikipedia.org), not chrome-extension://<id>, so
// an extension-ID-based CORS allowlist on the backend can never match a
// content-script fetch. A background worker's fetch() runs in the
// extension's own context and correctly reports chrome-extension://<id>
// regardless of which site the content script is running on.
import type { TextLength } from "./text-length"

export const SIMPLIFY_MESSAGE_TYPE = "simplify" as const

export type SimplifyMessage = {
  type: typeof SIMPLIFY_MESSAGE_TYPE
  text: string
  targetGradeLevel: number
  targetLength: TextLength
  installId: string
}

export type SimplifyResponse =
  | { ok: true; simplified: string }
  | { ok: false; error: string }
