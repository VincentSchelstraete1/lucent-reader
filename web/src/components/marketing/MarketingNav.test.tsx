import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { CHROME_EXTENSION_URL } from "../../lib/extension"
import { MarketingNav } from "./MarketingNav"

describe("MarketingNav", () => {
  it("links to the official Chrome extension listing", () => {
    const html = renderToStaticMarkup(<MemoryRouter><MarketingNav /></MemoryRouter>)

    expect(html).toContain(CHROME_EXTENSION_URL)
    expect(html).toContain("Chrome extension")
    expect(html).toContain('target="_blank"')
  })
})
