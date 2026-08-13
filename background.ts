import { BACKEND_URL } from "./lib/config"
import {
  SIMPLIFY_MESSAGE_TYPE,
  type SimplifyMessage,
  type SimplifyResponse
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
  if (message?.type !== SIMPLIFY_MESSAGE_TYPE) return false

  handleSimplify(message as SimplifyMessage)
    .then(sendResponse)
    .catch((err) =>
      sendResponse({
        ok: false,
        error: err instanceof Error ? err.message : "Something went wrong"
      })
    )

  return true // keep the message channel open for the async sendResponse
})
