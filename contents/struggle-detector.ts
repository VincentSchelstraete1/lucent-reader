import { logEvent, downloadSessionLog } from "../lib/session-log"
import { getInstallId } from "../lib/install-id"
import {
  DEFAULT_GRADE_LEVEL,
  MAX_QUIZ_QUESTIONS,
  VALID_GRADE_LEVELS,
  applyQuizAnswer,
  finalizeQuizResult,
  getTargetGradeLevel,
  getTierLabel,
  isQuizConfident,
  pickPassageForTier,
  setTargetGradeLevel,
  startQuizState,
  type AssessmentPassage,
  type AssessmentResponse,
  type QuizState
} from "../lib/reading-level"
import {
  DEFAULT_TEXT_LENGTH,
  TEXT_LENGTH_OPTIONS,
  getTargetLength,
  setTargetLength,
  type TextLength
} from "../lib/text-length"

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
      max-width: 32px;
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
      transition: max-width 200ms ease, border-radius 200ms ease, justify-content 0ms 200ms;
      z-index: 999999;
    }
   .arw-badge:hover,
    .arw-badge.arw-expanded {
      width: auto;
      max-width: 400px;
      border-radius: 20px;
      justify-content: flex-start;
      padding: 0 12px 0 8px;
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
      max-width: 350px;
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

// The target reading level for simplification. Defaults to
// DEFAULT_GRADE_LEVEL until the stored value loads (see init() at the
// bottom of this file), then reflects whatever the options-page
// assessment or the manual dropdown last set - both write to the same
// chrome.storage.local key via lib/reading-level.ts, so this stays in
// sync with the options page across page loads.
let targetGradeLevel = DEFAULT_GRADE_LEVEL

// Same idea as targetGradeLevel above, but for output length. Loaded from
// storage in init() and kept in sync with the "Text Length" dropdown.
let targetLength: TextLength = DEFAULT_TEXT_LENGTH

// Reference to the menu's grade-level <select>, set once injectMenu()
// builds it. The quiz modal needs this so that finishing the quiz updates
// the dropdown's displayed value immediately, without the two drifting
// out of sync until the next page load.
let gradeLevelSelectEl: HTMLSelectElement | null = null

const ICONS = {
  idle: `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 2l1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5L12 2z"/><path d="M19 14l.75 2.25L22 17l-2.25.75L19 20l-.75-2.25L16 17l2.25-.75L19 14z"/></svg>`,
  loading: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-9-9"/></svg>`,
  done: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 9 17 20 6"/></svg>`,
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

  const simplified = await simplifyText(originalText, targetGradeLevel, targetLength)

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

async function simplifyText(
  text: string,
  targetLevel: number,
  length: TextLength
): Promise<string> {
  const installId = await getInstallId()

  const response = await fetch("http://localhost:8000/simplify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      target_grade_level: targetLevel,
      target_length: length,
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
    targetGradeLevel,
    targetLength
  })

  styleBadge("loading")

  try {
    await simplifyParagraph(paragraph)
    styleBadge("done")
    logEvent("simplify_done", {
      textPreview: (paragraph.textContent || "").slice(0, 60),
      targetGradeLevel,
      targetLength
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
    logEvent("simplify_all_click", { targetGradeLevel, targetLength })
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
  gradeLevelRow.style.gap = "12px"
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

  VALID_GRADE_LEVELS.forEach((level) => {
    const option = document.createElement("option")
    option.value = String(level)
    option.textContent = getTierLabel(level)
    if (level === targetGradeLevel) option.selected = true
    gradeLevelSelect.appendChild(option)
  })

  gradeLevelSelect.addEventListener("change", () => {
    targetGradeLevel = Number(gradeLevelSelect.value)
    setTargetGradeLevel(targetGradeLevel)
    logEvent("target_grade_level_changed", { targetGradeLevel })
  })

  gradeLevelSelectEl = gradeLevelSelect

  gradeLevelRow.appendChild(gradeLevelLabel)
  gradeLevelRow.appendChild(gradeLevelSelect)

  // ---- New: text length selector ----
  const textLengthRow = document.createElement("div")
  textLengthRow.style.display = "flex"
  textLengthRow.style.alignItems = "center"
  textLengthRow.style.justifyContent = "space-between"
  textLengthRow.style.gap = "12px"
  textLengthRow.style.padding = "4px 2px"

  const textLengthLabel = document.createElement("span")
  textLengthLabel.textContent = "Text Length"
  textLengthLabel.style.fontSize = "14px"
  textLengthLabel.style.color = tokens.readingText

  const textLengthSelect = document.createElement("select")
  textLengthSelect.style.padding = "6px 10px"
  textLengthSelect.style.borderRadius = "20px"
  textLengthSelect.style.border = `1px solid ${tokens.captionText}`
  textLengthSelect.style.fontSize = "12px"
  textLengthSelect.style.cursor = "pointer"
  textLengthSelect.style.backgroundColor = "#FFFFFF"
  textLengthSelect.style.color = tokens.readingText

  TEXT_LENGTH_OPTIONS.forEach(({ value, label }) => {
    const option = document.createElement("option")
    option.value = value
    option.textContent = label
    if (value === targetLength) option.selected = true
    textLengthSelect.appendChild(option)
  })

  textLengthSelect.addEventListener("change", () => {
    targetLength = textLengthSelect.value as TextLength
    setTargetLength(targetLength)
    logEvent("target_length_changed", { targetLength })
  })

  textLengthRow.appendChild(textLengthLabel)
  textLengthRow.appendChild(textLengthSelect)

  // ---- New: reading level quiz link ----
  const quizBtn = document.createElement("button")
  quizBtn.textContent = "Take Reading Level Quiz"
  quizBtn.style.padding = "10px 14px"
  quizBtn.style.borderRadius = "20px"
  quizBtn.style.border = `1px solid ${tokens.captionText}`
  quizBtn.style.backgroundColor = "#FFFFFF"
  quizBtn.style.color = tokens.readingText
  quizBtn.style.fontSize = "14px"
  quizBtn.style.cursor = "pointer"
  quizBtn.style.textAlign = "left"

  quizBtn.addEventListener("click", () => {
    // Close the menu panel first so it isn't sitting behind the modal
    // backdrop while the quiz is open.
    panel.style.display = "none"
    openQuizModal()
  })

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
  panel.appendChild(quizBtn)
  panel.appendChild(gradeLevelRow)
  panel.appendChild(textLengthRow)
  panel.appendChild(exportBtn)

  menuButton.addEventListener("click", () => {
    panel.style.display = panel.style.display === "none" ? "flex" : "none"
  })

  document.body.appendChild(menuButton)
  document.body.appendChild(panel)
}

// ---- Reading Level Quiz modal ----
//
// An in-page wrapper around the same assessment used by options.tsx.
// The scoring logic, the passages, and the storage read/write all live
// in lib/reading-level.ts and are reused as-is here - this section only
// builds the modal DOM and re-renders it as the user answers.

let quizState: QuizState = startQuizState()
let quizQuestionCount = 0
let quizCurrentPassage: AssessmentPassage | null = null
let quizContentEl: HTMLDivElement | null = null
let quizBackdropEl: HTMLDivElement | null = null

const QUIZ_ANSWER_OPTIONS: { value: AssessmentResponse; label: string }[] = [
  { value: "too_easy", label: "Too easy" },
  { value: "just_right", label: "Just right" },
  { value: "too_hard", label: "Too hard" }
]

function injectQuizStyles() {
  const style = document.createElement("style")
  style.textContent = `
    .arw-quiz-answer-btn:hover {
      background-color: ${tokens.accentTeal};
      color: #FFFFFF;
      border-color: ${tokens.accentTeal};
    }
    .arw-quiz-close:hover {
      background-color: rgba(0, 0, 0, 0.06);
    }
  `
  document.head.appendChild(style)
}

function syncGradeLevelDropdown(level: number) {
  if (!gradeLevelSelectEl) return
  gradeLevelSelectEl.value = String(level)
}

function renderQuizStep() {
  if (!quizContentEl || !quizCurrentPassage) return
  quizContentEl.innerHTML = ""

  const progress = document.createElement("p")
  progress.textContent = `Question ${quizQuestionCount + 1} (up to ${MAX_QUIZ_QUESTIONS})`
  progress.style.fontSize = "13px"
  progress.style.color = tokens.captionText
  progress.style.marginBottom = "10px"

  const passageBox = document.createElement("div")
  passageBox.textContent = quizCurrentPassage.text
  passageBox.style.backgroundColor = "#FFFFFF"
  passageBox.style.border = `1px solid ${tokens.captionText}`
  passageBox.style.borderRadius = "12px"
  passageBox.style.padding = "20px"
  passageBox.style.fontSize = "16px"
  passageBox.style.lineHeight = "1.7"
  passageBox.style.marginBottom = "20px"

  const answerRow = document.createElement("div")
  answerRow.style.display = "flex"
  answerRow.style.gap = "10px"

  QUIZ_ANSWER_OPTIONS.forEach(({ value, label }) => {
    const btn = document.createElement("button")
    btn.textContent = label
    btn.className = "arw-quiz-answer-btn"
    btn.style.flex = "1"
    btn.style.padding = "10px 12px"
    btn.style.borderRadius = "20px"
    btn.style.border = `1px solid ${tokens.captionText}`
    btn.style.backgroundColor = "#FFFFFF"
    btn.style.color = tokens.readingText
    btn.style.fontSize = "13px"
    btn.style.cursor = "pointer"
    btn.addEventListener("click", () => handleQuizAnswer(value))
    answerRow.appendChild(btn)
  })

  quizContentEl.appendChild(progress)
  quizContentEl.appendChild(passageBox)
  quizContentEl.appendChild(answerRow)
}

function renderQuizResult(level: number) {
  if (!quizContentEl) return
  quizContentEl.innerHTML = ""

  const resultBox = document.createElement("div")
  resultBox.innerHTML = `Target reading level set to <strong>${getTierLabel(level)}</strong>.`
  resultBox.style.backgroundColor = tokens.badgeDoneBg
  resultBox.style.color = tokens.badgeDoneText
  resultBox.style.borderRadius = "12px"
  resultBox.style.padding = "20px"
  resultBox.style.fontSize = "15px"
  resultBox.style.marginBottom = "16px"

  const retakeBtn = document.createElement("button")
  retakeBtn.textContent = "Take Again"
  retakeBtn.style.padding = "10px 20px"
  retakeBtn.style.borderRadius = "20px"
  retakeBtn.style.border = `1px solid ${tokens.captionText}`
  retakeBtn.style.backgroundColor = "#FFFFFF"
  retakeBtn.style.color = tokens.readingText
  retakeBtn.style.fontSize = "14px"
  retakeBtn.style.cursor = "pointer"
  retakeBtn.addEventListener("click", startQuiz)

  quizContentEl.appendChild(resultBox)
  quizContentEl.appendChild(retakeBtn)
}

// Applies one answer via the shared adaptive engine in lib/reading-level.ts,
// then either asks the next (narrower) question or - once the engine
// reports it's confident, or we've hit the hard cap - finalizes and shows
// the result. All the branching/confidence logic lives in the lib module;
// this only decides what to render next.
async function handleQuizAnswer(response: AssessmentResponse) {
  if (!quizCurrentPassage) return

  const nextState = applyQuizAnswer(quizState, quizCurrentPassage, response)
  const nextCount = quizQuestionCount + 1

  if (nextCount >= MAX_QUIZ_QUESTIONS || isQuizConfident(nextState)) {
    const level = finalizeQuizResult(nextState)
    await setTargetGradeLevel(level)
    targetGradeLevel = level
    syncGradeLevelDropdown(level)
    logEvent("quiz_completed", { targetGradeLevel: level, questionCount: nextCount })
    quizState = nextState
    renderQuizResult(level)
    return
  }

  quizState = nextState
  quizQuestionCount = nextCount
  quizCurrentPassage = pickPassageForTier(quizState.tierIndex, quizState.usedPassageTexts)
  renderQuizStep()
}

function startQuiz() {
  quizState = startQuizState()
  quizQuestionCount = 0
  quizCurrentPassage = pickPassageForTier(quizState.tierIndex, quizState.usedPassageTexts)
  renderQuizStep()
}

function openQuizModal() {
  if (!quizBackdropEl) return
  logEvent("quiz_opened", {})
  startQuiz()
  quizBackdropEl.style.display = "flex"
}

function closeQuizModal() {
  if (!quizBackdropEl) return
  quizBackdropEl.style.display = "none"
}

function injectQuizModal() {
  injectQuizStyles()

  const backdrop = document.createElement("div")
  backdrop.style.position = "fixed"
  backdrop.style.top = "0"
  backdrop.style.left = "0"
  backdrop.style.right = "0"
  backdrop.style.bottom = "0"
  backdrop.style.backgroundColor = "rgba(0,0,0,0.5)"
  backdrop.style.zIndex = "1000000"
  backdrop.style.display = "none"
  backdrop.style.alignItems = "center"
  backdrop.style.justifyContent = "center"

  // Closes only when the backdrop itself is clicked, not clicks that
  // bubble up from inside the modal - the modal's own click handler
  // below stops that propagation.
  backdrop.addEventListener("click", () => closeQuizModal())

  const modal = document.createElement("div")
  modal.style.backgroundColor = tokens.readingBg
  modal.style.borderRadius = "16px"
  modal.style.padding = "24px"
  modal.style.maxWidth = "480px"
  modal.style.width = "90%"
  modal.style.maxHeight = "80vh"
  modal.style.overflowY = "auto"
  modal.style.boxShadow = "0 8px 32px rgba(0,0,0,0.3)"
  modal.style.fontFamily = "Inter, sans-serif"
  modal.addEventListener("click", (e) => e.stopPropagation())

  const header = document.createElement("div")
  header.style.display = "flex"
  header.style.alignItems = "center"
  header.style.justifyContent = "space-between"
  header.style.marginBottom = "16px"

  const title = document.createElement("h2")
  title.textContent = "Reading Level Quiz"
  title.style.fontSize = "18px"
  title.style.color = tokens.readingText
  title.style.margin = "0"

  const closeBtn = document.createElement("button")
  closeBtn.textContent = "×"
  closeBtn.className = "arw-quiz-close"
  closeBtn.setAttribute("aria-label", "Close")
  closeBtn.style.width = "28px"
  closeBtn.style.height = "28px"
  closeBtn.style.borderRadius = "50%"
  closeBtn.style.border = "none"
  closeBtn.style.backgroundColor = "transparent"
  closeBtn.style.color = tokens.readingText
  closeBtn.style.fontSize = "18px"
  closeBtn.style.lineHeight = "1"
  closeBtn.style.cursor = "pointer"
  closeBtn.addEventListener("click", closeQuizModal)

  header.appendChild(title)
  header.appendChild(closeBtn)

  const content = document.createElement("div")

  modal.appendChild(header)
  modal.appendChild(content)
  backdrop.appendChild(modal)
  document.body.appendChild(backdrop)

  quizBackdropEl = backdrop
  quizContentEl = content
}

// Loads the stored grade level and text length (set by the options-page
// assessment, the in-page quiz, or a prior dropdown change) before
// building the menu, so both dropdowns' initial selections are correct
// instead of always starting at the defaults.
async function init() {
  targetGradeLevel = await getTargetGradeLevel()
  targetLength = await getTargetLength()
  loadReadingFont()
  injectBadgeStyles()
  injectMenu()
  injectQuizModal()
}

init()