export type SessionEvent = {
  type: string
  timestamp: number
  data: Record<string, unknown>
}

function getLog(): SessionEvent[] {
  const w = window as any
  if (!w.__arwSessionLog) w.__arwSessionLog = []
  return w.__arwSessionLog
}

export function logEvent(type: string, data: Record<string, unknown>) {
  getLog().push({ type, timestamp: Date.now(), data })
}

export function downloadSessionLog() {
  const log = getLog()
  const blob = new Blob([JSON.stringify(log, null, 2)], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `reading-session-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}