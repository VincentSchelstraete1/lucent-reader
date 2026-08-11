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
