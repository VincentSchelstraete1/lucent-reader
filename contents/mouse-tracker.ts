import { logEvent } from "../lib/session-log"
import { isSensitivePage } from "../lib/sensitive-page"

export const config = {
  matches: ["<all_urls>"]
}

let lastRun = 0
const THROTTLE_MS = 150

function handler(event) {
  const now = Date.now()
  if (now - lastRun < THROTTLE_MS) return
  lastRun = now

  logEvent("mouse_move", { x: event.clientX, y: event.clientY })
}

// Unlike struggle-detector.ts, this ran on <all_urls> with no
// readability gate at all - so it was tracking mouse position on every
// site, sensitive pages included, before this check existed.
if (!isSensitivePage()) {
  document.addEventListener("mousemove", handler)
}