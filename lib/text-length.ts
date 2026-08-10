// Shared source of truth for the desired output length of simplified
// text. Same chrome.storage.local pattern as reading-level.ts, but kept
// as its own module since length and grade level are independent
// settings that just happen to both flow into the same /simplify call.
//
// Four discrete options rather than a slider - each one maps directly to
// a specific instruction in the backend prompt (see LENGTH_INSTRUCTIONS
// in backend/main.py), so there's no ambiguous "60%" value to translate.

export const TEXT_LENGTH_OPTIONS = [
  { value: "much_shorter", label: "Much Shorter" },
  { value: "shorter", label: "Shorter" },
  { value: "same", label: "Same Length" },
  { value: "more_detail", label: "More Detail" }
] as const

export type TextLength = (typeof TEXT_LENGTH_OPTIONS)[number]["value"]

export const DEFAULT_TEXT_LENGTH: TextLength = "same"

const STORAGE_KEY = "targetLength"

export async function getTargetLength(): Promise<TextLength> {
  const stored = await chrome.storage.local.get(STORAGE_KEY)
  return stored[STORAGE_KEY] ?? DEFAULT_TEXT_LENGTH
}

export async function setTargetLength(length: TextLength): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEY]: length })
}
