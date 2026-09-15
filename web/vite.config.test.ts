import { describe, expect, it } from "vitest"

import { validateProductionApiOrigin } from "./vite.config"

describe("production frontend configuration", () => {
  it("accepts a plain HTTPS API origin", () => {
    expect(validateProductionApiOrigin("https://api.lucentreader.com/"))
      .toBe("https://api.lucentreader.com")
  })

  it.each([
    undefined,
    "http://api.lucentreader.com",
    "https://api.lucentreader.com/path",
    "https://user:secret@api.lucentreader.com",
    "https://api.lucentreader.com?debug=true"
  ])("rejects an unsafe production API address: %s", (value) => {
    expect(() => validateProductionApiOrigin(value)).toThrow()
  })
})
