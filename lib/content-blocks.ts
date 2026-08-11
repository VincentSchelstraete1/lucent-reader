// Shared "what counts as a paragraph" detection, used everywhere the
// content scripts used to hardcode document.querySelectorAll("p") or
// closest("p"): dwell detection, highlight-to-badge, and "Simplify
// Entire Page". Wikipedia's article body is all <p> tags, but plenty of
// modern sites render their body text in <div>s (or occasionally a
// block-styled <span>) instead, so this broadens matching beyond <p>
// while trying hard not to pick up nav links, buttons, ad slots, or
// stray short strings.

// Tags that can independently qualify as a content block. SPAN is
// deliberately not in this set - see isStructural() below for why it's
// handled as a special case instead of being listed here outright.
const STRUCTURAL_TAGS = new Set([
  "P",
  "DIV",
  "SECTION",
  "ARTICLE",
  "LI",
  "TD",
  "TH",
  "BLOCKQUOTE",
  "FIGCAPTION",
  "DT",
  "DD"
])

// Elements whose text should never count toward a block, and whose
// subtree should never be searched for nested blocks either - either
// because it's not prose (script/style/svg/canvas/iframe), or because
// it's an interactive control rather than content (button/select/
// textarea/label/input), which is the "tiny label/button text" case.
const NON_CONTENT_TAGS = new Set([
  "NAV",
  "HEADER",
  "FOOTER",
  "ASIDE",
  "SCRIPT",
  "STYLE",
  "NOSCRIPT",
  "TEMPLATE",
  "SVG",
  "CANVAS",
  "IFRAME",
  "BUTTON",
  "SELECT",
  "TEXTAREA",
  "LABEL",
  "INPUT"
])

const NON_CONTENT_ROLES = new Set([
  "navigation",
  "banner",
  "contentinfo",
  "complementary",
  "menu",
  "menubar",
  "toolbar",
  "search",
  "form"
])

// Word-level tokens (after splitting on non-alphanumerics and camelCase
// boundaries), not raw substrings - a raw-substring check on "ad" alone
// would false-positive on ordinary words like "gradient", "shadow", or
// "header", which are common in real class names.
const NON_CONTENT_CLASS_TOKENS = new Set([
  "nav",
  "navbar",
  "navigation",
  "sidebar",
  "menu",
  "submenu",
  "ad",
  "ads",
  "footer"
])

const MIN_TEXT_LENGTH = 60

function classTokens(el: Element): string[] {
  const raw = `${String((el as HTMLElement).className || "")} ${el.id || ""}`
  const spaced = raw.replace(/([a-z0-9])([A-Z])/g, "$1 $2")
  return spaced.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean)
}

function hasNonContentClassToken(el: Element): boolean {
  return classTokens(el).some((token) => NON_CONTENT_CLASS_TOKENS.has(token))
}

// SPAN is normally inline text formatting (bold/italic/emphasis inside
// a sentence), and treating every <span> as its own independent block
// would fragment ordinary paragraphs into lots of tiny, non-qualifying
// pieces. Some component libraries do render real paragraph-level text
// in a <span> styled as a block via CSS, though - so a span only counts
// as structural when it's actually laid out as one.
function isStructural(el: Element): boolean {
  if (STRUCTURAL_TAGS.has(el.tagName)) return true
  if (el.tagName !== "SPAN") return false
  const display = getComputedStyle(el as HTMLElement).display
  return (
    display !== "" &&
    display !== "none" &&
    display !== "contents" &&
    !display.startsWith("inline")
  )
}

// Tag (<nav>/<header>/<footer>/<aside>) and aria/role exclusions are
// semantically unambiguous, so they're checked all the way up the
// ancestor chain - being anywhere inside a real <nav> always disqualifies
// a block. Class/id token matching is intentionally NOT checked on
// <html> or <body>: real sites (Wikipedia's Vector skin is a good
// example) put page-wide feature-flag/theme classes there - e.g.
// "vector-feature-main-menu-pinned-disabled" - that contain a "menu" or
// "nav" token without meaning "this page is a menu." Checking those two
// root elements would falsely exclude the entire page.
function isExcluded(el: Element): boolean {
  for (let node: Element | null = el; node; node = node.parentElement) {
    if (NON_CONTENT_TAGS.has(node.tagName)) return true
    const role = node.getAttribute("role")
    if (role && NON_CONTENT_ROLES.has(role.toLowerCase())) return true
    if (node.getAttribute("aria-hidden") === "true") return true
    if (node.tagName !== "HTML" && node.tagName !== "BODY" && hasNonContentClassToken(node)) {
      return true
    }
  }
  return false
}

function isVisible(el: HTMLElement): boolean {
  if (el.hidden) return false
  return el.getClientRects().length > 0
}

// Text contributed directly by this element: its own text nodes, plus
// text from inline formatting descendants (isStructural() === false),
// but NOT text belonging to a nested structural descendant - that
// descendant is evaluated as its own independent candidate instead, so
// counting its text here too would double-count the same words on both
// the container and its child.
function ownText(el: Element): string {
  let text = ""
  for (const child of Array.from(el.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) {
      text += child.textContent ?? ""
    } else if (child.nodeType === Node.ELEMENT_NODE) {
      const childEl = child as Element
      if (NON_CONTENT_TAGS.has(childEl.tagName)) continue
      if (isStructural(childEl)) continue
      text += ownText(childEl)
    }
  }
  return text.trim()
}

function isQualifyingBlock(el: Element): el is HTMLElement {
  if (!(el instanceof HTMLElement)) return false
  if (!isStructural(el)) return false
  if (isExcluded(el)) return false
  if (!isVisible(el)) return false
  return ownText(el).length >= MIN_TEXT_LENGTH
}

// Replacement for document.querySelectorAll("p") / readerRoot.querySelectorAll("p").
export function getContentBlocks(root: ParentNode = document): HTMLElement[] {
  const rootEl = root instanceof Document ? root.body : (root as Element | null)
  if (!rootEl) return []

  const results: HTMLElement[] = []

  function walk(el: Element) {
    if (NON_CONTENT_TAGS.has(el.tagName)) return
    const role = el.getAttribute("role")
    if (role && NON_CONTENT_ROLES.has(role.toLowerCase())) return
    if (el.getAttribute("aria-hidden") === "true") return
    if (el.tagName !== "HTML" && el.tagName !== "BODY" && hasNonContentClassToken(el)) return

    if (isQualifyingBlock(el)) results.push(el)

    for (const child of Array.from(el.children)) walk(child)
  }

  walk(rootEl)

  // ownText() above already keeps a container's own qualification
  // decision independent of any qualifying descendant's text, but the
  // rest of the app (getTextSpan, simplifyParagraph) reads the full
  // .textContent of whatever block it's given - which, for a container,
  // includes its descendants' text too. So if both a container and a
  // descendant independently qualified, simplifying both would run the
  // descendant's text through twice and nest one badge/revert-button
  // inside the other. Keep only the innermost match in that case.
  return results.filter(
    (el) => !results.some((other) => other !== el && el.contains(other))
  )
}

// Replacement for element.closest("p") when locating the content block
// that contains a given node (e.g. the user's text selection anchor).
export function findContentBlock(node: Node | null): HTMLElement | null {
  let el: Element | null =
    node instanceof Element ? node : (node?.parentElement ?? null)

  while (el) {
    if (isQualifyingBlock(el)) return el
    el = el.parentElement
  }
  return null
}
