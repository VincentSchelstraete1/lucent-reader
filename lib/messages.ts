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

// Sent from the popup (chrome.tabs.sendMessage, not the background
// worker) directly to the active tab's content script, when the user
// clicks "Activate on this page" - only relevant when the page didn't
// already auto-activate (auto-activate is off, or the page failed the
// isProbablyReaderable check). The content script still enforces
// isSensitivePage() itself before acting on this - a manual request
// can never override that hard safety gate.
export const MANUAL_ACTIVATE_MESSAGE_TYPE = "manual_activate" as const

export type ManualActivateMessage = {
  type: typeof MANUAL_ACTIVATE_MESSAGE_TYPE
}

export type ManualActivateResponse =
  | { ok: true; alreadyActive: boolean }
  | { ok: false; reason: "sensitive_page" }
