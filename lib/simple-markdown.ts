// A tiny, safe subset of markdown for rendering simplified paragraph
// output: bold key terms, bullet lists, and short paragraphs - nothing
// else. Builds DOM nodes directly (createElement/createTextNode) rather
// than ever passing the model's text through innerHTML. The text here
// originates from an LLM prompt that itself embeds untrusted webpage
// content, so even though it's our own backend generating the response,
// treating model output as raw HTML would be a real (if indirect)
// injection surface - building nodes by hand makes that impossible
// regardless of what comes back.

const BULLET_PATTERN = /^[-*•]\s+(.*)$/

function appendInlineBold(parent: HTMLElement, text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  for (const part of parts) {
    if (!part) continue
    const boldMatch = part.match(/^\*\*([^*]+)\*\*$/)
    if (boldMatch) {
      const strong = document.createElement("strong")
      strong.textContent = boldMatch[1]
      parent.appendChild(strong)
    } else {
      parent.appendChild(document.createTextNode(part))
    }
  }
}

// Splits on blank lines into blocks, then within each block groups
// consecutive bullet lines into a single <ul> and consecutive prose
// lines into a single <p> - so a block that's pure prose becomes one
// paragraph, a block that's pure bullets becomes one list, and the rare
// block mixing both becomes a short run of each in order.
export function renderSimpleMarkdown(container: HTMLElement, text: string): void {
  container.innerHTML = ""

  const blocks = text
    .split(/\n\s*\n/)
    .map((b) => b.trim())
    .filter(Boolean)

  if (blocks.length === 0) {
    container.appendChild(document.createElement("p"))
    return
  }

  for (const block of blocks) {
    const lines = block
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)

    let i = 0
    while (i < lines.length) {
      if (BULLET_PATTERN.test(lines[i])) {
        const ul = document.createElement("ul")
        while (i < lines.length) {
          const match = lines[i].match(BULLET_PATTERN)
          if (!match) break
          const li = document.createElement("li")
          appendInlineBold(li, match[1])
          ul.appendChild(li)
          i++
        }
        container.appendChild(ul)
      } else {
        const proseLines: string[] = []
        while (i < lines.length && !BULLET_PATTERN.test(lines[i])) {
          proseLines.push(lines[i])
          i++
        }
        const p = document.createElement("p")
        appendInlineBold(p, proseLines.join(" "))
        container.appendChild(p)
      }
    }
  }
}
