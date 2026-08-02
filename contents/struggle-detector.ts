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
      width: 190px;
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
      max-width: 160px;
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

const ICONS = {
  idle: `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 2l1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5L12 2z"/><path d="M19 14l.75 2.25L22 17l-2.25.75L19 20l-.75-2.25L16 17l2.25-.75L19 14z"/></svg>`,
  loading: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-9-9"/></svg>`,
  done: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 9 17 20 6"/></svg>`
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

function showBadgeFor(paragraph: HTMLElement) {
  if (hideTimeoutId) {
    clearTimeout(hideTimeoutId)
    hideTimeoutId = null
  }
  currentParagraph = paragraph
  styleBadge("idle")

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
  el.style.position = "absolute"
  el.style.top = "4px"
  el.style.right = "4px"
  el.style.width = "20px"
  el.style.height = "20px"
  el.style.borderRadius = "50%"
  el.style.border = `1px solid ${tokens.captionText}`
  el.style.backgroundColor = "#FFFFFF"
  el.style.color = tokens.readingText
  el.style.fontSize = "12px"
  el.style.lineHeight = "18px"
  el.style.textAlign = "center"
  el.style.padding = "0"
  el.style.cursor = "pointer"
  el.style.boxShadow = "0 1px 3px rgba(0,0,0,0.15)"
  el.style.zIndex = "999999"
}

function addRevertButton(paragraph: HTMLElement) {
  const revertBtn = document.createElement("button")
  revertBtn.textContent = "↺"
  revertBtn.title = "Revert to original text"
  styleRevertButton(revertBtn)

  revertBtn.addEventListener("click", (e) => {
    e.stopPropagation()
    const original = originalTextByParagraph.get(paragraph)
    if (original !== undefined) {
      paragraph.textContent = original
    }
    paragraph.style.borderLeft = ""
    paragraph.style.paddingLeft = ""
    paragraph.style.position = ""
    originalTextByParagraph.delete(paragraph)
  })

  paragraph.appendChild(revertBtn)
}

async function simplifyParagraph(paragraph: HTMLElement) {
  if (originalTextByParagraph.has(paragraph)) return

  const originalText = paragraph.textContent || ""
  if (!originalText.trim()) return

  const simplified = await fakeSimplify(originalText)

  originalTextByParagraph.set(paragraph, originalText)
  paragraph.textContent = simplified
  paragraph.style.position = "relative"
  paragraph.style.borderLeft = `3px solid ${tokens.accentTeal}`
  paragraph.style.paddingLeft = "10px"

  addRevertButton(paragraph)
}

badge.addEventListener("click", async () => {
  if (!currentParagraph) return
  const paragraph = currentParagraph

  styleBadge("loading")

  await simplifyParagraph(paragraph)

  styleBadge("done")

  hideTimeoutId = window.setTimeout(hideBadge, 2000)
})

async function fakeSimplify(text: string): Promise<string> {
  await new Promise((resolve) => setTimeout(resolve, 1000))
  return "[Simplified] " + text.split(". ")[0] + "."
}

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

// ---- Menu: Simplify Entire Page + Reading Mode toggle ----

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

  panel.appendChild(simplifyAllBtn)
  panel.appendChild(row)

  menuButton.addEventListener("click", () => {
    panel.style.display = panel.style.display === "none" ? "flex" : "none"
  })

  document.body.appendChild(menuButton)
  document.body.appendChild(panel)
}

loadReadingFont()
injectBadgeStyles()
injectMenu()