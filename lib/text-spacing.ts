// Shared source of truth for the page-content text spacing control
// (letter spacing, word spacing, line height). Same chrome.storage.local
// pattern as text-length.ts - four discrete levels rather than a
// continuous slider, each mapping directly to a fixed set of CSS values
// applied by contents/struggle-detector.ts, so there's no ambiguous
// in-between state to translate into CSS.

export const TEXT_SPACING_OPTIONS = [
  {
    value: "off",
    label: "Off",
    letterSpacing: "normal",
    wordSpacing: "normal",
    lineHeight: "normal"
  },
  {
    value: "low",
    label: "Low",
    letterSpacing: "0.03em",
    wordSpacing: "0.08em",
    lineHeight: "1.5"
  },
  {
    value: "medium",
    label: "Medium",
    letterSpacing: "0.06em",
    wordSpacing: "0.16em",
    lineHeight: "1.75"
  },
  {
    value: "high",
    label: "High",
    letterSpacing: "0.12em",
    wordSpacing: "0.25em",
    lineHeight: "2"
  }
] as const

export type TextSpacing = (typeof TEXT_SPACING_OPTIONS)[number]["value"]

export const DEFAULT_TEXT_SPACING: TextSpacing = "off"

export const TEXT_SPACING_STORAGE_KEY = "textSpacing"

export async function getTextSpacing(): Promise<TextSpacing> {
  const stored = await chrome.storage.local.get(TEXT_SPACING_STORAGE_KEY)
  return stored[TEXT_SPACING_STORAGE_KEY] ?? DEFAULT_TEXT_SPACING
}

export async function setTextSpacing(spacing: TextSpacing): Promise<void> {
  await chrome.storage.local.set({ [TEXT_SPACING_STORAGE_KEY]: spacing })
}
