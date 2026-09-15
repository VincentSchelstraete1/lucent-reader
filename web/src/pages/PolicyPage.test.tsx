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
    expect(html).toContain("permanently delete your account")
    expect(html).toContain("Account export is not yet self-service")
    expect(html).toContain("Effective September 14, 2026")
    expect(html).toContain("7 days on Hobby or 14 days on Pro")
    expect(html).toContain("3 days on Hobby or 7 days on Pro")
    expect(html).toContain("up to 30 days")
    expect(html).toContain("zero-day data retention")
    expect(html).not.toContain("must approve final retention periods")
  })

  it("states the core service and upload conditions", () => {
    const html = renderToStaticMarkup(<MemoryRouter><TermsPage /></MemoryRouter>)
    expect(html).toContain("Only upload or save material you are allowed to use")
    expect(html).toContain("may be incomplete or incorrect")
  })
})
