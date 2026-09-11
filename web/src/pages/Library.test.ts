import { describe, expect, it } from "vitest"
import { formatMaterialTitle, materialAvailableForView } from "./Library"

describe("Library presentation", () => {
  it("formats storage-like filenames without changing meaningful titles", () => {
    expect(formatMaterialTitle("fresh_generalization_notes")).toBe("Fresh Generalization Notes")
    expect(formatMaterialTitle("final_holdout_pendulum.pdf")).toBe("Final Holdout Pendulum")
    expect(formatMaterialTitle("Genetics Lecture 33")).toBe("Genetics Lecture 33")
  })

  it("shows every material with notes in Learn mode", () => {
    expect(materialAvailableForView("learn", true, 0)).toBe(true)
    expect(materialAvailableForView("learn", false, 0)).toBe(false)
  })

  it("keeps mode-specific availability for flashcards and quizzes", () => {
    expect(materialAvailableForView("flashcards", true, 0)).toBe(true)
    expect(materialAvailableForView("flashcards", false, 0)).toBe(false)
    expect(materialAvailableForView("quiz", true, 1)).toBe(true)
    expect(materialAvailableForView("quiz", true, 0)).toBe(false)
  })
})
