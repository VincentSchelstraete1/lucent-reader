import { logEvent } from "../lib/session-log"

export const config = {
  matches: ["https://en.wikipedia.org/*"]
}

let lastRun = 0
const THROTTLE_MS = 150

function handler(event) {
  const now = Date.now()
  if (now - lastRun < THROTTLE_MS) return
  lastRun = now

  logEvent("mouse_move", { x: event.clientX, y: event.clientY })
}

document.addEventListener("mousemove", handler)