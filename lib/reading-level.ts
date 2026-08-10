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

function nearestValidGradeLevel(value: number): number {
  return VALID_GRADE_LEVELS.reduce((closest, level) =>
    Math.abs(level - value) < Math.abs(closest - value) ? level : closest
  )
}

// User-facing names for each level - this app is for people with
// dyslexia, so comparing them to a school grade isn't good framing. The
// numbers above are still what drive the simplify prompt and the storage
// key; this is purely a display-layer lookup.
const TIER_LABELS: Record<number, string> = {
  3: "Very Simple",
  5: "Simple",
  8: "Comfortable",
  10: "Detailed"
}

export function getTierLabel(level: number): string {
  return TIER_LABELS[level] ?? TIER_LABELS[nearestValidGradeLevel(level)]
}

export type AssessmentResponse = "too_easy" | "just_right" | "too_hard"

export interface AssessmentPassage {
  grade: number
  text: string
}

// Fine-grained difficulty scale used only during the adaptive quiz - more
// granular than VALID_GRADE_LEVELS above, so there's room to narrow in on
// someone's real comfort level over a few questions before snapping the
// final answer to the nearest level we actually offer. Two passages per
// rung so a "just right" confirming check (see applyQuizAnswer) never
// re-shows a passage the person already read.
const ADAPTIVE_TIER_GRADES = [2, 4, 6, 8, 10, 12] as const

export const PASSAGE_POOL: AssessmentPassage[] = [
  {
    grade: 2,
    text: "The old dog liked to nap in the sun. Every day, she found a warm spot by the window. When the sun moved, she moved too."
  },
  {
    grade: 2,
    text: "Ben has a small red kite. He likes to fly it in the park. On windy days, the kite goes very high in the sky."
  },
  {
    grade: 4,
    text: "Beavers are known for building dams across rivers and streams. They use branches, mud, and rocks to build these dams, which create ponds where the beavers can build their homes safely."
  },
  {
    grade: 4,
    text: "Volcanoes form when hot melted rock, called magma, pushes up through cracks in the Earth's surface. When a volcano erupts, this magma flows out as lava, which can travel a long way before it cools and turns hard."
  },
  {
    grade: 6,
    text: "Coral reefs form when tiny animals called polyps build hard skeletons around themselves. Over many years, thousands of these skeletons connect and grow into the large reef structures we see today."
  },
  {
    grade: 6,
    text: "The water cycle describes how water moves between the ocean, the sky, and the land. Heat from the sun causes water to evaporate into vapor, which later cools, forms clouds, and falls back down as rain or snow."
  },
  {
    grade: 8,
    text: "Photosynthesis allows plants to convert light energy into chemical energy stored in glucose. This process takes place mainly in the chloroplasts of plant cells, where a pigment called chlorophyll absorbs sunlight and helps convert carbon dioxide and water into usable energy."
  },
  {
    grade: 8,
    text: "The immune system defends the body against harmful invaders such as bacteria and viruses. Specialized cells called lymphocytes identify these invaders and coordinate a targeted response, often creating a lasting memory that allows for a faster reaction if the same invader appears again."
  },
  {
    grade: 10,
    text: "Economic inflation refers to a sustained rise in the general price level of goods and services, which gradually erodes purchasing power and often prompts central banks to adjust monetary policy in response."
  },
  {
    grade: 10,
    text: "Cognitive dissonance is the psychological discomfort experienced when a person holds two or more contradictory beliefs, values, or attitudes at once, often leading them to rationalize or minimize the inconsistency to restore a sense of internal consistency."
  },
  {
    grade: 12,
    text: "Quantum entanglement describes a phenomenon in which two or more particles become correlated so that the quantum state of each cannot be described independently of the others, even when separated by a considerable distance - a property Einstein referred to as 'spooky action at a distance.'"
  },
  {
    grade: 12,
    text: "Judicial review is the constitutional mechanism by which courts assess whether legislative or executive actions comply with the constitution. Although not explicitly enumerated in the U.S. Constitution, this power was firmly established through the 1803 case Marbury v. Madison and has since become a cornerstone of American constitutional law."
  }
]

export const MAX_QUIZ_QUESTIONS = 6

// Index into ADAPTIVE_TIER_GRADES. With 6 rungs there's no single exact
// midpoint, so this picks the lower-middle one (grade 6) - close to the
// old fixed default of grade 5, and a mild bias toward starting easier
// rather than harder fits a tool built for people who struggle to read.
const START_TIER_INDEX = 2

export interface QuizState {
  tierIndex: number
  low: number
  high: number
  justRightStreak: number
  usedPassageTexts: string[]
  history: { grade: number; response: AssessmentResponse }[]
}

export function startQuizState(): QuizState {
  return {
    tierIndex: START_TIER_INDEX,
    low: 0,
    high: ADAPTIVE_TIER_GRADES.length - 1,
    justRightStreak: 0,
    usedPassageTexts: [],
    history: []
  }
}

// Picks an unshown passage at the given tier. Falls back to the closest
// unshown passage of any tier if this tier's two passages are both
// already used (possible on a long, back-and-forth quiz), and only
// repeats a passage outright if every single one in the pool has been
// shown already - which can't happen within MAX_QUIZ_QUESTIONS since the
// pool has 12 passages and the quiz caps at 6.
export function pickPassageForTier(
  tierIndex: number,
  usedPassageTexts: string[]
): AssessmentPassage {
  const targetGrade = ADAPTIVE_TIER_GRADES[tierIndex]
  const atTier = PASSAGE_POOL.filter(
    (p) => p.grade === targetGrade && !usedPassageTexts.includes(p.text)
  )
  if (atTier.length > 0) return atTier[0]

  const unused = PASSAGE_POOL.filter((p) => !usedPassageTexts.includes(p.text))
  const pool = unused.length > 0 ? unused : PASSAGE_POOL

  return pool.reduce((closest, p) =>
    Math.abs(p.grade - targetGrade) < Math.abs(closest.grade - targetGrade) ? p : closest
  )
}

// Applies one answer to the quiz state. "Too easy"/"too hard" narrow the
// [low, high] range of plausible tiers directly (classic binary search).
// "Just right" leaves the range alone and instead builds a streak, since
// one "just right" isn't enough to be confident on its own - it just
// triggers a confirming check at the same tier - but two in a row is.
export function applyQuizAnswer(
  state: QuizState,
  passage: AssessmentPassage,
  response: AssessmentResponse
): QuizState {
  const { tierIndex, low, high } = state
  let newLow = low
  let newHigh = high
  let newTierIndex = tierIndex
  let newStreak = 0

  if (response === "too_easy") {
    newLow = Math.max(low, tierIndex + 1)
    newTierIndex = Math.min(high, tierIndex + 1)
  } else if (response === "too_hard") {
    newHigh = Math.min(high, tierIndex - 1)
    newTierIndex = Math.max(low, tierIndex - 1)
  } else {
    newStreak = state.justRightStreak + 1
  }

  return {
    tierIndex: newTierIndex,
    low: newLow,
    high: newHigh,
    justRightStreak: newStreak,
    usedPassageTexts: [...state.usedPassageTexts, passage.text],
    history: [...state.history, { grade: passage.grade, response }]
  }
}

// True once we're confident enough to stop, even under the hard cap:
// either the plausible range has narrowed to a single tier (an easy/hard
// answer collapsed it), or we've seen two "just right" answers in a row.
export function isQuizConfident(state: QuizState): boolean {
  if (state.low >= state.high) return true
  if (state.justRightStreak >= 2) return true
  return false
}

export function finalizeQuizResult(state: QuizState): number {
  return nearestValidGradeLevel(ADAPTIVE_TIER_GRADES[state.tierIndex])
}
