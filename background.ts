import { BACKEND_URL } from "./lib/config"
import {
  ENSURE_DOCUMENT_MESSAGE_TYPE,
  EXPLAIN_MESSAGE_TYPE,
  OPEN_SIDE_PANEL_MESSAGE_TYPE,
  SAVE_NOTE_MESSAGE_TYPE,
  SIMPLIFY_MESSAGE_TYPE,
  SUMMARIZE_MESSAGE_TYPE,
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

// Makes the toolbar icon open Lucent's interface on click (mockup item
// 1) instead of a default_popup - there is no more popup.tsx, its
// content moved into sidepanel.tsx's Settings tab. See
// lib/lucent-panel.ts for the native-side-panel-vs-popup-fallback
// decision itself; this is just the entry point.
chrome.action.onClicked.addListener((tab) => {
  if (tab.windowId !== undefined) openLucent(tab.windowId)
})


async function handleSimplify(message: SimplifyMessage): Promise<SimplifyResponse> {
  const response = await fetch(`${BACKEND_URL}/simplify`, {
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
  const response = await fetch(`${BACKEND_URL}/explain`, {
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
  const response = await fetch(`${BACKEND_URL}/summarize`, {
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
  const sourceResponse = await fetch(`${BACKEND_URL}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "website", url: message.url })
  })
  if (!sourceResponse.ok) return { ok: false, error: "Failed to save this page" }
  const source = await sourceResponse.json()

  const documentResponse = await fetch(`${BACKEND_URL}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_id: source.id,
      title: message.title,
      content: message.content
    })
  })
  if (!documentResponse.ok) return { ok: false, error: "Failed to save this page" }
  const document = await documentResponse.json()
  return { ok: true, documentId: document.id }
}

async function handleSaveNote(message: SaveNoteMessage): Promise<SaveNoteResponse> {
  if (!message.documentId) {
    return { ok: false, error: "A saved document is required before saving this result" }
  }

  const response = await fetch(`${BACKEND_URL}/notes`, {
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
    return { ok: false, error: "Save failed" }
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
  if (message?.type === SIMPLIFY_MESSAGE_TYPE){
    handleSimplify(message as SimplifyMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : "Something went wrong"
      })
    )
  }
  else if (message?.type === EXPLAIN_MESSAGE_TYPE){
    handleExplain(message as ExplainMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : "Something went wrong"
      })
    )
  }
  else if (message?.type === ENSURE_DOCUMENT_MESSAGE_TYPE){
    handleEnsureDocument(message as EnsureDocumentMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : "Something went wrong"
      })
    )
  }
  else if (message?.type === SAVE_NOTE_MESSAGE_TYPE){
    handleSaveNote(message as SaveNoteMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : "Something went wrong"
      })
    )
  }
  else if (message?.type === SUMMARIZE_MESSAGE_TYPE){
    handleSummarize(message as SummarizeMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : "Something went wrong"
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
