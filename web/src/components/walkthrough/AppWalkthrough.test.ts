import { describe, expect, it } from "vitest"
import { CHROME_EXTENSION_URL } from "../../lib/extension"
import { APP_WALKTHROUGH_STEPS, shouldOpenAppWalkthrough } from "./AppWalkthrough"

describe("AppWalkthrough", () => {
  it("forces the tour for a newly created account", () => {
    expect(shouldOpenAppWalkthrough("?welcome=1", "1")).toBe(true)
  })

  it("preserves the existing first-browser-visit behavior", () => {
    expect(shouldOpenAppWalkthrough("", null)).toBe(true)
    expect(shouldOpenAppWalkthrough("", "1")).toBe(false)
  })

  it("gives new learners a direct path to the Chrome extension", () => {
    expect(APP_WALKTHROUGH_STEPS).toContainEqual(expect.objectContaining({
      title: "Bring Lucent into Chrome",
      cta: { label: "Add to Chrome", href: CHROME_EXTENSION_URL },
    }))
  })
})
