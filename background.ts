import { authenticatedFetch, authStatus, login, logout } from "./lib/extension-auth"
import {
  ENSURE_DOCUMENT_MESSAGE_TYPE,
  EXPLAIN_MESSAGE_TYPE,
  OPEN_SIDE_PANEL_MESSAGE_TYPE,
  SAVE_NOTE_MESSAGE_TYPE,
  SIMPLIFY_MESSAGE_TYPE,
  SUMMARIZE_MESSAGE_TYPE,
  AUTH_STATUS_MESSAGE_TYPE,
  AUTH_LOGIN_MESSAGE_TYPE,
  AUTH_LOGOUT_MESSAGE_TYPE,
  type EnsureDocumentMessage,
  type EnsureDocumentResponse,
  type ExplainMessage,
  type ExplainResponse,
  type SaveNoteMessage,
  type SaveNoteResponse,
  type SimplifyMessage,
  type SimplifyResponse,
  type SummarizeMessage,
  type SummarizeResponse
} from "./lib/messages"
import { openLucent } from "./lib/lucent-panel"

async function apiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json()
    return typeof data.detail === "string" ? data.detail : fallback
  } catch {
    return fallback
  }
}

function requestError(error: unknown): string {
  if (error instanceof TypeError) return "Lucent backend is unreachable"
  return error instanceof Error ? error.message : "Something went wrong"
}

function text(value: unknown, max = 1_000_000): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max
}

function validAiMessage(message: unknown): message is SimplifyMessage | ExplainMessage | SummarizeMessage {
  if (!message || typeof message !== "object") return false
  const value = message as Record<string, unknown>
  return text(value.text) && Number.isInteger(value.targetGradeLevel) && typeof value.installId === "string" &&
    (value.targetLength === "shorter" || value.targetLength === "same" || value.targetLength === "longer") &&
    (value.type !== EXPLAIN_MESSAGE_TYPE || text(value.context))
}

function validEnsureDocument(message: unknown): message is EnsureDocumentMessage {
  if (!message || typeof message !== "object") return false
  const value = message as Record<string, unknown>
  if (!text(value.url, 4096) || !text(value.title, 255) || !text(value.content)) return false
  try { return ["http:", "https:"].includes(new URL(value.url).protocol) } catch { return false }
}

function validSaveNote(message: unknown): message is SaveNoteMessage {
  if (!message || typeof message !== "object") return false
  const value = message as Record<string, unknown>
  let sourceUrlValid = false
  try { sourceUrlValid = text(value.sourceUrl, 4096) && ["http:", "https:"].includes(new URL(value.sourceUrl).protocol) } catch { sourceUrlValid = false }
  return sourceUrlValid && text(value.title, 255) && text(value.content) && Number.isInteger(value.documentId) && Number(value.documentId) > 0 &&
    ["highlight", "explanation", "simplification", "note", "summary"].includes(String(value.contentType)) &&
    (value.sourcePassage === undefined || text(value.sourcePassage))
}

// Makes the toolbar icon open Lucent's interface on click (mockup item
// 1) instead of a default_popup - there is no more popup.tsx, its
// content moved into sidepanel.tsx's Settings tab. See
// lib/lucent-panel.ts for the native-side-panel-vs-popup-fallback
// decision itself; this is just the entry point.
chrome.action.onClicked.addListener((tab) => {
  if (tab.windowId !== undefined) openLucent(tab.windowId)
})


async function handleSimplify(message: SimplifyMessage): Promise<SimplifyResponse> {
  const response = await authenticatedFetch(`/simplify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: message.text,
      target_grade_level: message.targetGradeLevel,
      target_length: message.targetLength,
      install_id: message.installId
    })
  })

  if (response.status === 429) {
    const errorData = await response.json()
    return { ok: false, error: errorData.detail }
  }

  if (!response.ok) {
    return { ok: false, error: "Simplify request failed" }
  }

  const data = await response.json()
  return { ok: true, simplified: data.simplified }
}

async function handleExplain(message: ExplainMessage): Promise<ExplainResponse> {
  const response = await authenticatedFetch(`/explain`, {
    method: "POST",
    headers: {"Content-Type" : "application/json"},
    body: JSON.stringify({
      text: message.text,
      context: message.context, 
      target_grade_level: message.targetGradeLevel,
      target_length: message.targetLength,
      install_id: message.installId
    })
  })

  if (response.status === 429) {
    const errorData = await response.json()
    return { ok: false, error: errorData.detail}
  }

  if (!response.ok){
    return { ok: false, error: "Explanation request failed"}
  }

  const data = await response.json()
  return { ok: true, explanation: data.explanation}
}

async function handleSummarize(message: SummarizeMessage): Promise<SummarizeResponse> {
  const response = await authenticatedFetch(`/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: message.text,
      target_grade_level: message.targetGradeLevel,
      target_length: message.targetLength,
      install_id: message.installId
    })
  })

  if (response.status === 429) {
    const errorData = await response.json()
    return { ok: false, error: errorData.detail }
  }

  if (!response.ok) {
    return { ok: false, error: "Summarize request failed" }
  }

  const data = await response.json()
  return { ok: true, summary: data.summary }
}

async function handleEnsureDocument(message: EnsureDocumentMessage): Promise<EnsureDocumentResponse> {
  const sourceResponse = await authenticatedFetch(`/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "website", url: message.url })
  })
  if (!sourceResponse.ok) {
    return { ok: false, error: await apiError(sourceResponse, "Source creation failed") }
  }
  const source = await sourceResponse.json()

  const documentResponse = await authenticatedFetch(`/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_id: source.id,
      title: message.title,
      content: message.content
    })
  })
  if (!documentResponse.ok) {
    return { ok: false, error: await apiError(documentResponse, "Document creation failed") }
  }
  const document = await documentResponse.json()
  return { ok: true, documentId: document.id }
}

async function handleSaveNote(message: SaveNoteMessage): Promise<SaveNoteResponse> {
  if (!message.documentId) {
    return { ok: false, error: "A saved document is required before saving this result" }
  }

  const response = await authenticatedFetch(`/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: message.title,
      content: message.content,
      source_passage: message.sourcePassage ?? null,
      content_type: message.contentType,
      source_url: message.sourceUrl,
      document_id: message.documentId,
      tags: message.tags ?? null
    })
  })

  if (!response.ok) {
    return { ok: false, error: await apiError(response, "Result save failed") }
  }

  return { ok: true }
}

// Fresh installs start eligible to see the one-time onboarding tooltip
// (contents/struggle-detector.ts shows it the first time the simplify
// badge appears). Updates explicitly mark it already-seen instead of
// leaving the flag unset - unset would read as "not seen yet" and pop
// the tooltip for people who've already been using the extension.
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    chrome.storage.local.set({ hasSeenOnboarding: false })
  } else if (details.reason === "update") {
    chrome.storage.local.set({ hasSeenOnboarding: true })
  }
})

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const privilegedExtensionPage = sender.url?.startsWith(chrome.runtime.getURL("")) ?? false
  if (message?.type === AUTH_STATUS_MESSAGE_TYPE && privilegedExtensionPage) {
    authStatus().then((status) => sendResponse({ ok: true, ...status })).catch((error) => sendResponse({ ok: false, error: requestError(error) }))
    return true
  }
  if (message?.type === AUTH_LOGIN_MESSAGE_TYPE && privilegedExtensionPage) {
    login().then(() => sendResponse({ ok: true, authenticated: true })).catch((error) => sendResponse({ ok: false, error: requestError(error) }))
    return true
  }
  if (message?.type === AUTH_LOGOUT_MESSAGE_TYPE && privilegedExtensionPage) {
    logout().then(() => sendResponse({ ok: true, authenticated: false })).catch((error) => sendResponse({ ok: false, error: requestError(error) }))
    return true
  }
  if (message?.type === SIMPLIFY_MESSAGE_TYPE){
    if (!validAiMessage(message)) { sendResponse({ ok: false, error: "Invalid simplify request" }); return false }
    handleSimplify(message as SimplifyMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: requestError(err)
      })
    )
  }
  else if (message?.type === EXPLAIN_MESSAGE_TYPE){
    if (!validAiMessage(message)) { sendResponse({ ok: false, error: "Invalid explain request" }); return false }
    handleExplain(message as ExplainMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: requestError(err)
      })
    )
  }
  else if (message?.type === ENSURE_DOCUMENT_MESSAGE_TYPE){
    if (!validEnsureDocument(message)) { sendResponse({ ok: false, error: "Invalid document request" }); return false }
    handleEnsureDocument(message as EnsureDocumentMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: requestError(err)
      })
    )
  }
  else if (message?.type === SAVE_NOTE_MESSAGE_TYPE){
    if (!validSaveNote(message)) { sendResponse({ ok: false, error: "Invalid save request" }); return false }
    handleSaveNote(message as SaveNoteMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: requestError(err)
      })
    )
  }
  else if (message?.type === SUMMARIZE_MESSAGE_TYPE){
    if (!validAiMessage(message)) { sendResponse({ ok: false, error: "Invalid summarize request" }); return false }
    handleSummarize(message as SummarizeMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: requestError(err)
      })
    )
  }
  else if (message?.type === OPEN_SIDE_PANEL_MESSAGE_TYPE){
    // openLucent needs a window to open into - the sender is the
    // content script's tab, which always has one.
    if (sender.tab?.windowId !== undefined) {
      openLucent(sender.tab.windowId)
    }
    return false
  }
  else {
    return false
  }

  return true // keep the message channel open for the async sendResponse
})
