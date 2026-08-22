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
import {
  SUMMARIZE_MESSAGE_TYPE,
  type SummarizeMessage,
  type SummarizeResponse
} from "./lib/messages"
import { OPEN_SIDE_PANEL_MESSAGE_TYPE } from "./lib/messages"
import { USE_POPUP_FALLBACK_STORAGE_KEY, DEFAULT_USE_POPUP_FALLBACK, getUsePopupFallback } from "./lib/side-panel-mode"

// Cached in memory (kept in sync via the onChanged listener below)
// rather than read fresh from chrome.storage.local on every click -
// chrome.sidePanel.open() has a hard requirement that it's called
// *synchronously* within the user-gesture handler, and even a single
// `await chrome.storage.local.get(...)` before it is enough to break
// that chain and make Chrome silently reject the call (confirmed
// directly: this is exactly what made the real side panel stop opening
// in Chrome after usePopupFallback was first added as an always-awaited
// check).
let cachedUsePopupFallback = DEFAULT_USE_POPUP_FALLBACK
getUsePopupFallback().then((v) => {
  cachedUsePopupFallback = v
})
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && USE_POPUP_FALLBACK_STORAGE_KEY in changes) {
    cachedUsePopupFallback = changes[USE_POPUP_FALLBACK_STORAGE_KEY].newValue ?? DEFAULT_USE_POPUP_FALLBACK
  }
})

// Makes the toolbar icon open the side panel on click (mockup item 1)
// instead of a default_popup - there is no more popup.tsx, its content
// moved into sidepanel.tsx's Settings tab.
//
// Deliberately NOT using chrome.sidePanel.setPanelBehavior({
// openPanelOnActionClick: true }) - that's a *declarative* handoff, and
// Chrome's documented contract for it is that chrome.action.onClicked
// then never fires again, because the click is considered "consumed" by
// the side panel behavior. That's true even if the browser's side panel
// implementation is a no-op that doesn't actually show anything (which
// is seemingly the case in Arc: chrome.sidePanel exists and
// setPanelBehavior resolves without error, but nothing visible happens,
// and per that same contract onClicked is still suppressed - so a
// fallback registered separately never got a chance to run, no matter
// how it detected sidePanel's availability).
//
// Handling this ourselves instead: onClicked always fires (nothing ever
// opts into the auto-consuming behavior above), and inside it we
// explicitly call the imperative chrome.sidePanel.open() - which Chrome
// supports calling directly from a user-gesture handler like this one -
// falling back to a plain window/tab if that call fails or doesn't
// exist at all.
// Shared by the toolbar icon (onClicked, below) and the on-page top-right
// toggle (OPEN_SIDE_PANEL_MESSAGE_TYPE handler further down) - same
// open-or-fall-back logic either way, so both entry points stay
// consistent instead of drifting.
// Reuses sidepanel.html as-is (it has no dependency on actually being a
// side panel) rendered in a small popup window instead. Anchored to the
// calling window's own right edge, matching its height, so it looks
// like a docked panel rather than an arbitrary window - plain
// width/height alone weren't enough in Arc (it opened full-size instead
// of the requested dimensions without an explicit left/top).
async function openPopupFallback(windowId: number) {
  try {
    console.log("[Lucent] opening popup window fallback")
    const createOptions: chrome.windows.CreateData = {
      url: chrome.runtime.getURL("sidepanel.html"),
      type: "popup",
      width: 300,
      height: 640
    }

    try {
      const parentWindow = await chrome.windows.get(windowId)
      if (
        parentWindow.left !== undefined &&
        parentWindow.top !== undefined &&
        parentWindow.width !== undefined &&
        parentWindow.height !== undefined
      ) {
        createOptions.left = parentWindow.left + parentWindow.width - createOptions.width!
        createOptions.top = parentWindow.top
        createOptions.height = parentWindow.height
      }
    } catch (err) {
      console.error("[Lucent] couldn't read the parent window's bounds, using defaults", err)
    }

    const win = await chrome.windows.create(createOptions)
    console.log("[Lucent] chrome.windows.create resolved", win)
  } catch (err) {
    console.error("Lucent: popup window fallback failed, opening a tab instead", err)
    chrome.tabs.create({ url: chrome.runtime.getURL("sidepanel.html") }).then(
      (t) => console.log("[Lucent] chrome.tabs.create resolved", t),
      (e) => console.error("[Lucent] chrome.tabs.create ALSO failed", e)
    )
  }
}

// Confirmed directly: chrome.sidePanel.open() resolves with no error in
// Arc even though nothing ever becomes visible there, so a successful
// resolution can't be trusted as proof it actually worked - there's no
// reliable way to detect this automatically, hence cachedUsePopupFallback
// (a manual one-time choice - see lib/side-panel-mode.ts and its toggle
// on the options page) rather than always running both.
//
// NOT async, and chrome.sidePanel.open() is called as the very first
// thing with nothing awaited before it - Chrome requires this call to
// happen synchronously within the user-gesture handler that triggered
// it (the click), and even one `await` beforehand is enough to make
// Chrome silently reject it. That's exactly what broke this the first
// time cachedUsePopupFallback's predecessor was read fresh from
// chrome.storage.local (an inherently async call) before this line.
function openLucentPanel(windowId: number) {
  console.log("[Lucent] openLucentPanel called", {
    windowId,
    hasSidePanel: typeof chrome.sidePanel?.open,
    usePopupFallback: cachedUsePopupFallback
  })

  if (!cachedUsePopupFallback && typeof chrome.sidePanel?.open === "function") {
    chrome.sidePanel.open({ windowId }).then(
      () => console.log("[Lucent] chrome.sidePanel.open() resolved with no error"),
      (err) => {
        console.error("Lucent: sidePanel.open() failed, falling back to a window", err)
        openPopupFallback(windowId)
      }
    )
    return
  }

  openPopupFallback(windowId)
}

chrome.action.onClicked.addListener((tab) => {
  console.log("[Lucent] chrome.action.onClicked fired", tab)
  if (tab.windowId !== undefined) openLucentPanel(tab.windowId)
})

console.log("[Lucent] background service worker loaded, chrome.sidePanel =", typeof chrome.sidePanel)


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
  const response = await fetch(`${BACKEND_URL}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: message.title,
      content: message.content,
      content_type: message.contentType,
      source_url: message.sourceUrl,
      document_id: message.documentId ?? null,
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
    console.log("[Lucent] OPEN_SIDE_PANEL_MESSAGE_TYPE received", sender.tab?.windowId)
    // openLucentPanel needs a window to open into - the sender is the
    // content script's tab, which always has one.
    if (sender.tab?.windowId !== undefined) {
      openLucentPanel(sender.tab.windowId)
    }
    return false
  }
  else {
    return false
  }

  return true // keep the message channel open for the async sendResponse
})
