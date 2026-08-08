import { logEvent, downloadSessionLog } from "../lib/session-log"
import { getInstallId } from "../lib/install-id"

export const config = {
  matches: ["https://en.wikipedia.org/*"]
}

const STRUGGLE_THRESHOLD_MS = 4000
const activeTimers = new Map<Element, number>()
const flaggedParagraphs = new Set<Element>()
const originalTextByParagraph = new Map<HTMLElement, string>()

const tokens = {
  readingBg: "#F5F1E8",
  readingText: "#2C2C2A",
  accentTeal: "#1D9E75",
  badgeDoneBg: "#EEEDFE",
  badgeDoneText: "#26215C",
  captionText: "#5E5E5B"
}

function loadReadingFont() {
  const link = document.createElement("link")
  link.rel = "stylesheet"
  link.href = "https://fonts.googleapis.com/css2?family=Varela+Round&display=swap"
  document.head.appendChild(link)
}

function injectBadgeStyles() {
  const style = document.createElement("style")
  style.textContent = `
    .arw-badge {
      position: absolute;
      top: 2px;
      left: -40px;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      white-space: nowrap;
      cursor: pointer;
      padding: 0;
      border: 1px solid ${tokens.captionText};
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      transition: width 200ms ease, border-radius 200ms ease, justify-content 0ms 200ms;
      z-index: 999999;
    }
    .arw-badge:hover,
    .arw-badge.arw-expanded {
      width: 230px;
      border-radius: 20px;
      justify-content: flex-start;
      padding-left: 8px;
    }
    .arw-badge .arw-icon {
      flex-shrink: 0;
      font-size: 14px;
      width: 20px;
      text-align: center;
    }
    .arw-badge .arw-label {
      opacity: 0;
      max-width: 0;
      overflow: hidden;
      margin-left: 0;
      font-family: Inter, sans-serif;
      font-size: 13px;
      transition: opacity 150ms ease 80ms, margin-left 150ms ease 80ms, max-width 200ms ease;
    }
    .arw-badge:hover .arw-label,
    .arw-badge.arw-expanded .arw-label {
      opacity: 1;
      max-width: 200px;
      margin-left: 6px;
    }
    @keyframes arw-spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    .arw-icon.arw-spinning svg {
      animation: arw-spin 800ms linear infinite;
    }
  `
  document.head.appendChild(style)
}

const badge = document.createElement("button")
badge.className = "arw-badge"

const badgeIcon = document.createElement("span")
badgeIcon.className = "arw-icon"

const badgeLabel = document.createElement("span")
badgeLabel.className = "arw-label"

badge.appendChild(badgeIcon)
badge.appendChild(badgeLabel)
badge.style.opacity = "0"
badge.style.pointerEvents = "none"
badge.style.transition = "opacity 120ms ease"

let currentParagraph: HTMLElement | null = null
let hideTimeoutId: number | null = null

// The target reading level for simplification. Selectable by the user
// for now - later, this gets set automatically instead of picked
// manually, but everything downstream (the simplify call, the logging)
// stays the same either way.
let targetGradeLevel = 5

const ICONS = {
  idle: `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 2l1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5L12 2z"/><path d="M19 14l.75 2.25L22 17l-2.25.75L19 20l-.75-2.25L16 17l2.25-.75L19 14z"/></svg>`,
  loading: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-9-9"/></svg>`,
  done: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 9 17 20 6"/></svg>`
  error: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
}

function styleBadge(state: "idle" | "loading" | "done") {
  if (state === "idle") {
    badgeIcon.innerHTML = ICONS.idle
    badgeLabel.textContent = "Simplify this paragraph"
    badge.style.backgroundColor = tokens.readingBg
    badge.style.color = tokens.readingText
    badge.classList.remove("arw-expanded")
    badgeIcon.classList.remove("arw-spinning")
  } else if (state === "loading") {
    badgeIcon.innerHTML = ICONS.loading
    badgeLabel.textContent = "Simplifying..."
    badge.style.backgroundColor = tokens.accentTeal
    badge.style.color = "#FFFFFF"
    badge.classList.add("arw-expanded")
    badgeIcon.classList.add("arw-spinning")
  } else if (state === "done") {
    badgeIcon.innerHTML = ICONS.done
    badgeLabel.textContent = "Simplified"
    badge.style.backgroundColor = tokens.badgeDoneBg
    badge.style.color = tokens.badgeDoneText
    badge.classList.add("arw-expanded")
    badgeIcon.classList.remove("arw-spinning")
  }
}

function getTextSpan(paragraph: HTMLElement): HTMLSpanElement {
  let span = paragraph.querySelector(":scope > .arw-text") as HTMLSpanElement | null
  if (!span) {
    const originalText = paragraph.textContent || ""
    span = document.createElement("span")
    span.className = "arw-text"
    span.textContent = originalText
    paragraph.textContent = ""
    paragraph.appendChild(span)
  }
  return span
}

function showBadgeFor(paragraph: HTMLElement) {
  if (hideTimeoutId) {
    clearTimeout(hideTimeoutId)
    hideTimeoutId = null
  }
  currentParagraph = paragraph
  styleBadge("idle")

  getTextSpan(paragraph)
  if (!paragraph.style.position) paragraph.style.position = "relative"
  paragraph.appendChild(badge)

  badge.style.opacity = "1"
  badge.style.pointerEvents = "auto"
}

function hideBadge() {
  badge.style.opacity = "0"
  badge.style.pointerEvents = "none"
  currentParagraph = null
}

function styleRevertButton(el: HTMLElement) {
  el.style.display = "inline-flex"
  el.style.alignItems = "center"
  el.style.justifyContent = "center"
  el.style.width = "18px"
  el.style.height = "18px"
  el.style.marginLeft = "6px"
  el.style.verticalAlign = "middle"
  el.style.borderRadius = "50%"
  el.style.border = `1px solid ${tokens.captionText}`
  el.style.backgroundColor = "#FFFFFF"
  el.style.color = tokens.readingText
  el.style.fontSize = "11px"
  el.style.lineHeight = "1"
  el.style.padding = "0"
  el.style.cursor = "pointer"
  el.style.boxShadow = "0 1px 3px rgba(0,0,0,0.15)"
}

function addRevertButton(paragraph: HTMLElement) {
  const revertBtn = document.createElement("button")
  revertBtn.textContent = "↺"
  revertBtn.title = "Revert to original text"
  styleRevertButton(revertBtn)

  revertBtn.addEventListener("click", (e) => {
    e.stopPropagation()
    logEvent("revert_click", {})
    const original = originalTextByParagraph.get(paragraph)
    const span = paragraph.querySelector(":scope > .arw-text") as HTMLSpanElement | null
    if (original !== undefined && span) {
      span.textContent = original
    }
    paragraph.style.borderLeft = ""
    paragraph.style.paddingLeft = ""
    revertBtn.remove()
    originalTextByParagraph.delete(paragraph)
  })

  const span = paragraph.querySelector(":scope > .arw-text") as HTMLSpanElement | null
  if (span) {
    span.insertAdjacentElement("afterend", revertBtn)
  } else {
    paragraph.appendChild(revertBtn)
  }
}

async function simplifyParagraph(paragraph: HTMLElement) {
  if (originalTextByParagraph.has(paragraph)) return

  const span = getTextSpan(paragraph)
  const originalText = span.textContent || ""
  if (!originalText.trim()) return

  const simplified = await simplifyText(originalText, targetGradeLevel)

  originalTextByParagraph.set(paragraph, originalText)
  span.textContent = simplified
  paragraph.style.position = "relative"
  paragraph.style.borderLeft = `3px solid ${tokens.accentTeal}`
  paragraph.style.paddingLeft = "10px"

  addRevertButton(paragraph)
}

// Takes the target grade level as a parameter now - once this becomes
// a real API call, this same value slots directly into the prompt,
// e.g. "Simplify this to a Grade {targetLevel} reading level."

async function simplifyText(text: string, targetLevel: number): Promise<string> {
  const installId = await getInstallId()
  
  const response = await fetch("http://localhost:8000/simplify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text, 
      target_grade_level: targetLevel,
      install_id: installId
    })
  })


  if (response.status === 429) {
    const errorData = await response.json()
    throw new Error(errorData.detail)
  }

  if (!response.ok) {
    throw new Error("Simplify request failed")
  }

  const data = await response.json()
  return data.simplified

}

badge.addEventListener("click", async () => {
  if (!currentParagraph) return
  const paragraph = currentParagraph

  logEvent("simplify_click", {
    textPreview: (paragraph.textContent || "").slice(0, 60),
    targetGradeLevel
  })

  styleBadge("loading")

  try {
    await simplifyParagraph(paragraph)
    styleBadge("done")
    logEvent("simplify_done", {
      textPreview: (paragraph.textContent || "").slice(0, 60),
      targetGradeLevel
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : "Something went wrong"
    badgeIcon.innerHTML = ICONS.error
    badgeLabel.textContent = message
    badge.style.backgroundColor = "#FBEAEA"
    badge.style.color = "#8A2E2E"
    badge.classList.add("arw-expanded")
    logEvent("simplify_error", {
      textPreview: (paragraph.textContent || "").slice(0, 60),
      error: message
    })
  }

  hideTimeoutId = window.setTimeout(hideBadge, 2000)
})

// ---- Trigger 1: user highlights text themselves ----

let selectionDebounceId: number | null = null

function handleSelectionChange() {
  if (selectionDebounceId) clearTimeout(selectionDebounceId)
  selectionDebounceId = window.setTimeout(() => {
    const selection = window.getSelection()
    if (!selection || selection.toString().trim().length === 0) return

    const anchorNode = selection.anchorNode
    if (!anchorNode) return
    const el = anchorNode.nodeType === Node.TEXT_NODE ? anchorNode.parentElement : (anchorNode as HTMLElement)
    const paragraph = el?.closest("p") as HTMLElement | null

    if (paragraph) showBadgeFor(paragraph)
  }, 150)
}

document.addEventListener("selectionchange", handleSelectionChange)

document.addEventListener("mousedown", (e) => {
  if (!badge.contains(e.target as Node)) hideBadge()
})

// ---- Trigger 2: dwell time (struggle detection) ----

function handleIntersection(entries: IntersectionObserverEntry[]) {
  for (const entry of entries) {
    const paragraph = entry.target as HTMLElement
    if (entry.isIntersecting) {
      const timerId = window.setTimeout(() => {
        if (!flaggedParagraphs.has(paragraph)) {
          flaggedParagraphs.add(paragraph)
          logEvent("dwell_flag", { textPreview: (paragraph.textContent || "").slice(0, 60) })
          showBadgeFor(paragraph)
        }
      }, STRUGGLE_THRESHOLD_MS)
      activeTimers.set(paragraph, timerId)
    } else {
      const timerId = activeTimers.get(paragraph)
      if (timerId) {
        clearTimeout(timerId)
        activeTimers.delete(paragraph)
      }
    }
  }
}

const observer = new IntersectionObserver(handleIntersection, { threshold: 0.5 })
document.querySelectorAll("p").forEach((p) => observer.observe(p))

// ---- Menu: Simplify Entire Page + Reading Mode + Target Grade Level ----

let readingModeOn = false

const READING_CONTAINER_SELECTORS = [
  "html",
  "body",
  "#content",
  "#bodyContent",
  "#mw-content-text",
  ".mw-parser-output",
  "#mw-content-container"
]

function applyReadingMode(on: boolean) {
  READING_CONTAINER_SELECTORS.forEach((selector) => {
    const el = document.querySelector(selector) as HTMLElement | null
    if (el) el.style.backgroundColor = on ? tokens.readingBg : ""
  })

  document.querySelectorAll("p").forEach((p) => {
    const el = p as HTMLElement
    el.style.fontFamily = on ? "'Varela Round', sans-serif" : ""
    el.style.fontSize = on ? "18px" : ""
    el.style.lineHeight = on ? "1.8" : ""
    el.style.color = on ? tokens.readingText : ""
  })
}

function injectMenu() {
  const menuButton = document.createElement("button")
  menuButton.textContent = "Aa"
  menuButton.style.position = "fixed"
  menuButton.style.bottom = "20px"
  menuButton.style.right = "20px"
  menuButton.style.zIndex = "999999"
  menuButton.style.width = "48px"
  menuButton.style.height = "48px"
  menuButton.style.borderRadius = "50%"
  menuButton.style.border = "none"
  menuButton.style.backgroundColor = tokens.readingText
  menuButton.style.color = tokens.readingBg
  menuButton.style.fontFamily = "Inter, sans-serif"
  menuButton.style.fontSize = "16px"
  menuButton.style.cursor = "pointer"
  menuButton.style.boxShadow = "0 2px 8px rgba(0,0,0,0.25)"

  const panel = document.createElement("div")
  panel.style.position = "fixed"
  panel.style.bottom = "76px"
  panel.style.right = "20px"
  panel.style.zIndex = "999999"
  panel.style.backgroundColor = tokens.readingBg
  panel.style.border = `1px solid ${tokens.captionText}`
  panel.style.borderRadius = "12px"
  panel.style.padding = "12px"
  panel.style.display = "none"
  panel.style.flexDirection = "column"
  panel.style.gap = "10px"
  panel.style.boxShadow = "0 4px 16px rgba(0,0,0,0.2)"
  panel.style.minWidth = "220px"
  panel.style.fontFamily = "Inter, sans-serif"

  const simplifyAllBtn = document.createElement("button")
  simplifyAllBtn.textContent = "Simplify Entire Page"
  simplifyAllBtn.style.padding = "10px 14px"
  simplifyAllBtn.style.borderRadius = "20px"
  simplifyAllBtn.style.border = `1px solid ${tokens.captionText}`
  simplifyAllBtn.style.backgroundColor = "#FFFFFF"
  simplifyAllBtn.style.color = tokens.readingText
  simplifyAllBtn.style.fontSize = "14px"
  simplifyAllBtn.style.cursor = "pointer"
  simplifyAllBtn.style.textAlign = "left"

  simplifyAllBtn.addEventListener("click", async () => {
    logEvent("simplify_all_click", { targetGradeLevel })
    simplifyAllBtn.disabled = true
    simplifyAllBtn.textContent = "Simplifying page..."
    simplifyAllBtn.style.backgroundColor = tokens.accentTeal
    simplifyAllBtn.style.color = "#FFFFFF"

    const paragraphs = Array.from(document.querySelectorAll("p")) as HTMLElement[]
    for (const p of paragraphs) {
      await simplifyParagraph(p)
    }

    simplifyAllBtn.disabled = false
    simplifyAllBtn.textContent = "✓ Page Simplified"
    simplifyAllBtn.style.backgroundColor = tokens.badgeDoneBg
    simplifyAllBtn.style.color = tokens.badgeDoneText
  })

  const row = document.createElement("div")
  row.style.display = "flex"
  row.style.alignItems = "center"
  row.style.justifyContent = "space-between"
  row.style.padding = "4px 2px"

  const label = document.createElement("span")
  label.textContent = "Reading Mode"
  label.style.fontSize = "14px"
  label.style.color = tokens.readingText

  const switchBtn = document.createElement("button")
  switchBtn.textContent = "Off"
  switchBtn.style.padding = "6px 12px"
  switchBtn.style.borderRadius = "20px"
  switchBtn.style.border = "none"
  switchBtn.style.fontSize = "12px"
  switchBtn.style.cursor = "pointer"
  switchBtn.style.backgroundColor = tokens.captionText
  switchBtn.style.color = "#FFFFFF"

  switchBtn.addEventListener("click", () => {
    readingModeOn = !readingModeOn
    applyReadingMode(readingModeOn)
    switchBtn.textContent = readingModeOn ? "On" : "Off"
    switchBtn.style.backgroundColor = readingModeOn ? tokens.accentTeal : tokens.captionText
  })

  row.appendChild(label)
  row.appendChild(switchBtn)

  // ---- New: target grade level selector ----
  const gradeLevelRow = document.createElement("div")
  gradeLevelRow.style.display = "flex"
  gradeLevelRow.style.alignItems = "center"
  gradeLevelRow.style.justifyContent = "space-between"
  gradeLevelRow.style.padding = "4px 2px"

  const gradeLevelLabel = document.createElement("span")
  gradeLevelLabel.textContent = "Target Reading Level"
  gradeLevelLabel.style.fontSize = "14px"
  gradeLevelLabel.style.color = tokens.readingText

  const gradeLevelSelect = document.createElement("select")
  gradeLevelSelect.style.padding = "6px 10px"
  gradeLevelSelect.style.borderRadius = "20px"
  gradeLevelSelect.style.border = `1px solid ${tokens.captionText}`
  gradeLevelSelect.style.fontSize = "12px"
  gradeLevelSelect.style.cursor = "pointer"
  gradeLevelSelect.style.backgroundColor = "#FFFFFF"
  gradeLevelSelect.style.color = tokens.readingText

  ;[3, 5, 8, 10].forEach((level) => {
    const option = document.createElement("option")
    option.value = String(level)
    option.textContent = `Grade ${level}`
    if (level === targetGradeLevel) option.selected = true
    gradeLevelSelect.appendChild(option)
  })

  gradeLevelSelect.addEventListener("change", () => {
    targetGradeLevel = Number(gradeLevelSelect.value)
    logEvent("target_grade_level_changed", { targetGradeLevel })
  })

  gradeLevelRow.appendChild(gradeLevelLabel)
  gradeLevelRow.appendChild(gradeLevelSelect)

  const exportBtn = document.createElement("button")
  exportBtn.textContent = "Export Session Log"
  exportBtn.style.padding = "10px 14px"
  exportBtn.style.borderRadius = "20px"
  exportBtn.style.border = `1px solid ${tokens.captionText}`
  exportBtn.style.backgroundColor = "#FFFFFF"
  exportBtn.style.color = tokens.readingText
  exportBtn.style.fontSize = "14px"
  exportBtn.style.cursor = "pointer"
  exportBtn.style.textAlign = "left"

  exportBtn.addEventListener("click", () => {
    downloadSessionLog()
  })

  panel.appendChild(simplifyAllBtn)
  panel.appendChild(row)
  panel.appendChild(gradeLevelRow)
  panel.appendChild(exportBtn)

  menuButton.addEventListener("click", () => {
    panel.style.display = panel.style.display === "none" ? "flex" : "none"
  })

  document.body.appendChild(menuButton)
  document.body.appendChild(panel)
}

loadReadingFont()
injectBadgeStyles()
injectMenu()