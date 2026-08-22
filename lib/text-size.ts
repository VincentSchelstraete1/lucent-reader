// Reading-mode font size, as a percentage of its normal size - same
// chrome.storage.local pattern as text-spacing.ts, but a clamped numeric
// value (stepped by the A-/A+ buttons) rather than a fixed set of levels,
// since "100%" is itself the value shown in the UI.

export const MIN_TEXT_SIZE_PERCENT = 80
export const MAX_TEXT_SIZE_PERCENT = 150
export const TEXT_SIZE_STEP = 10

export const DEFAULT_TEXT_SIZE_PERCENT = 100

// Preset options for the compact Text Size dropdown in the Reading
// Controls bar - the expanded panel's A-/A+ steppers still move by
// TEXT_SIZE_STEP between arbitrary values in [MIN,MAX], these are just a
// fixed set of common values for the quick dropdown.
export const TEXT_SIZE_PRESETS = [80, 90, 100, 110, 125, 150] as const

export const TEXT_SIZE_STORAGE_KEY = "textSizePercent"

export async function getTextSizePercent(): Promise<number> {
  const stored = await chrome.storage.local.get(TEXT_SIZE_STORAGE_KEY)
  return stored[TEXT_SIZE_STORAGE_KEY] ?? DEFAULT_TEXT_SIZE_PERCENT
}

export async function setTextSizePercent(percent: number): Promise<void> {
  const clamped = Math.min(MAX_TEXT_SIZE_PERCENT, Math.max(MIN_TEXT_SIZE_PERCENT, percent))
  await chrome.storage.local.set({ [TEXT_SIZE_STORAGE_KEY]: clamped })
}
