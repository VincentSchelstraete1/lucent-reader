import { Readability, isProbablyReaderable } from "@mozilla/readability"

import {
  findContentBlock,
  getContentBlocks,
  rangeMeaningfullyOverlapsBlock
} from "../lib/content-blocks"
import { logEvent, downloadSessionLog } from "../lib/session-log"
import { getInstallId } from "../lib/install-id"
import { isSensitivePage } from "../lib/sensitive-page"
import {
  TEXT_SPACING_OPTIONS,
  TEXT_SPACING_STORAGE_KEY,
  DEFAULT_TEXT_SPACING,
  getTextSpacing,
  setTextSpacing,
  type TextSpacing
} from "../lib/text-spacing"
import {
  FONT_OPTIONS,
  READING_FONT_STORAGE_KEY,
  DEFAULT_READING_FONT,
  getReadingFont,
  setReadingFont,
  type ReadingFont
} from "../lib/reading-font"
import fontOpenDyslexicRegular from "data-base64:../assets/fonts/opendyslexic-400.woff2"
import fontOpenDyslexicBold from "data-base64:../assets/fonts/opendyslexic-700.woff2"
import {
  SIMPLIFY_MESSAGE_TYPE,
  type SimplifyMessage,
  type SimplifyResponse,
  MANUAL_ACTIVATE_MESSAGE_TYPE,
  type ManualActivateResponse
} from "../lib/messages"
import {
  EXPLAIN_MESSAGE_TYPE,
  type ExplainMessage,
  type ExplainResponse
} from "../lib/messages"
import {
  DEFAULT_FONT_OVERRIDE_ENABLED,
  DEFAULT_AUTO_ACTIVATE_ENABLED,
  FONT_OVERRIDE_ENABLED_STORAGE_KEY,
  getFontOverrideEnabled,
  getAutoActivateEnabled
} from "../lib/extension-settings"
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
import { renderSimpleMarkdown } from "../lib/simple-markdown"
import { getHasSeenOnboarding, markOnboardingSeen } from "../lib/onboarding"

export const config = {
  matches: ["<all_urls>"]
}

const STRUGGLE_THRESHOLD_MS = 4000
const activeTimers = new Map<Element, number>()
const flaggedParagraphs = new Set<Element>()

// The paragraph's real original markup (links, bold, italic - everything),
// captured once per paragraph the first time we ever touch it, before any
// mutation of our own (badge, simplified text, etc.) happens. Simplifying
// always re-derives from this, never from an already-simplified copy, so
// re-simplifying after a settings change starts from the true original
// and reverting restores the real HTML, not a flattened text-only copy.
const pristineByParagraph = new Map<HTMLElement, { html: string; text: string }>()
const simplifiedParagraphs = new Set<HTMLElement>()

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
      /* 2147483647 (2^31 - 1) is the actual max z-index a browser honors,
         not just "a big number" - used here instead of 999999 because
         cookie-consent banners (OneTrust and similar) commonly set
         themselves to this same ceiling, and 999999 loses that fight
         outright. Confirmed on PBS NewsHour: its cookie banner rendered
         on top of and swallowed clicks on this badge/the Aa button
         (same z-index tier) when both landed in the same corner. */
      z-index: 2147483647;
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

// Styling for the structured content renderSimpleMarkdown() (see
// lib/simple-markdown.ts) produces inside a simplified paragraph's
// .arw-text container - short paragraphs, bullet lists, bolded key
// terms - instead of one flat block of text.
function injectSimplifiedContentStyles() {
  const style = document.createElement("style")
  style.textContent = `
    .arw-text p {
      margin: 0 0 0.6em;
    }
    .arw-text ul {
      margin: 0 0 0.6em;
      padding-left: 1.3em;
    }
    .arw-text li {
      margin-bottom: 0.3em;
    }
    .arw-text p:last-child,
    .arw-text ul:last-child {
      margin-bottom: 0;
    }
  `
  document.head.appendChild(style)
}

// ---- Page-wide style overrides: text spacing + reading font ----
//
// One shared <style> tag for both, rather than one each - its content
// is the concatenation of whatever each control currently wants, so
// changing one never clobbers the other. "off"/"default" clear their
// own half entirely rather than forcing an explicit "normal" value, so
// the extension leaves the page's own styling completely untouched
// until a control is actually turned on.
let pageStyleEl: HTMLStyleElement | null = null
let spacingCSSRules = ""
let fontCSSRules = ""

function getPageStyleEl(): HTMLStyleElement {
  if (!pageStyleEl) {
    pageStyleEl = document.createElement("style")
    pageStyleEl.id = "arw-page-style"
    document.head.appendChild(pageStyleEl)
  }
  return pageStyleEl
}

function renderPageStyle() {
  getPageStyleEl().textContent = `${spacingCSSRules}\n${fontCSSRules}`
}

function applyTextSpacing(spacing: TextSpacing) {
  if (spacing === "off") {
    spacingCSSRules = ""
    renderPageStyle()
    return
  }

  const option = TEXT_SPACING_OPTIONS.find((o) => o.value === spacing)
  if (!option) return

  spacingCSSRules = `
    body, body * {
      letter-spacing: ${option.letterSpacing} !important;
      word-spacing: ${option.wordSpacing} !important;
      line-height: ${option.lineHeight} !important;
    }
  `
  renderPageStyle()
}

// Google Fonts are loaded on demand, once per font, via the same kind
// of stylesheet <link> loadReadingFont() below already uses for Varela
// Round - just parameterized per-font instead of hardcoded.
const loadedGoogleFonts = new Set<string>()

function loadGoogleFont(googleFontParam: string) {
  if (loadedGoogleFonts.has(googleFontParam)) return
  loadedGoogleFonts.add(googleFontParam)
  const link = document.createElement("link")
  link.rel = "stylesheet"
  link.href = `https://fonts.googleapis.com/css2?family=${googleFontParam}&display=swap`
  document.head.appendChild(link)
}

// Master switch, off by default (see lib/extension-settings.ts) -
// checked first, unconditionally, so turning this off in Settings
// clears any font override regardless of which font is selected in the
// Aa menu. Kept in sync live: the chrome.storage.onChanged listener in
// init() below updates this and re-calls applyReadingFont() whenever
// the Settings toggle changes, so flipping it takes effect immediately
// without a page reload.
let fontOverrideEnabled = DEFAULT_FONT_OVERRIDE_ENABLED

function applyReadingFont(font: ReadingFont) {
  if (!fontOverrideEnabled) {
    fontCSSRules = ""
    renderPageStyle()
    return
  }

  const option = FONT_OPTIONS.find((o) => o.value === font)
  if (!option || option.value === "default") {
    fontCSSRules = ""
    renderPageStyle()
    return
  }

  if (option.strategy === "google" && "googleFontParam" in option) {
    loadGoogleFont(option.googleFontParam)
  }

  // OpenDyslexic isn't on Google Fonts, so it ships inside the
  // extension itself (assets/fonts/) and gets embedded here as a data:
  // URI via the data-base64: imports below - no runtime network
  // request, and not subject to a page's CSP the way an external
  // stylesheet link can be. Only injected into the page's own <style>
  // tag when actually selected, so a page that never turns this on
  // doesn't carry the ~230KB of embedded font data in its CSSOM.
  const fontFaceBlock =
    option.value === "opendyslexic"
      ? `
        @font-face {
          font-family: "OpenDyslexic";
          src: url(${fontOpenDyslexicRegular}) format("woff2");
          font-weight: 400;
          font-style: normal;
        }
        @font-face {
          font-family: "OpenDyslexic";
          src: url(${fontOpenDyslexicBold}) format("woff2");
          font-weight: 700;
          font-style: normal;
        }
      `
      : ""

  fontCSSRules = `
    ${fontFaceBlock}
    body, body * {
      font-family: ${option.cssFontFamily} !important;
    }
  `
  renderPageStyle()
}

const ICONS = {
  idle: `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 2l1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5L12 2z"/><path d="M19 14l.75 2.25L22 17l-2.25.75L19 20l-.75-2.25L16 17l2.25-.75L19 14z"/></svg>`,
  loading: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-9-9"/></svg>`,
  done: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 12 9 17 20 6"/></svg>`,
  error: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  explain: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 4.9.8c0 1.7-2.4 2-2.4 3.7"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`
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

// Second small pill button, shown alongside the Simplify badge whenever
// it's shown (see showBadgeFor/hideBadge) - reuses the same .arw-badge
// styling so it looks like a natural pair, just positioned a bit lower
// (see attachExplainBadgeTo) so the two don't overlap.
const explainBadge = document.createElement("button")
explainBadge.className = "arw-badge"

const explainBadgeIcon = document.createElement("span")
explainBadgeIcon.className = "arw-icon"
explainBadgeIcon.innerHTML = ICONS.explain

const explainBadgeLabel = document.createElement("span")
explainBadgeLabel.className = "arw-label"
explainBadgeLabel.textContent = "Explain"

explainBadge.appendChild(explainBadgeIcon)
explainBadge.appendChild(explainBadgeLabel)
explainBadge.style.opacity = "0"
explainBadge.style.pointerEvents = "none"
explainBadge.style.transition = "opacity 120ms ease"
explainBadge.style.backgroundColor = tokens.readingBg
explainBadge.style.color = tokens.readingText

// Small card that renders whatever performExplain() returns, positioned
// just under the paragraph the Explain badge was clicked on. Left in
// the DOM (display: none) between uses rather than created/destroyed
// each time, same pattern as the badge itself.
const explainCard = document.createElement("div")
explainCard.id = "arw-explain-card"
explainCard.style.position = "absolute"
explainCard.style.display = "none"
explainCard.style.maxWidth = "320px"
explainCard.style.backgroundColor = tokens.readingBg
explainCard.style.color = tokens.readingText
explainCard.style.border = `1px solid ${tokens.captionText}`
explainCard.style.borderRadius = "12px"
explainCard.style.boxShadow = "0 4px 16px rgba(0,0,0,0.18)"
explainCard.style.padding = "12px 14px"
explainCard.style.fontFamily = "Inter, sans-serif"
explainCard.style.fontSize = "13px"
explainCard.style.lineHeight = "1.5"
explainCard.style.zIndex = "2147483647"

const explainCardHeader = document.createElement("div")
explainCardHeader.style.display = "flex"
explainCardHeader.style.alignItems = "center"
explainCardHeader.style.justifyContent = "space-between"
explainCardHeader.style.marginBottom = "6px"
explainCardHeader.style.gap = "12px"

const explainCardTitle = document.createElement("span")
explainCardTitle.textContent = "Explanation"
explainCardTitle.style.fontWeight = "600"
explainCardTitle.style.fontSize = "12px"
explainCardTitle.style.color = tokens.captionText

const explainCardClose = document.createElement("button")
explainCardClose.textContent = "✕"
explainCardClose.title = "Close"
explainCardClose.style.border = "none"
explainCardClose.style.background = "transparent"
explainCardClose.style.color = tokens.captionText
explainCardClose.style.cursor = "pointer"
explainCardClose.style.fontSize = "12px"
explainCardClose.style.padding = "0"
explainCardClose.addEventListener("click", () => hideExplanationCard())

explainCardHeader.appendChild(explainCardTitle)
explainCardHeader.appendChild(explainCardClose)

const explainCardBody = document.createElement("div")

explainCard.appendChild(explainCardHeader)
explainCard.appendChild(explainCardBody)

// The paragraph the currently-open (or most recently opened) explain
// card is anchored to - separate from currentParagraphs, since the
// selection (and so currentParagraphs) can change or clear while the
// card from a previous explanation is still open on screen.
let explainAnchorParagraph: HTMLElement | null = null

// A snapshot of the highlighted text, taken in showBadgeFor at the one
// moment a real (non-empty) selection is confirmed - read there rather
// than at explainBadge's own click time because clicking a button
// outside the selected text can itself collapse the browser selection
// before the click handler runs, so window.getSelection() by then is
// unreliable.
let explainSelectedText = ""

// All paragraphs the current badge applies to - normally just one, but
// a selection spanning multiple paragraphs puts all of them here (see
// handleSelectionChange), so a single click simplifies all of them.
let currentParagraphs: HTMLElement[] | null = null
let currentSelectedText: string | null = null
let surroundingContext: string | null = null
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

// Same idea again, but for the Text Spacing control in the Aa menu.
// Loaded from storage in init(). The menu's click handler updates this,
// applies the spacing immediately (see applyTextSpacing above), and
// persists it - the top-level chrome.storage.onChanged listener further
// down also re-applies it, but that's for other tabs/a later page load,
// not this one.
let currentTextSpacing: TextSpacing = DEFAULT_TEXT_SPACING

// Same idea again, but for the Reading Font control in the Aa menu.
let currentReadingFont: ReadingFont = DEFAULT_READING_FONT

// Whether the first-run onboarding tooltip has already been shown.
// Defaults to true (don't show) until init() loads the real stored
// value - a fresh install explicitly starts this false in
// chrome.storage.local (see background.ts's onInstalled listener), so
// only a genuinely new install ever sees maybeShowOnboardingTooltip()
// actually show anything.
let hasSeenOnboarding = true

// Reference to the menu's grade-level <select>, set once injectMenu()
// builds it. The quiz modal needs this so that finishing the quiz updates
// the dropdown's displayed value immediately, without the two drifting
// out of sync until the next page load.
let gradeLevelSelectEl: HTMLSelectElement | null = null

// count > 1 means the current selection spans multiple paragraphs - the
// label says so explicitly ("Simplify 3 paragraphs") rather than firing
// off that many API calls from a click that looked like it would only
// affect one paragraph.
function styleBadge(state: "idle" | "loading" | "done", count = 1) {
  if (state === "idle") {
    badgeIcon.innerHTML = ICONS.idle
    badgeLabel.textContent = count > 1 ? `Simplify ${count} paragraphs` : "Simplify this paragraph"
    badge.style.backgroundColor = tokens.readingBg
    badge.style.color = tokens.readingText
    badge.classList.remove("arw-expanded")
    badgeIcon.classList.remove("arw-spinning")
  } else if (state === "loading") {
    badgeIcon.innerHTML = ICONS.loading
    badgeLabel.textContent = count > 1 ? `Simplifying ${count} paragraphs...` : "Simplifying..."
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

// Captures the paragraph's real, untouched markup exactly once - the
// very first time we ever see it, before showing a badge or simplifying
// ever mutates anything. Safe to call repeatedly; only the first call
// per paragraph does anything.
//
// Reads directly from the live paragraph - safe because the shared
// badge is never a child of any paragraph (see attachBadgeTo below), so
// there's no risk of its own label text ("Simplify 4 paragraphs" etc.)
// ever getting baked into what this treats as "the real original
// content."
function capturePristine(paragraph: HTMLElement) {
  if (!pristineByParagraph.has(paragraph)) {
    pristineByParagraph.set(paragraph, {
      html: paragraph.innerHTML,
      text: paragraph.textContent || ""
    })
  }
}

// Positions the shared badge over a paragraph without ever becoming a
// child of it (or touching its CSS position at all) - deliberately.
// This used to append the badge into the paragraph and give the
// paragraph position: relative so the badge's position: absolute
// resolved against it. Confirmed directly: on a real Wikipedia article,
// that alone - with no badge even involved - was enough to break clicks
// on a floated infobox/sidebar elsewhere on the page. Per the CSS
// spec's default painting order, a positioned element paints above
// floated content regardless of z-index; a paragraph that shares a
// containing block with a floated infobox still has a full-width box
// even where its text visibly wraps around the float, so making that
// paragraph position: relative silently lets its (invisible) box start
// intercepting clicks meant for the infobox underneath it. Positioning
// the badge in page coordinates against document.body instead avoids
// mutating any paragraph's styling at all, so this can't happen -  and
// it scrolls with the page the same way a nested absolute element
// would, since that's how position: absolute against the initial
// containing block behaves.
function attachBadgeTo(paragraph: HTMLElement) {
  const rect = paragraph.getBoundingClientRect()
  badge.style.top = `${rect.top + window.scrollY + 2}px`
  badge.style.left = `${rect.left + window.scrollX - 40}px`
}

// Same page-coordinate approach as attachBadgeTo, offset 40px lower so
// it sits directly beneath the Simplify badge instead of on top of it.
function attachExplainBadgeTo(paragraph: HTMLElement) {
  const rect = paragraph.getBoundingClientRect()
  explainBadge.style.top = `${rect.top + window.scrollY + 2 + 40}px`
  explainBadge.style.left = `${rect.left + window.scrollX - 40}px`
}

// Positions the explanation card just under the paragraph it's about,
// in page coordinates - same reasoning as attachBadgeTo (see its
// comment) for why this is against document.body rather than nesting
// inside the paragraph itself.
function attachExplainCardTo(paragraph: HTMLElement) {
  const rect = paragraph.getBoundingClientRect()
  explainCard.style.top = `${rect.bottom + window.scrollY + 8}px`
  explainCard.style.left = `${rect.left + window.scrollX}px`
}

// paragraphs is usually a single-element array (the common case: a
// small selection or a dwell flag on one paragraph), but can be more
// than one when a selection spans multiple paragraphs - see
// handleSelectionChange. The badge is a single shared element, so it's
// positioned on whichever paragraph comes first in document order, and
// a click simplifies all of them together.
function showBadgeFor(paragraphs: HTMLElement[]) {
  if (paragraphs.length === 0) return
  if (hideTimeoutId) {
    clearTimeout(hideTimeoutId)
    hideTimeoutId = null
  }

  // Read-only: just remembers what's already there. Nothing about
  // showing a badge should touch any paragraph's actual content - only
  // an explicit simplify click does that (see simplifyParagraph below).
  paragraphs.forEach(capturePristine)

  currentParagraphs = paragraphs
  explainSelectedText = (window.getSelection()?.toString() || "").trim()
  styleBadge("idle", paragraphs.length)

  attachBadgeTo(paragraphs[0])

  badge.style.opacity = "1"
  badge.style.pointerEvents = "auto"

  attachExplainBadgeTo(paragraphs[0])
  explainBadge.style.opacity = "1"
  explainBadge.style.pointerEvents = "auto"
}

// ---- First-run onboarding: a centered, two-slide explainer modal ----
//
// An earlier version tried to point a tooltip/spotlight at the real
// badge - first directly on badge appearance, then via a scroll-into-
// view-and-point step after a first slide. Both were unreliable in
// practice (the badge only exists once a real paragraph has been
// flagged or highlighted, and .arw-badge sits at left: -40px of its
// anchor so it isn't always even fully on-screen). Two fully static
// slides, entirely independent of any real page content, sidestep that
// class of bug outright - and since nothing here depends on a badge
// having appeared yet, this can run immediately on page load instead of
// waiting for one.
type OnboardingSlide = {
  title: string
  body: string
  icon: string
  // Only slide 1 sets this - shows a second mock badge next to the
  // first, so the tour visually matches the real product (Simplify and
  // Explain badges appear together on a highlight, not one at a time -
  // see showBadgeFor/attachExplainBadgeTo).
  secondIcon?: string
  mockText: string
  highlightMockText?: boolean
}

const ONBOARDING_SLIDES: OnboardingSlide[] = [
  {
    title: "How Lucent Reader works",
    body: "Highlight any text you find hard to read, and two small badges appear right next to it: Simplify and Explain.",
    icon: ICONS.idle,
    secondIcon: ICONS.explain,
    mockText: "Lorem ipsum dolor sit amet...",
    highlightMockText: true
  },
  {
    title: "One click, simpler or clearer",
    body: "Click Simplify to instantly rewrite that text in plain language, or click Explain to get a short explanation of what it means.",
    icon: ICONS.done,
    mockText: "Amet is now easier to read."
  },
  {
    title: "More ways to customize",
    body: "Tap the Aa button in the bottom-right corner any time to set your reading level, adjust text length, or simplify the whole page at once.",
    icon: "Aa",
    mockText: "Reading level, text length, whole page"
  },
  {
    title: "Settings, in the toolbar icon",
    body: "Click the Lucent Reader icon in your browser toolbar for a Settings tab - turn on a dyslexia-friendly font (off by default) or turn off auto-activation if you'd rather start it yourself on each page.",
    icon: "⚙",
    mockText: "Dyslexia-friendly font: Off  ·  Auto-activate: On"
  }
]

let onboardingModalEl: HTMLDivElement | null = null

function closeOnboardingModal() {
  if (onboardingModalEl) {
    onboardingModalEl.remove()
    onboardingModalEl = null
  }
}

// Shown once, immediately when the extension activates on a readable
// page for the first time after a fresh install (see hasSeenOnboarding
// above and its call site in init()) - two static slides, not a real
// tour of the actual page.
function maybeShowOnboardingModal() {
  if (hasSeenOnboarding) return
  hasSeenOnboarding = true
  markOnboardingSeen()

  let slideIndex = 0

  const backdrop = document.createElement("div")
  backdrop.style.position = "fixed"
  backdrop.style.top = "0"
  backdrop.style.left = "0"
  backdrop.style.right = "0"
  backdrop.style.bottom = "0"
  backdrop.style.backgroundColor = "rgba(0,0,0,0.5)"
  // Needs to stay above the Aa button/panel/badge (all now 2147483647,
  // see the comment on .arw-badge's z-index) or this dimmed backdrop
  // stops actually covering them - confirmed directly: with a lower
  // value here, the Aa button rendered fully bright on top of the dim
  // overlay instead of being hidden under it. Tied at the same max
  // value, the tiebreak is DOM order, and this backdrop is only created
  // here at runtime - well after injectMenu() has already appended the
  // button/panel during init() - so it naturally paints on top.
  backdrop.style.zIndex = "2147483647"
  backdrop.style.display = "flex"
  backdrop.style.alignItems = "center"
  backdrop.style.justifyContent = "center"

  const modal = document.createElement("div")
  modal.style.backgroundColor = tokens.readingBg
  modal.style.borderRadius = "16px"
  modal.style.padding = "28px"
  modal.style.maxWidth = "360px"
  modal.style.width = "90%"
  modal.style.boxShadow = "0 8px 32px rgba(0,0,0,0.3)"
  modal.style.fontFamily = "Inter, sans-serif"
  modal.style.textAlign = "center"

  const progress = document.createElement("div")
  progress.style.fontSize = "12px"
  progress.style.color = tokens.captionText
  progress.style.marginBottom = "8px"

  const title = document.createElement("h2")
  title.style.fontSize = "18px"
  title.style.color = tokens.readingText
  title.style.margin = "0 0 12px"

  const explanation = document.createElement("p")
  explanation.style.fontSize = "14px"
  explanation.style.color = tokens.readingText
  explanation.style.lineHeight = "1.5"
  explanation.style.margin = "0 0 16px"

  const mockRow = document.createElement("div")
  mockRow.style.display = "flex"
  mockRow.style.alignItems = "center"
  mockRow.style.gap = "10px"
  mockRow.style.backgroundColor = "#FFFFFF"
  mockRow.style.border = `1px solid ${tokens.captionText}`
  mockRow.style.borderRadius = "10px"
  mockRow.style.padding = "12px 14px"
  mockRow.style.marginBottom = "20px"
  mockRow.style.textAlign = "left"

  const mockBadge = document.createElement("div")
  mockBadge.style.flexShrink = "0"
  mockBadge.style.width = "28px"
  mockBadge.style.height = "28px"
  mockBadge.style.borderRadius = "50%"
  mockBadge.style.border = `1px solid ${tokens.captionText}`
  mockBadge.style.display = "flex"
  mockBadge.style.alignItems = "center"
  mockBadge.style.justifyContent = "center"
  mockBadge.style.backgroundColor = tokens.readingBg
  mockBadge.style.color = tokens.readingText
  mockBadge.style.fontSize = "11px"
  mockBadge.style.fontWeight = "600"

  // Same styling as mockBadge - only shown for slides that set
  // secondIcon (currently just slide 1), see renderSlide().
  const mockBadge2 = document.createElement("div")
  mockBadge2.style.flexShrink = "0"
  mockBadge2.style.width = "28px"
  mockBadge2.style.height = "28px"
  mockBadge2.style.borderRadius = "50%"
  mockBadge2.style.border = `1px solid ${tokens.captionText}`
  mockBadge2.style.alignItems = "center"
  mockBadge2.style.justifyContent = "center"
  mockBadge2.style.backgroundColor = tokens.readingBg
  mockBadge2.style.color = tokens.readingText
  mockBadge2.style.fontSize = "11px"
  mockBadge2.style.fontWeight = "600"

  const mockText = document.createElement("div")
  mockText.style.fontSize = "13px"
  mockText.style.color = tokens.captionText
  mockText.style.borderRadius = "3px"

  mockRow.appendChild(mockBadge)
  mockRow.appendChild(mockBadge2)
  mockRow.appendChild(mockText)

  const nextBtn = document.createElement("button")
  nextBtn.style.padding = "10px 20px"
  nextBtn.style.borderRadius = "20px"
  nextBtn.style.border = "none"
  nextBtn.style.backgroundColor = tokens.accentTeal
  nextBtn.style.color = "#FFFFFF"
  nextBtn.style.fontSize = "14px"
  nextBtn.style.cursor = "pointer"

  function renderSlide() {
    const slide = ONBOARDING_SLIDES[slideIndex]
    progress.textContent = `${slideIndex + 1} of ${ONBOARDING_SLIDES.length}`
    title.textContent = slide.title
    explanation.textContent = slide.body
    mockBadge.innerHTML = slide.icon
    mockBadge2.style.display = slide.secondIcon ? "flex" : "none"
    if (slide.secondIcon) mockBadge2.innerHTML = slide.secondIcon
    mockText.textContent = slide.mockText
    mockText.style.backgroundColor = slide.highlightMockText ? "#FFF3B0" : "transparent"
    mockText.style.padding = slide.highlightMockText ? "2px 4px" : "0"
    nextBtn.textContent = slideIndex === ONBOARDING_SLIDES.length - 1 ? "Got it" : "Next"
  }

  nextBtn.addEventListener("click", () => {
    if (slideIndex < ONBOARDING_SLIDES.length - 1) {
      slideIndex++
      renderSlide()
    } else {
      closeOnboardingModal()
    }
  })

  renderSlide()

  modal.appendChild(progress)
  modal.appendChild(title)
  modal.appendChild(explanation)
  modal.appendChild(mockRow)
  modal.appendChild(nextBtn)
  backdrop.appendChild(modal)
  document.body.appendChild(backdrop)

  onboardingModalEl = backdrop
}

function hideBadge() {
  badge.style.opacity = "0"
  badge.style.pointerEvents = "none"
  currentParagraphs = null

  explainBadge.style.opacity = "0"
  explainBadge.style.pointerEvents = "none"
}

// Separate from hideBadge - the card is left open (if already open)
// even after the selection that triggered it clears, so the user can
// finish reading the explanation. Only explicit interactions (its own
// close button, or opening a new explanation) close it.
function hideExplanationCard() {
  explainCard.style.display = "none"
  explainAnchorParagraph = null
}

function showExplanation(text: string) {
  explainCardBody.textContent = text
  explainCardBody.style.color = tokens.readingText
  explainCard.style.backgroundColor = tokens.readingBg
  explainCard.style.borderColor = tokens.captionText

  if (explainAnchorParagraph) attachExplainCardTo(explainAnchorParagraph)
  explainCard.style.display = "block"
}

function showExplanationError(error: string) {
  explainCardBody.textContent = error
  explainCardBody.style.color = "#8A2E2E"
  explainCard.style.backgroundColor = "#FBEAEA"
  explainCard.style.borderColor = "#8A2E2E"

  if (explainAnchorParagraph) attachExplainCardTo(explainAnchorParagraph)
  explainCard.style.display = "block"
}

function styleControlButton(el: HTMLElement) {
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

function revertParagraph(paragraph: HTMLElement) {
  const pristine = pristineByParagraph.get(paragraph)
  if (!pristine) return

  // Restores the real original markup (links, bold, italic - everything),
  // not a plain-text copy. This also discards the revert/resimplify
  // buttons and whatever badge state was sitting in the paragraph, which
  // is correct - a reverted paragraph goes back to looking untouched.
  paragraph.innerHTML = pristine.html
  paragraph.style.borderLeft = ""
  paragraph.style.paddingLeft = ""
  simplifiedParagraphs.delete(paragraph)
}

// Adds the small revert (↺) and re-simplify (↻) controls after a
// paragraph has been simplified. Re-simplify re-runs simplifyParagraph,
// which always works from the cached pristine text - so it re-simplifies
// from the true original at whatever the current grade-level/length
// settings are, rather than stacking a simplification on top of the
// last one.
function addParagraphControls(paragraph: HTMLElement) {
  const revertBtn = document.createElement("button")
  revertBtn.textContent = "↺"
  revertBtn.title = "Revert to original text"
  styleControlButton(revertBtn)
  revertBtn.addEventListener("click", (e) => {
    e.stopPropagation()
    logEvent("revert_click", {})
    revertParagraph(paragraph)
  })

  const resimplifyBtn = document.createElement("button")
  resimplifyBtn.textContent = "↻"
  resimplifyBtn.title = "Re-simplify with current settings"
  styleControlButton(resimplifyBtn)
  resimplifyBtn.addEventListener("click", (e) => {
    e.stopPropagation()
    logEvent("resimplify_click", { targetGradeLevel, targetLength })
    performSimplify([paragraph])
  })

  const textEl = paragraph.querySelector(":scope > .arw-text") as HTMLDivElement | null
  if (textEl) {
    textEl.insertAdjacentElement("afterend", revertBtn)
    revertBtn.insertAdjacentElement("afterend", resimplifyBtn)
  } else {
    paragraph.appendChild(revertBtn)
    paragraph.appendChild(resimplifyBtn)
  }
}

// Always simplifies from the true original text (pristineByParagraph),
// never from whatever's currently showing - so calling this again on an
// already-simplified paragraph re-simplifies from scratch at the
// current settings instead of compounding onto the last simplification.
async function simplifyParagraph(paragraph: HTMLElement) {
  capturePristine(paragraph)
  const pristine = pristineByParagraph.get(paragraph)!
  if (!pristine.text.trim()) return

  const simplified = await simplifyText(pristine.text, targetGradeLevel, targetLength)

  // Rebuilds the paragraph as structured content (short paragraphs,
  // bullet lists, bolded key terms via renderSimpleMarkdown) rather than
  // one flat text block - unavoidable either way, since the simplified
  // text is a genuinely different rewrite with no markup of its own to
  // preserve. What matters is that this only happens on an explicit
  // simplify action, and that revertParagraph() can always restore the
  // real original from pristineByParagraph.
  paragraph.innerHTML = ""
  const textContainer = document.createElement("div")
  textContainer.className = "arw-text"
  renderSimpleMarkdown(textContainer, simplified)
  paragraph.appendChild(textContainer)

  paragraph.style.borderLeft = `3px solid ${tokens.accentTeal}`
  paragraph.style.paddingLeft = "10px"

  simplifiedParagraphs.add(paragraph)
  addParagraphControls(paragraph)
  // Repositions the badge over this paragraph's current (post-
  // simplify) layout, since its height may have changed - doesn't
  // touch the paragraph itself, see attachBadgeTo.
  attachBadgeTo(paragraph)
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

  // The actual fetch to the backend happens in the background service
  // worker, not here - see lib/messages.ts for why.
  const message: SimplifyMessage = {
    type: SIMPLIFY_MESSAGE_TYPE,
    text,
    targetGradeLevel: targetLevel,
    targetLength: length,
    installId
  }
  const response = (await chrome.runtime.sendMessage(message)) as SimplifyResponse

  if (response.ok === false) {
    throw new Error(response.error)
  }

  return response.simplified
}

async function explainText(
  text:string,
  context: string,
  targetLevel: number,
  length: TextLength,
): Promise<string> {
  const installId = await getInstallId()

  const message: ExplainMessage = {
    type: EXPLAIN_MESSAGE_TYPE,
    text,
    context,
    targetGradeLevel: targetLevel,
    targetLength: length,
    installId
  }

  const response = (await chrome.runtime.sendMessage(message)) as ExplainResponse

  if(response.ok === false) {
    throw new Error(response.error)
  }

  return response.explanation
}

// Registers the badge's click handler, the highlight-to-badge and
// dwell-detection triggers, and starts observing the page's content
// blocks. Wired up like this (as one function, called conditionally)
// rather than as top-level side effects, so that a page which fails the
// isProbablyReaderable() check at the bottom of this file genuinely
// never activates any of it - no observer, no listeners, no menu.
// Shared by both ways to trigger a simplify: clicking the badge itself,
// and clicking the small re-simplify (↻) control on an already-
// simplified paragraph (see addParagraphControls above). Moves the
// shared badge onto this paragraph and drives it through the same
// loading/done/error states either way, so the two entry points look
// and behave identically.
let simplifyInFlight = false

async function performSimplify(paragraphs: HTMLElement[]) {
  // Guards against a re-entrant call (a second click while the first is
  // still awaiting its API response, or an overlapping dwell/selection
  // trigger firing mid-flight) starting a second concurrent simplify on
  // the same paragraph(s) - each independently reads pristine, wipes the
  // paragraph's innerHTML, and rebuilds it, so two of them racing is a
  // real correctness gap, not just a wasted API call.
  if (paragraphs.length === 0 || simplifyInFlight) return
  simplifyInFlight = true
  try {
    await runSimplify(paragraphs)
  } finally {
    simplifyInFlight = false
  }
}

let explainInFlight = false

async function performExplain(currentSelectedText: string, surroundingContext: string){
  if(currentSelectedText.length === 0 || explainInFlight) return 
  explainInFlight = true
  
  try {
    const explanation = await explainText(
      currentSelectedText,
      surroundingContext,
      targetGradeLevel,
      targetLength
    )

    showExplanation(explanation)
  } catch (err) {
    const message = err instanceof Error ? err.message : "Something went wrong"
    showExplanationError(message)
  } finally {
    explainInFlight = false
  }

}

async function runSimplify(paragraphs: HTMLElement[]) {
  currentParagraphs = paragraphs
  const anchor = paragraphs[0]
  attachBadgeTo(anchor)
  badge.style.opacity = "1"
  badge.style.pointerEvents = "auto"

  logEvent("simplify_click", {
    paragraphCount: paragraphs.length,
    textPreview: (anchor.textContent || "").slice(0, 60),
    targetGradeLevel,
    targetLength
  })

  styleBadge("loading", paragraphs.length)

  // The Render free tier spins the backend down after inactivity - a
  // keep-alive workflow (.github/workflows/keep-alive.yml) pings it
  // every 10 minutes to prevent that, but if a ping window is ever
  // missed (a redeploy, a delayed Actions run), the first real request
  // after a cold start can take several seconds longer than usual.
  // Past that point, "Simplifying..." reads as a stuck/broken
  // extension rather than what it actually is, so this swaps the label
  // to something that explains the wait instead.
  const wakeUpTimeoutId = window.setTimeout(() => {
    badgeLabel.textContent = "Waking up the server..."
  }, 5000)

  // Each paragraph is simplified independently (its own API call, its
  // own revert/resimplify controls afterward) - Promise.allSettled so
  // one failure among several selected paragraphs doesn't roll back or
  // block the ones that succeeded.
  const results = await Promise.allSettled(paragraphs.map((p) => simplifyParagraph(p)))
  clearTimeout(wakeUpTimeoutId)

  const failures = results.filter(
    (r): r is PromiseRejectedResult => r.status === "rejected"
  )

  if (failures.length === 0) {
    styleBadge("done", paragraphs.length)
    logEvent("simplify_done", {
      paragraphCount: paragraphs.length,
      textPreview: (anchor.textContent || "").slice(0, 60),
      targetGradeLevel,
      targetLength
    })
  } else {
    const firstMessage = failures[0].reason instanceof Error ? failures[0].reason.message : "Something went wrong"
    const message =
      failures.length === paragraphs.length
        ? firstMessage
        : `${failures.length} of ${paragraphs.length} failed`
    badgeIcon.innerHTML = ICONS.error
    badgeLabel.textContent = message
    badge.style.backgroundColor = "#FBEAEA"
    badge.style.color = "#8A2E2E"
    badge.classList.add("arw-expanded")
    logEvent("simplify_error", {
      paragraphCount: paragraphs.length,
      failureCount: failures.length,
      error: firstMessage
    })
  }

  hideTimeoutId = window.setTimeout(hideBadge, 2000)
}

function activateBadgeClickHandler() {
  badge.addEventListener("click", async () => {
    if (!currentParagraphs) return
    await performSimplify(currentParagraphs)
  })
}

// performExplain() itself already handles the in-flight guard, the try/
// catch, and routing the result to showExplanation/showExplanationError
// - this just anchors the card to the right paragraph first and gives
// the badge its own loading label while the request is in flight.
function activateExplainBadgeClickHandler() {
  explainBadge.addEventListener("click", async () => {
    if (!currentParagraphs || !explainSelectedText) return

    explainAnchorParagraph = currentParagraphs[0]
    attachExplainCardTo(explainAnchorParagraph)

    explainBadgeLabel.textContent = "Explaining..."
    explainBadge.classList.add("arw-expanded")

    logEvent("explain_click", {
      paragraphCount: currentParagraphs.length,
      textPreview: explainSelectedText.slice(0, 60)
    })

    await performExplain(explainSelectedText, explainAnchorParagraph.textContent || "")

    explainBadgeLabel.textContent = "Explain"
    explainBadge.classList.remove("arw-expanded")
  })
}

// ---- Trigger 1: user highlights text themselves ----

let selectionDebounceId: number | null = null

function handleSelectionChange() {
  if (selectionDebounceId) clearTimeout(selectionDebounceId)
  selectionDebounceId = window.setTimeout(() => {
    const selection = window.getSelection()
    if (!selection || selection.toString().trim().length === 0) {
      currentSelectedText = selection.toString().trim()
      surroundingContext = ""
      hideBadge()
      return
    }

    if (selection.rangeCount === 0) return

    const anchorNode = selection.anchorNode
    if (!anchorNode) return
    // anchorOffset matters here - see resolveAnchorStart() in
    // lib/content-blocks.ts for why (block-level selections can report
    // an element anchor with a child-index offset instead of a text node).
    const anchorParagraph = findContentBlock(anchorNode, selection.anchorOffset)
    if (!anchorParagraph) {
      currentSelectedText = selection.toString().trim()
      surroundingContext = ""
      hideBadge()
      return
      
    }

    // A selection can span multiple paragraphs (drag across paragraph
    // boundaries) - find every content block the selection's range
    // actually touches, not just the one containing the anchor, so
    // "Simplify" acts on everything that's visibly highlighted instead
    // of silently only the first paragraph. The anchor paragraph is
    // always included even if the overlap check somehow misses it, so
    // the single-paragraph case (the overwhelming majority of
    // selections) is unaffected.
    //
    // Uses rangeMeaningfullyOverlapsBlock() rather than a plain
    // range.intersectsNode() filter - confirmed directly that
    // intersectsNode alone counts a selection that ends at offset 0 of
    // the NEXT paragraph (selecting zero of its characters) as
    // "intersecting" that paragraph, which is an ordinary, common
    // outcome of a real drag ending at the last character of one
    // paragraph. Without the stricter check, that silently swept an
    // unselected paragraph into the simplify batch.
    const range = selection.getRangeAt(0)
    const touched = getActiveParagraphs().filter((p) => rangeMeaningfullyOverlapsBlock(range, p))
    const paragraphs = touched.includes(anchorParagraph) ? touched : [anchorParagraph, ...touched]
    paragraphs.sort((a, b) =>
      a === b ? 0 : a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1
    )

    showBadgeFor(paragraphs)
  }, 150)
}

function activateSelectionTrigger() {
  document.addEventListener("selectionchange", handleSelectionChange)

  document.addEventListener("mousedown", (e) => {
    const target = e.target as Node
    // explainBadge/explainCard are excluded too - otherwise mousedown on
    // the Explain button (which fires before its own click handler)
    // would hideBadge() first, clearing currentParagraphs out from under
    // that click handler before it ever runs.
    if (!badge.contains(target) && !explainBadge.contains(target) && !explainCard.contains(target)) {
      hideBadge()
    }
  })
}

// Badge/explain-card position is computed once, in page coordinates
// (getBoundingClientRect + window.scrollX/Y - see attachBadgeTo), on the
// assumption that scrolling means the whole document scrolls. That's
// true on a normal page, but Reading Mode's overlay is its own
// position: fixed, overflow-y: auto container (see buildReaderOverlay) -
// scrolling through reader content moves the overlay's scrollTop, not
// window.scrollY, so anything positioned that way silently stops
// tracking its paragraph and just sits still while the text scrolls
// underneath it. "scroll" events don't bubble, but a capturing listener
// on document still sees them fire on the overlay (or any other
// scrollable ancestor), so this one listener covers both cases without
// needing a direct reference to the overlay element.
let scrollRepositionScheduled = false

function repositionAnchoredUI() {
  if (scrollRepositionScheduled) return
  scrollRepositionScheduled = true
  requestAnimationFrame(() => {
    scrollRepositionScheduled = false
    if (currentParagraphs && currentParagraphs.length > 0) {
      attachBadgeTo(currentParagraphs[0])
      attachExplainBadgeTo(currentParagraphs[0])
    }
    if (explainAnchorParagraph && explainCard.style.display === "block") {
      attachExplainCardTo(explainAnchorParagraph)
    }
  })
}

function activateScrollReposition() {
  document.addEventListener("scroll", repositionAnchoredUI, { capture: true, passive: true })
}

// ---- Trigger 2: dwell time (struggle detection) ----

function handleIntersection(entries: IntersectionObserverEntry[]) {
  for (const entry of entries) {
    const paragraph = entry.target as HTMLElement
    if (entry.isIntersecting) {
      // Already flagged (or already simplified via some other trigger,
      // e.g. a highlight) - scrolling this exact paragraph out of view
      // and back in should be a no-op, not schedule yet another dwell
      // timer for a paragraph we've already acted on. Checked here,
      // before scheduling, rather than only inside the timeout below -
      // repeated scroll-in/out on an already-flagged paragraph used to
      // still queue a fresh timer every time (harmless on its own since
      // the inner check caught it, but wasteful and not a true no-op).
      if (flaggedParagraphs.has(paragraph) || simplifiedParagraphs.has(paragraph)) continue
      const timerId = window.setTimeout(() => {
        if (!flaggedParagraphs.has(paragraph) && !simplifiedParagraphs.has(paragraph)) {
          flaggedParagraphs.add(paragraph)
          logEvent("dwell_flag", { textPreview: (paragraph.textContent || "").slice(0, 60) })
          showBadgeFor([paragraph])
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

// Not constructed until activateDwellDetection() runs, so that a page
// that fails the isProbablyReaderable() check never gets an
// IntersectionObserver watching it at all.
let observer: IntersectionObserver | null = null

// Tracks exactly which paragraphs the observer currently watches.
// IntersectionObserver has no "list what's observed" API, so this Set is
// the only way to cleanly unobserve everything when Reading Mode swaps
// which paragraph set (real page vs. extracted reader view) is active.
const observedParagraphs = new Set<Element>()

function observeParagraph(p: Element) {
  if (!observer || observedParagraphs.has(p)) return
  observedParagraphs.add(p)
  observer.observe(p)
}

function unobserveAllParagraphs() {
  if (!observer) return
  observedParagraphs.forEach((p) => observer!.unobserve(p))
  observedParagraphs.clear()
  activeTimers.forEach((timerId) => clearTimeout(timerId))
  activeTimers.clear()
}

function activateDwellDetection() {
  observer = new IntersectionObserver(handleIntersection, { threshold: 0.5 })
  getContentBlocks().forEach(observeParagraph)
}

// Returns whichever paragraph set "Simplify Entire Page" should act on:
// the extracted reader-view paragraphs while Reading Mode is on (the
// real page underneath is hidden and shouldn't be touched), or the real
// page's own content blocks otherwise.
function getActiveParagraphs(): HTMLElement[] {
  return readingModeOn ? readerParagraphs : getContentBlocks()
}

// ---- Menu: Simplify Entire Page + Reading Mode + Target Grade Level ----

let readingModeOn = false

// ---- Reader Mode ----
//
// Real article extraction via Mozilla's Readability (the engine behind
// Firefox Reader View), rendered as a full-screen overlay on top of the
// untouched real page - not a recoloring of Wikipedia's own DOM. The
// simplify features (badge, dwell detection, highlight-to-simplify,
// revert) aren't reimplemented for this view: showBadgeFor,
// simplifyParagraph, addParagraphControls, and the selectionchange
// handler are all already generic over any <p> element, so once the
// extracted paragraphs are real elements in the live document and
// handed to observeParagraph(), everything else just works unmodified.

let readerOverlayEl: HTMLDivElement | null = null
let readerParagraphs: HTMLElement[] = []
let switchBtnEl: HTMLButtonElement | null = null

function injectReaderStyles() {
  const style = document.createElement("style")
  style.textContent = `
    .arw-reader-content p {
      margin: 0 0 1.3em;
      font-size: 19px;
      line-height: 1.8;
      color: ${tokens.readingText};
    }
    .arw-reader-content h1, .arw-reader-content h2, .arw-reader-content h3 {
      color: ${tokens.readingText};
      line-height: 1.4;
      margin: 1.4em 0 0.6em;
    }
    .arw-reader-content ul, .arw-reader-content ol {
      color: ${tokens.readingText};
      font-size: 19px;
      line-height: 1.8;
      padding-left: 1.4em;
    }
    .arw-reader-content img, .arw-reader-content figure {
      max-width: 100%;
      height: auto;
    }
    /* Explicit color + background, not just layout - Readability strips
       every class and style attribute during extraction (confirmed: every
       code/pre/span in the rendered output comes through with no class
       and no inline style left), so none of a source page's own syntax-
       highlighting colors survive. Left unset, these would inherit
       whatever color/background the host page's own unscoped code/pre
       tag-level CSS resolves to right now - including that page's own
       dark-mode theme, since this overlay lives in the same document, not
       an isolated Shadow DOM. Confirmed directly on docs.python.org in
       its dark theme: code chips computed to our own dark inherited text
       color on that page's dark-mode code background (rgb(44,44,42) on
       rgb(66,66,66) - both dark, unreadable), and code blocks to white
       text on a transparent background sitting on this overlay's cream
       page (also unreadable). Same class of bug as the table backstop
       below, just for text color instead of layout. */
    .arw-reader-content pre, .arw-reader-content code {
      white-space: pre-wrap;
      word-break: break-word;
      max-width: 100%;
      background-color: #EAE6D9 !important;
      color: ${tokens.readingText} !important;
    }
    .arw-reader-content code {
      padding: 0.15em 0.4em;
      border-radius: 4px;
      font-size: 0.9em;
    }
    .arw-reader-content pre {
      padding: 1em;
      border-radius: 8px;
      overflow-x: auto;
    }
    .arw-reader-content pre code {
      background-color: transparent !important;
      padding: 0;
    }
    .arw-reader-content blockquote {
      border-left: 3px solid ${tokens.accentTeal};
      margin: 1em 0;
      padding-left: 1em;
      color: ${tokens.captionText};
    }
    .arw-reader-content a {
      color: ${tokens.accentTeal};
    }
    /* Defensive backstop, not the primary fix - real infoboxes/navboxes
       are stripped before extraction in extractArticle() below. This
       just keeps any unanticipated table on some other page from
       stacking (Wikipedia's own responsive table CSS still applies
       inside this overlay, since it's the same live document, and can
       force table cells to display:block below certain widths). */
    .arw-reader-content table {
      border-collapse: collapse;
      margin: 1em 0;
      font-size: 16px;
    }
    .arw-reader-content th, .arw-reader-content td {
      display: table-cell !important;
      border: 1px solid ${tokens.captionText};
      padding: 6px 10px;
      text-align: left;
      vertical-align: top;
    }
    .arw-reader-content tr {
      display: table-row !important;
    }
    .arw-reader-table-wrap {
      max-width: 100%;
      overflow-x: auto;
    }
  `
  document.head.appendChild(style)
}

// Wikipedia classes that are never real article prose - infoboxes,
// sidebars, navigation footers, and maintenance banners. Readability's
// own content-scoring can still pull these in (an infobox sits right
// next to the lead paragraph, so it sometimes looks like "part of the
// content" structurally), so they're removed from the clone before
// Readability ever sees it, rather than relying on Readability to
// exclude them correctly.
const NON_ARTICLE_SELECTORS = [
  ".infobox",
  ".sidebar",
  ".navbox",
  ".vertical-navbox",
  ".metadata",
  ".ambox",
  ".toc",
  "#toc"
]

// Functional "next/previous page" links (continuing the same article/manual
// onto another URL) vs. general site navigation: Readability has no concept
// of the former. It strips both the same way - a "Next"/"Prev" link almost
// always sits inside a short, link-dense container (a <div class="navfooter">
// or <div class="pagination">), and that container itself gets removed by
// _cleanConditionally()/the unlikely-candidates pass in Readability.js
// well before per-link logic ever runs, taking the links down with it.
// Confirmed directly against https://www.postgresql.org/docs/17/resources.html -
// its docbook-generated `<div class="navfooter">` with
// `<a accesskey="p">Prev</a>` and `<a accesskey="n">Next</a>` is silently
// gone from Readability's output.
//
// Rather than trying to preserve navfooter-like containers wholesale
// (which would drag the Up/Home links and their surrounding table markup
// back in too - real site chrome, correctly excluded), this pulls out just
// the one prev/next anchor of each direction before Readability ever
// touches the clone, using signals that mean "adjacent document in a
// series" specifically: rel="next"/rel="prev" are literally the HTML
// spec's definition of that relationship, and accesskey="n"/accesskey="p"
// are the long-standing a11y convention docbook (and PostgreSQL's docs)
// use for the same thing. Bare text like "Next" or "Prev" is only trusted
// alongside one of those two structural signals, since on its own it's
// just as likely to be a "next/previous blog post" widget - a different
// article, not part of this one's own pagination. Without a rel/accesskey
// signal, only specific, low-ambiguity phrasing counts.
const PAGINATION_LINK_TEXT: Record<"next" | "prev", RegExp> = {
  next: /^(next\s*page|next\s*section|next\s*chapter|continue\s*reading)\s*[»›→>]?$/i,
  prev: /^[«‹<]?\s*(prev(ious)?\s*page|prev(ious)?\s*section|prev(ious)?\s*chapter)$/i
}

function findPaginationLink(
  doc: Document,
  direction: "next" | "prev"
): { href: string; text: string } | null {
  const relTokensToMatch = direction === "next" ? ["next"] : ["prev", "previous"]
  const accessKey = direction === "next" ? "n" : "p"
  const anchors = Array.from(doc.querySelectorAll("a[href]"))
  for (const anchor of anchors) {
    const href = (anchor as HTMLAnchorElement).href
    if (!href) continue
    const relTokens = (anchor.getAttribute("rel") || "").toLowerCase().split(/\s+/)
    const isRelMatch = relTokens.some((token) => relTokensToMatch.includes(token))
    const isAccessKeyMatch = (anchor.getAttribute("accesskey") || "").toLowerCase() === accessKey
    const text = (anchor.textContent || "").trim()
    // Docbook-style nav links (PostgreSQL's docs included) put the actual
    // next/previous chapter title in the title attribute and leave the
    // visible text as a bare "Next"/"Prev" - prefer that for the label
    // when present, since "Continue reading: Bug Reporting Guidelines"
    // means a lot more than "Continue reading: Next".
    const displayText = (anchor.getAttribute("title") || "").trim() || text
    if ((isRelMatch || isAccessKeyMatch) && text) {
      return { href, text: displayText }
    }
    if (PAGINATION_LINK_TEXT[direction].test(text)) {
      return { href, text: displayText }
    }
  }
  return null
}

// Runs Readability against a clone of the document, never the live one -
// Readability mutates the tree it's given as it parses, and doing that
// to the real page would break it.
function extractArticle(): {
  title: string
  contentHTML: string
  nextLink: { href: string; text: string } | null
  prevLink: { href: string; text: string } | null
} | null {
  const clone = document.cloneNode(true) as Document
  NON_ARTICLE_SELECTORS.forEach((selector) => {
    clone.querySelectorAll(selector).forEach((el) => el.remove())
  })
  // Must run before Readability.parse() mutates/removes nodes from the
  // clone - by the time parse() returns, the pagination links (along with
  // the rest of their navfooter-like container) are already gone.
  const nextLink = findPaginationLink(clone, "next")
  const prevLink = findPaginationLink(clone, "prev")
  const article = new Readability(clone).parse()
  if (!article || !article.content) return null
  return {
    title: article.title || document.title,
    contentHTML: article.content,
    nextLink,
    prevLink
  }
}

// Wraps any table that still made it through extraction in its own
// horizontally-scrollable container, so an unexpectedly wide table
// scrolls within itself instead of forcing the whole page to scroll
// sideways.
function wrapWideTables(container: HTMLElement) {
  container.querySelectorAll("table").forEach((table) => {
    const wrap = document.createElement("div")
    wrap.className = "arw-reader-table-wrap"
    table.parentNode?.insertBefore(wrap, table)
    wrap.appendChild(table)
  })
}

// Set right before a Prev/Next click's own default navigation takes the
// tab to a whole new page load - and with it, a whole new content script
// instance with no memory of readingModeOn. sessionStorage (not
// chrome.storage.local) specifically: it's scoped to this one tab, so two
// tabs each reading their own paginated article via these links can never
// stomp on each other's flag, and it survives exactly a same-origin
// navigation within the same tab, which is what a "next page" link always
// is in practice. Read once at top-level below, on the very next page
// load, to auto-resume Reading Mode there.
const READING_MODE_CONTINUE_KEY = "arw-reading-mode-continue"

function buildPaginationLinkEl(
  link: { href: string; text: string },
  direction: "next" | "prev"
): HTMLAnchorElement {
  const el = document.createElement("a")
  el.href = link.href
  el.textContent =
    direction === "next" ? `Continue reading: ${link.text} →` : `← Previous: ${link.text}`
  el.style.flex = "1"
  el.style.padding = "14px 20px"
  el.style.borderRadius = "10px"
  el.style.border = `1px solid ${tokens.accentTeal}`
  el.style.color = tokens.accentTeal
  el.style.textDecoration = "none"
  el.style.fontSize = "16px"
  el.style.fontWeight = "600"
  el.style.textAlign = direction === "next" ? "right" : "left"
  el.addEventListener("click", () => {
    sessionStorage.setItem(READING_MODE_CONTINUE_KEY, "1")
  })
  return el
}

function buildReaderOverlay(article: {
  title: string
  contentHTML: string
  nextLink: { href: string; text: string } | null
  prevLink: { href: string; text: string } | null
}): {
  overlay: HTMLDivElement
  contentContainer: HTMLDivElement
} {
  const overlay = document.createElement("div")
  overlay.id = "arw-reader-overlay"
  overlay.style.position = "fixed"
  overlay.style.top = "0"
  overlay.style.left = "0"
  overlay.style.right = "0"
  overlay.style.bottom = "0"
  overlay.style.zIndex = "500000"
  overlay.style.backgroundColor = tokens.readingBg
  overlay.style.overflowY = "auto"
  overlay.style.overflowX = "hidden"
  overlay.style.boxSizing = "border-box"
  // Without this, scrolling the overlay to its top/bottom edge lets the
  // wheel/trackpad gesture's remaining delta "chain" through to the real
  // page underneath (position: fixed doesn't stop scroll chaining on its
  // own) - invisibly scrolling the hidden page behind this full-screen
  // overlay. That silently changes window.scrollY, which is exactly what
  // attachBadgeTo/attachExplainCardTo add to a paragraph's
  // getBoundingClientRect() to place UI in page coordinates (see
  // repositionAnchoredUI) - so the Explain card/badges would drift out
  // of sync with the visibly-scrolling overlay content even though their
  // own reposition-on-scroll logic was firing correctly. Confirmed
  // directly: programmatic overlay.scrollBy() alone (no chaining) kept
  // the card perfectly anchored; only real chained scroll broke it.
  overlay.style.overscrollBehavior = "contain"

  const closeBtn = document.createElement("button")
  closeBtn.textContent = "✕ Exit Reading Mode"
  closeBtn.style.position = "fixed"
  closeBtn.style.top = "16px"
  closeBtn.style.right = "16px"
  closeBtn.style.zIndex = "500001"
  closeBtn.style.padding = "8px 16px"
  closeBtn.style.borderRadius = "20px"
  closeBtn.style.border = "none"
  closeBtn.style.backgroundColor = tokens.accentTeal
  closeBtn.style.color = "#FFFFFF"
  closeBtn.style.fontFamily = "Inter, sans-serif"
  closeBtn.style.fontSize = "13px"
  closeBtn.style.cursor = "pointer"
  closeBtn.style.boxShadow = "0 2px 8px rgba(0,0,0,0.2)"
  closeBtn.addEventListener("click", () => setReadingMode(false))

  const wrapper = document.createElement("div")
  wrapper.style.maxWidth = "680px"
  wrapper.style.width = "100%"
  wrapper.style.boxSizing = "border-box"
  wrapper.style.margin = "0 auto"
  wrapper.style.padding = "72px 24px 80px"
  wrapper.style.fontFamily = "'Varela Round', sans-serif"

  const titleEl = document.createElement("h1")
  titleEl.textContent = article.title
  titleEl.style.fontSize = "28px"
  titleEl.style.lineHeight = "1.3"
  titleEl.style.color = tokens.readingText
  titleEl.style.marginBottom = "24px"

  const contentContainer = document.createElement("div")
  contentContainer.className = "arw-reader-content"
  contentContainer.innerHTML = article.contentHTML
  wrapWideTables(contentContainer)

  wrapper.appendChild(titleEl)
  wrapper.appendChild(contentContainer)

  // Rescued separately from Readability's own output (see
  // findPaginationLink) since neither survives extraction otherwise -
  // rendered as their own clearly-separate affordance rather than folded
  // into contentContainer, so they read as "leave this article to
  // continue it elsewhere" rather than as part of the article's own prose.
  if (article.prevLink || article.nextLink) {
    const paginationRow = document.createElement("div")
    paginationRow.style.display = "flex"
    paginationRow.style.gap = "12px"
    paginationRow.style.marginTop = "2.4em"

    if (article.prevLink) {
      paginationRow.appendChild(buildPaginationLinkEl(article.prevLink, "prev"))
    }
    if (article.nextLink) {
      paginationRow.appendChild(buildPaginationLinkEl(article.nextLink, "next"))
    }

    wrapper.appendChild(paginationRow)
  }

  overlay.appendChild(closeBtn)
  overlay.appendChild(wrapper)

  return { overlay, contentContainer }
}

// Builds a fresh overlay from a fresh extraction every time Reading Mode
// turns on, rather than trying to persist/reuse one across toggles - the
// real page is never mutated in the first place, so there's nothing to
// restore on exit beyond removing this overlay.
function enterReaderMode(): boolean {
  const article = extractArticle()
  if (!article) return false

  unobserveAllParagraphs()

  const { overlay, contentContainer } = buildReaderOverlay(article)
  document.body.appendChild(overlay)
  readerOverlayEl = overlay

  readerParagraphs = Array.from(contentContainer.querySelectorAll("p"))
  readerParagraphs.forEach(observeParagraph)

  return true
}

function exitReaderMode() {
  if (readerOverlayEl) {
    readerOverlayEl.remove()
    readerOverlayEl = null
  }
  readerParagraphs = []

  unobserveAllParagraphs()
  getContentBlocks().forEach(observeParagraph)
}

function syncReadingModeSwitch(on: boolean) {
  if (!switchBtnEl) return
  switchBtnEl.textContent = on ? "On" : "Off"
  switchBtnEl.style.backgroundColor = on ? tokens.accentTeal : tokens.captionText
}

function setReadingMode(on: boolean) {
  if (on) {
    const entered = enterReaderMode()
    if (!entered) {
      logEvent("reading_mode_error", {})
      syncReadingModeSwitch(false)
      return
    }
  } else {
    exitReaderMode()
  }

  readingModeOn = on
  syncReadingModeSwitch(on)
  logEvent("reading_mode_toggled", { readingModeOn })
}

function createSectionLabel(text: string): HTMLDivElement {
  const label = document.createElement("div")
  label.textContent = text
  label.style.fontSize = "11px"
  label.style.fontWeight = "600"
  label.style.letterSpacing = "0.06em"
  label.style.textTransform = "uppercase"
  label.style.color = tokens.captionText
  return label
}

function createDivider(): HTMLDivElement {
  const divider = document.createElement("div")
  divider.style.borderTop = `1px solid ${tokens.captionText}`
  divider.style.opacity = "0.3"
  divider.style.margin = "2px 0"
  return divider
}

function injectMenu(devModeEnabled: boolean) {
  const menuButton = document.createElement("button")
  menuButton.textContent = "Aa"
  menuButton.style.position = "fixed"
  menuButton.style.bottom = "20px"
  menuButton.style.right = "20px"
  // See the matching comment on .arw-badge's z-index above - same fix,
  // same reason (this button sits in the same bottom-right corner a lot
  // of cookie-consent banners claim for themselves).
  menuButton.style.zIndex = "2147483647"
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
  panel.style.zIndex = "2147483647"
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

  let simplifyAllInProgress = false
  let simplifyAllStopRequested = false

  simplifyAllBtn.addEventListener("click", async () => {
    // While a run is already in progress, this same button doubles as
    // "stop" - the button stays enabled (not disabled) specifically so
    // this second click can register at all. Setting the flag doesn't
    // interrupt whatever paragraph is currently mid-request; the loop
    // below only checks it between paragraphs, so the one in flight
    // finishes normally and everything queued after it is skipped.
    if (simplifyAllInProgress) {
      simplifyAllStopRequested = true
      logEvent("simplify_all_stopped", { targetGradeLevel, targetLength })
      return
    }

    logEvent("simplify_all_click", { targetGradeLevel, targetLength })
    simplifyAllInProgress = true
    simplifyAllStopRequested = false
    simplifyAllBtn.textContent = "Simplifying page... (click to stop)"
    simplifyAllBtn.style.backgroundColor = tokens.accentTeal
    simplifyAllBtn.style.color = "#FFFFFF"

    // A per-paragraph failure (a rate limit, a transient network error,
    // a cold-start timeout) must not abort the whole run - caught here
    // and logged so it's visible, while the loop moves on to the next
    // paragraph instead of leaving the button permanently stuck on
    // "Simplifying page..." forever. Confirmed directly: without this,
    // one uncaught rejection here means simplifyAllInProgress and the
    // button's label/style below never get reset, since the code that
    // resets them sits after this loop and never runs.
    for (const p of getActiveParagraphs()) {
      if (simplifyAllStopRequested) break
      try {
        await simplifyParagraph(p)
      } catch (err) {
        logEvent("simplify_all_paragraph_error", {
          error: err instanceof Error ? err.message : "Something went wrong"
        })
      }
    }

    simplifyAllInProgress = false
    const wasStopped = simplifyAllStopRequested
    simplifyAllStopRequested = false
    simplifyAllBtn.textContent = wasStopped ? "Simplify Entire Page" : "✓ Page Simplified"
    simplifyAllBtn.style.backgroundColor = wasStopped ? "#FFFFFF" : tokens.badgeDoneBg
    simplifyAllBtn.style.color = wasStopped ? tokens.readingText : tokens.badgeDoneText
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

  switchBtn.addEventListener("click", () => setReadingMode(!readingModeOn))

  switchBtnEl = switchBtn

  row.appendChild(label)
  row.appendChild(switchBtn)

  // ---- Target grade level selector, with the quiz as a small link
  // underneath rather than its own competing full-width button ----
  const gradeLevelRow = document.createElement("div")
  gradeLevelRow.style.display = "flex"
  gradeLevelRow.style.flexDirection = "column"
  gradeLevelRow.style.gap = "4px"
  gradeLevelRow.style.padding = "4px 2px"

  const gradeLevelTopRow = document.createElement("div")
  gradeLevelTopRow.style.display = "flex"
  gradeLevelTopRow.style.alignItems = "center"
  gradeLevelTopRow.style.justifyContent = "space-between"
  gradeLevelTopRow.style.gap = "12px"

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

  gradeLevelTopRow.appendChild(gradeLevelLabel)
  gradeLevelTopRow.appendChild(gradeLevelSelect)

  const quizLink = document.createElement("button")
  quizLink.textContent = "Not sure? Take the quiz"
  quizLink.style.alignSelf = "flex-start"
  quizLink.style.border = "none"
  quizLink.style.background = "none"
  quizLink.style.padding = "0"
  quizLink.style.fontSize = "12px"
  quizLink.style.color = tokens.accentTeal
  quizLink.style.textDecoration = "underline"
  quizLink.style.cursor = "pointer"

  quizLink.addEventListener("click", () => {
    // Close the menu panel first so it isn't sitting behind the modal
    // backdrop while the quiz is open.
    panel.style.display = "none"
    openQuizModal()
  })

  gradeLevelRow.appendChild(gradeLevelTopRow)
  gradeLevelRow.appendChild(quizLink)

  // ---- New: text length slider ----
  // Still just the same four fixed TEXT_LENGTH_OPTIONS from
  // lib/text-length.ts - the slider's integer value (0-3) is used
  // directly as an index into that array, so it's a different control
  // for picking one of the four options, not a new continuous value.
  const textLengthRow = document.createElement("div")
  textLengthRow.style.display = "flex"
  textLengthRow.style.flexDirection = "column"
  textLengthRow.style.gap = "6px"
  textLengthRow.style.padding = "4px 2px"

  const textLengthHeader = document.createElement("div")
  textLengthHeader.style.display = "flex"
  textLengthHeader.style.justifyContent = "space-between"

  const textLengthLabel = document.createElement("span")
  textLengthLabel.textContent = "Text Length"
  textLengthLabel.style.fontSize = "14px"
  textLengthLabel.style.color = tokens.readingText

  const textLengthValue = document.createElement("span")
  textLengthValue.style.fontSize = "12px"
  textLengthValue.style.color = tokens.captionText

  const textLengthSlider = document.createElement("input")
  textLengthSlider.type = "range"
  textLengthSlider.min = "0"
  textLengthSlider.max = String(TEXT_LENGTH_OPTIONS.length - 1)
  textLengthSlider.step = "1"
  textLengthSlider.style.width = "100%"
  textLengthSlider.style.cursor = "pointer"
  textLengthSlider.style.accentColor = tokens.accentTeal

  function syncTextLengthDisplay(index: number) {
    textLengthSlider.value = String(index)
    textLengthValue.textContent = TEXT_LENGTH_OPTIONS[index].label
  }

  const initialIndex = Math.max(
    0,
    TEXT_LENGTH_OPTIONS.findIndex((o) => o.value === targetLength)
  )
  syncTextLengthDisplay(initialIndex)

  textLengthSlider.addEventListener("input", () => {
    const index = Number(textLengthSlider.value)
    targetLength = TEXT_LENGTH_OPTIONS[index].value
    syncTextLengthDisplay(index)
    setTargetLength(targetLength)
    logEvent("target_length_changed", { targetLength })
  })

  textLengthHeader.appendChild(textLengthLabel)
  textLengthHeader.appendChild(textLengthValue)
  textLengthRow.appendChild(textLengthHeader)
  textLengthRow.appendChild(textLengthSlider)

  // ---- New: reading font control ----
  const fontRow = document.createElement("div")
  fontRow.style.display = "flex"
  fontRow.style.alignItems = "center"
  fontRow.style.justifyContent = "space-between"
  fontRow.style.gap = "12px"
  fontRow.style.padding = "4px 2px"

  const fontLabel = document.createElement("span")
  fontLabel.textContent = "Reading Font"
  fontLabel.style.fontSize = "14px"
  fontLabel.style.color = tokens.readingText

  const fontSelect = document.createElement("select")
  fontSelect.style.padding = "6px 10px"
  fontSelect.style.borderRadius = "20px"
  fontSelect.style.border = `1px solid ${tokens.captionText}`
  fontSelect.style.fontSize = "12px"
  fontSelect.style.cursor = "pointer"
  fontSelect.style.backgroundColor = "#FFFFFF"
  fontSelect.style.color = tokens.readingText

  FONT_OPTIONS.forEach((option) => {
    const fontOptionEl = document.createElement("option")
    fontOptionEl.value = option.value
    fontOptionEl.textContent = option.label
    if (option.value === currentReadingFont) fontOptionEl.selected = true
    fontSelect.appendChild(fontOptionEl)
  })

  fontSelect.addEventListener("change", () => {
    currentReadingFont = fontSelect.value as ReadingFont
    applyReadingFont(currentReadingFont)
    setReadingFont(currentReadingFont)
    logEvent("reading_font_changed", { readingFont: currentReadingFont })
  })

  fontRow.appendChild(fontLabel)
  fontRow.appendChild(fontSelect)

  // ---- New: text spacing control (letter spacing, word spacing, line
  // height) - four buttons rather than a slider/select, matching how the
  // toolbar popup version of this control looked before it moved here. ----
  const spacingRow = document.createElement("div")
  spacingRow.style.display = "flex"
  spacingRow.style.flexDirection = "column"
  spacingRow.style.gap = "6px"
  spacingRow.style.padding = "4px 2px"

  const spacingLabel = document.createElement("span")
  spacingLabel.textContent = "Text Spacing"
  spacingLabel.style.fontSize = "14px"
  spacingLabel.style.color = tokens.readingText

  const spacingButtonRow = document.createElement("div")
  spacingButtonRow.style.display = "flex"
  spacingButtonRow.style.gap = "6px"

  const spacingButtons: HTMLButtonElement[] = []

  function syncSpacingButtons() {
    spacingButtons.forEach((btn, i) => {
      const active = TEXT_SPACING_OPTIONS[i].value === currentTextSpacing
      btn.style.backgroundColor = active ? tokens.accentTeal : "#FFFFFF"
      btn.style.color = active ? "#FFFFFF" : tokens.readingText
      btn.style.borderColor = active ? tokens.accentTeal : tokens.captionText
    })
  }

  TEXT_SPACING_OPTIONS.forEach((option) => {
    const spacingBtn = document.createElement("button")
    spacingBtn.textContent = option.label
    spacingBtn.style.flex = "1"
    spacingBtn.style.padding = "6px 0"
    spacingBtn.style.borderRadius = "14px"
    spacingBtn.style.border = `1px solid ${tokens.captionText}`
    spacingBtn.style.backgroundColor = "#FFFFFF"
    spacingBtn.style.color = tokens.readingText
    spacingBtn.style.fontSize = "12px"
    spacingBtn.style.cursor = "pointer"
    spacingBtn.addEventListener("click", () => {
      currentTextSpacing = option.value
      applyTextSpacing(currentTextSpacing)
      setTextSpacing(currentTextSpacing)
      syncSpacingButtons()
      logEvent("text_spacing_changed", { textSpacing: currentTextSpacing })
    })
    spacingButtons.push(spacingBtn)
    spacingButtonRow.appendChild(spacingBtn)
  })

  syncSpacingButtons()

  spacingRow.appendChild(spacingLabel)
  spacingRow.appendChild(spacingButtonRow)

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

  // ---- Actions ----
  panel.appendChild(createSectionLabel("Actions"))
  panel.appendChild(simplifyAllBtn)

  panel.appendChild(createDivider())

  // ---- Preferences ----
  panel.appendChild(createSectionLabel("Preferences"))
  panel.appendChild(row)
  panel.appendChild(gradeLevelRow)
  panel.appendChild(textLengthRow)
  panel.appendChild(fontRow)
  panel.appendChild(spacingRow)

  // Research/dev tool, not something real end users need - only shown
  // when chrome.storage.local has devMode === true, which nothing sets
  // by default (see init()).
  if (devModeEnabled) {
    panel.appendChild(createDivider())
    panel.appendChild(createSectionLabel("Dev"))
    panel.appendChild(exportBtn)
  }

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
  // Same reasoning as the onboarding modal's backdrop - needs to stay
  // above the Aa button/panel (2147483647) or it stops covering them.
  // injectQuizModal() runs after injectMenu() in init(), so this
  // backdrop is appended later in the DOM and wins the max-z-index tie.
  backdrop.style.zIndex = "2147483647"
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

// Nothing sets this key by default, so devModeEnabled is false - and the
// "Export Session Log" button absent - for every real user. See the
// bottom of this file for how to flip it on locally for testing.
async function isDevModeEnabled(): Promise<boolean> {
  const stored = await chrome.storage.local.get("devMode")
  return stored.devMode === true
}

// Loads the stored grade level and text length (set by the options-page
// assessment, the in-page quiz, or a prior dropdown change) before
// building the menu, so both dropdowns' initial selections are correct
// instead of always starting at the defaults.
async function init() {
  targetGradeLevel = await getTargetGradeLevel()
  targetLength = await getTargetLength()
  currentTextSpacing = await getTextSpacing()
  currentReadingFont = await getReadingFont()
  fontOverrideEnabled = await getFontOverrideEnabled()
  hasSeenOnboarding = await getHasSeenOnboarding()
  const devModeEnabled = await isDevModeEnabled()
  loadReadingFont()
  injectBadgeStyles()
  injectSimplifiedContentStyles()
  injectReaderStyles()
  injectMenu(devModeEnabled)
  injectQuizModal()
  // Lives here permanently, positioned via attachBadgeTo() rather than
  // ever being re-parented into whatever paragraph it's currently
  // pointing at - see attachBadgeTo for why.
  document.body.appendChild(badge)
  document.body.appendChild(explainBadge)
  document.body.appendChild(explainCard)

  activateBadgeClickHandler()
  activateExplainBadgeClickHandler()
  activateSelectionTrigger()
  activateScrollReposition()
  activateDwellDetection()

  // Text spacing and reading font used to apply from a separate,
  // independent top-level block gated only by isSensitivePage() - not
  // isProbablyReaderable(). That meant a font picked in the Aa menu
  // silently followed the user to every non-sensitive page, including
  // ones where the Aa menu (and everything else init() sets up) never
  // even appears, e.g. Google search results. Applying them here
  // instead means they're on exactly the same footing as the badge:
  // both only ever run inside init(), and init() only ever runs where
  // this file's activation gate below decided the page is eligible.
  applyTextSpacing(currentTextSpacing)
  applyReadingFont(currentReadingFont)

  // Scoped to this tab's activation, same reasoning as above - a page
  // that never activated has no listener updating anything on it.
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return
    if (TEXT_SPACING_STORAGE_KEY in changes) {
      applyTextSpacing(changes[TEXT_SPACING_STORAGE_KEY].newValue ?? DEFAULT_TEXT_SPACING)
    }
    if (READING_FONT_STORAGE_KEY in changes) {
      currentReadingFont = changes[READING_FONT_STORAGE_KEY].newValue ?? DEFAULT_READING_FONT
      applyReadingFont(currentReadingFont)
    }
    if (FONT_OVERRIDE_ENABLED_STORAGE_KEY in changes) {
      fontOverrideEnabled = changes[FONT_OVERRIDE_ENABLED_STORAGE_KEY].newValue ?? DEFAULT_FONT_OVERRIDE_ENABLED
      applyReadingFont(currentReadingFont)
    }
  })

  maybeShowOnboardingModal()
}

// True once init() has actually run for this page load - via either
// path below (automatic or manual). Guards against the manual-activate
// message handler re-running init() a second time on a page that
// already auto-activated, and against a second manual click doing the
// same.
let hasActivated = false

// isSensitivePage() is checked first and takes priority over
// isProbablyReaderable() below - confirmed directly on real bank
// homepages (Bank of America, Wells Fargo) that isProbablyReaderable
// returns true there: a bank's marketing/disclosure copy is often
// dense enough to read as "an article" to a pure text-density
// heuristic, even though the page's real purpose is a login form.
// isProbablyReaderable answers "does this look like an article" -
// isSensitivePage answers "is this safe to run on at all" - those are
// different questions, and passing the first one is never enough on
// its own to activate anything here.
//
// continueReadingMode is true exactly once: on the page load immediately
// after the user clicked a Prev/Next link inside Reading Mode on the
// previous page (see buildPaginationLinkEl/READING_MODE_CONTINUE_KEY).
// Once someone is actually in Reading Mode, staying in it across a
// "next page" navigation is the whole point of offering that link at
// all - a plain page load landing back in the ordinary view would make
// every click feel like it exits Reading Mode. isSensitivePage() still
// applies unconditionally even here; isProbablyReaderable() and the
// auto-activate setting don't, since this is a specific continuation of
// something the user already explicitly turned on, not a fresh page's
// own automatic activation.
async function evaluateAutomaticActivation(continueReadingMode: boolean) {
  if (isSensitivePage()) {
    logEvent("page_skipped_sensitive_page", {})
    return
  }

  if (!continueReadingMode) {
    if (!isProbablyReaderable(document)) {
      // The same lightweight heuristic Firefox uses to decide whether to
      // show its own Reader View icon at all - a fast check of text
      // density and node count, not a full Readability.parse(). Now that
      // the extension runs on every site (not just Wikipedia), this
      // keeps it genuinely inactive on non-article pages (search
      // results, settings/dashboard UIs, etc.) instead of just hiding
      // the UI: nothing here runs at all - no observer, no selection
      // listener, no menu button, no font/spacing override - unless the
      // page looks like it actually has article content.
      logEvent("page_skipped_not_readerable", {})
      return
    }

    // Settings > "Auto-activate on readable pages" - default on, matching
    // the only behavior that existed before this setting did. Off means
    // the page still passed every eligibility check above, but init()
    // only runs if the user explicitly asks for it via the popup's
    // manual-activate button (see the message handler below).
    const autoActivateEnabled = await getAutoActivateEnabled()
    if (!autoActivateEnabled) {
      logEvent("page_skipped_auto_activate_disabled", {})
      return
    }
  }

  hasActivated = true
  await init()

  if (continueReadingMode) {
    logEvent("reading_mode_continued", {})
    // No-ops safely (logs reading_mode_error, leaves the switch off) if
    // this particular page turns out not to be extractable after all -
    // isProbablyReaderable was skipped above specifically to let Reading
    // Mode keep going across a "next page" click, but extraction can
    // still fail on a genuinely unreadable destination.
    setReadingMode(true)
  }
}

// Read (and immediately clear) exactly once per page load, before any
// activation gate runs - so a destination page that turns out not to
// activate at all (isSensitivePage, fails isProbablyReaderable with no
// continuation in play, etc.) never leaves this flag sitting around to
// wrongly auto-resume Reading Mode on some later, unrelated navigation.
const shouldContinueReadingMode = sessionStorage.getItem(READING_MODE_CONTINUE_KEY) === "1"
sessionStorage.removeItem(READING_MODE_CONTINUE_KEY)

evaluateAutomaticActivation(shouldContinueReadingMode)

// Manual activation from the popup's Home tab (see popup.tsx) - the
// only way to turn Lucent Reader on for a specific page when
// auto-activate is off, or when a page failed isProbablyReaderable but
// the user wants it anyway. isSensitivePage() is still enforced here
// unconditionally - a manual request is an explicit user action, but
// it can never override the one hard safety gate in this file.
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== MANUAL_ACTIVATE_MESSAGE_TYPE) return false

  if (isSensitivePage()) {
    const response: ManualActivateResponse = { ok: false, reason: "sensitive_page" }
    sendResponse(response)
    return true
  }

  if (hasActivated) {
    const response: ManualActivateResponse = { ok: true, alreadyActive: true }
    sendResponse(response)
    return true
  }

  hasActivated = true
  logEvent("manual_activate", {})
  init()
  const response: ManualActivateResponse = { ok: true, alreadyActive: false }
  sendResponse(response)
  return true
})