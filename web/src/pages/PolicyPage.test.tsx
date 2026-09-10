import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { MemoryRouter } from "react-router-dom"
import { PrivacyPage, TermsPage } from "./PolicyPage"

describe("public policy pages", () => {
  it("discloses stored learning data and external provider processing", () => {
    const html = renderToStaticMarkup(<MemoryRouter><PrivacyPage /></MemoryRouter>)
    expect(html).toContain("Anthropic")
    expect(html).toContain("Voyage")
    expect(html).toContain("learning-session state")
    expect(html).toContain("not yet self-service")
  })

  it("states the core service and upload conditions", () => {
    const html = renderToStaticMarkup(<MemoryRouter><TermsPage /></MemoryRouter>)
    expect(html).toContain("Only upload or save material you are allowed to use")
    expect(html).toContain("may be incomplete or incorrect")
  })
})
