// Shared source of truth for the user's target reading level. Both the
// options-page assessment and the in-page grade-level dropdown read/write
// the same chrome.storage.local value (same pattern as install-id.ts), so
// a level picked either way stays in sync everywhere.

export const VALID_GRADE_LEVELS = [3, 5, 8, 10] as const
export const DEFAULT_GRADE_LEVEL = 5

const STORAGE_KEY = "targetGradeLevel"

export async function getTargetGradeLevel(): Promise<number> {
  const stored = await chrome.storage.local.get(STORAGE_KEY)
  return stored[STORAGE_KEY] ?? DEFAULT_GRADE_LEVEL
}

export async function setTargetGradeLevel(level: number): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEY]: level })
}

export type AssessmentResponse = "too_easy" | "just_right" | "too_hard"

export interface AssessmentPassage {
  grade: number
  text: string
}

// Three short passages spanning the low/mid/high end of the levels we
// actually offer. Each one is written to *read* at roughly its labeled
// grade level, not just be about a topic of that difficulty.
export const ASSESSMENT_PASSAGES: AssessmentPassage[] = [
  {
    grade: 3,
    text: "The old dog liked to nap in the sun. Every day, she found a warm spot by the window. When the sun moved, she moved too."
  },
  {
    grade: 6,
    text: "Coral reefs form when tiny animals called polyps build hard skeletons around themselves. Over many years, thousands of these skeletons connect and grow into the large reef structures we see today."
  },
  {
    grade: 9,
    text: "Economic inflation refers to a sustained rise in the general price level of goods and services, which gradually erodes purchasing power and often prompts central banks to adjust monetary policy in response."
  }
]

// Turns three "too easy / just right / too hard" answers into a single
// target grade level. Each answer nudges an estimate away from that
// passage's own grade (easy -> they can handle something harder, hard ->
// they need something easier), then we average the three estimates and
// snap to the nearest level we actually support, since that's the only
// thing the simplify prompt and the manual dropdown know how to use.
export function computeTargetGradeLevel(
  responses: AssessmentResponse[]
): number {
  const estimates = responses.map((response, i) => {
    const passageGrade = ASSESSMENT_PASSAGES[i].grade
    if (response === "too_easy") return passageGrade + 3
    if (response === "too_hard") return passageGrade - 3
    return passageGrade
  })

  const average = estimates.reduce((sum, val) => sum + val, 0) / estimates.length

  return VALID_GRADE_LEVELS.reduce((closest, level) =>
    Math.abs(level - average) < Math.abs(closest - average) ? level : closest
  )
}
