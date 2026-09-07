import { describe, expect, it } from "vitest"
import { formatMaterialTitle } from "./Library"

describe("Library presentation", () => {
  it("formats storage-like filenames without changing meaningful titles", () => {
    expect(formatMaterialTitle("fresh_generalization_notes")).toBe("Fresh Generalization Notes")
    expect(formatMaterialTitle("final_holdout_pendulum.pdf")).toBe("Final Holdout Pendulum")
    expect(formatMaterialTitle("Genetics Lecture 33")).toBe("Genetics Lecture 33")
  })
})
