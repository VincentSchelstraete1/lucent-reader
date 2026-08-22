import { BACKEND_URL } from "./lib/config"
import {
  SIMPLIFY_MESSAGE_TYPE,
  type SimplifyMessage,
  type SimplifyResponse
} from "./lib/messages"
import {
  EXPLAIN_MESSAGE_TYPE,
  type ExplainMessage,
  type ExplainResponse
} from "./lib/messages"
import {
  ENSURE_DOCUMENT_MESSAGE_TYPE,
  type EnsureDocumentMessage,
  type EnsureDocumentResponse,
  SAVE_NOTE_MESSAGE_TYPE,
  type SaveNoteMessage,
  type SaveNoteResponse
} from "./lib/messages"


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
  const response = await fetch(`${BACKEND_URL}/explain`, { //TODO: wire up in backend 
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
  const response = await fetch(`${BACKEND_URL}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: message.title,
      content: message.content,
      content_type: message.contentType,
      source_url: message.sourceUrl,
      document_id: message.documentId ?? null
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

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
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
  else {
    return false
  }
  
  return true // keep the message channel open for the async sendResponse
})
