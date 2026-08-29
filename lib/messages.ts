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


export const EXPLAIN_MESSAGE_TYPE = "explain" as const

export type ExplainMessage = {
  type: typeof EXPLAIN_MESSAGE_TYPE
  text: string
  context: string
  targetGradeLevel: number
  targetLength: TextLength
  installId: string
}

export type ExplainResponse =
  | { ok: true; explanation: string }
  | { ok: false; error: string }

export const SUMMARIZE_MESSAGE_TYPE = "summarize" as const

export type SummarizeMessage = {
  type: typeof SUMMARIZE_MESSAGE_TYPE
  text: string
  targetGradeLevel: number
  targetLength: TextLength
  installId: string
}

export type SummarizeResponse =
  | { ok: true; summary: string }
  | { ok: false; error: string }


// Saved-note plumbing: a content script first ensures a Document exists
// for the current page (creating its Source + Document on first save,
// see ensureDocumentId in struggle-detector.ts), then saves the actual
// note. Same background-worker-does-the-fetch split as Simplify/Explain
// above, for the same CORS reason.
export const ENSURE_DOCUMENT_MESSAGE_TYPE = "ensure_document" as const

export type EnsureDocumentMessage = {
  type: typeof ENSURE_DOCUMENT_MESSAGE_TYPE
  url: string
  title: string
  content: string
}

export type EnsureDocumentResponse =
  | { ok: true; documentId: number }
  | { ok: false; error: string }

export type SaveContentType = "highlight" | "explanation" | "simplification" | "note" | "summary"

export const SAVE_NOTE_MESSAGE_TYPE = "save_note" as const

export type SaveNoteMessage = {
  type: typeof SAVE_NOTE_MESSAGE_TYPE
  title: string
  content: string
  sourcePassage?: string
  contentType: SaveContentType
  sourceUrl: string
  documentId: number
  tags?: string[]
}

export type SaveNoteResponse =
  | { ok: true }
  | { ok: false; error: string }

// Side panel <-> content script, for the Assist tab's Simplify/Explain/
// Summarize actions to operate on whatever's currently selected on the
// page. Sent with chrome.tabs.sendMessage(tabId, ...) directly to the
// active tab, same as MANUAL_ACTIVATE_MESSAGE_TYPE above - not routed
// through the background worker, since no backend fetch is involved here.
export const GET_SELECTION_MESSAGE_TYPE = "get_selection" as const

export type GetSelectionMessage = {
  type: typeof GET_SELECTION_MESSAGE_TYPE
}

export type GetSelectionResponse =
  | { ok: true; text: string; context: string; pageTitle: string }
  | { ok: false; reason: "no_selection" }

export const REPLACE_SELECTION_MESSAGE_TYPE = "replace_selection" as const

export type ReplaceSelectionMessage = {
  type: typeof REPLACE_SELECTION_MESSAGE_TYPE
  text: string
}

export type ReplaceSelectionResponse =
  | { ok: true }
  | { ok: false; reason: "no_selection" }

// On-page toggle (top-right corner) that opens the side panel - content
// scripts can't call chrome.sidePanel.open() directly (that API isn't
// exposed to content scripts), so this asks the background worker to do
// it for the sender's tab/window instead.
export const OPEN_SIDE_PANEL_MESSAGE_TYPE = "open_side_panel" as const

export type OpenSidePanelMessage = {
  type: typeof OPEN_SIDE_PANEL_MESSAGE_TYPE
}
