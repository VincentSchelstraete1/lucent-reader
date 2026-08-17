// Two independent, storage-backed toggles surfaced in the popup's
// Settings tab. Both gate application-wide behavior in
// contents/struggle-detector.ts, not any single control there.

// Master switch for the Reading Font feature (see lib/reading-font.ts).
// Default OFF - whatever font is selected in the Aa menu never actually
// renders until this is turned on in Settings. Checked inside
// applyReadingFont() itself, so flipping it live re-renders immediately
// without needing a page reload.
export const FONT_OVERRIDE_ENABLED_STORAGE_KEY = "fontOverrideEnabled"
export const DEFAULT_FONT_OVERRIDE_ENABLED = false

export async function getFontOverrideEnabled(): Promise<boolean> {
  const stored = await chrome.storage.local.get(FONT_OVERRIDE_ENABLED_STORAGE_KEY)
  return stored[FONT_OVERRIDE_ENABLED_STORAGE_KEY] ?? DEFAULT_FONT_OVERRIDE_ENABLED
}

export async function setFontOverrideEnabled(enabled: boolean): Promise<void> {
  await chrome.storage.local.set({ [FONT_OVERRIDE_ENABLED_STORAGE_KEY]: enabled })
}

// Whether the extension turns itself on automatically on pages it
// detects as readable (today's only behavior, and still the default),
// or only when the user explicitly activates it from the popup's Home
// tab for that specific tab (see the MANUAL_ACTIVATE_MESSAGE_TYPE
// handler in contents/struggle-detector.ts).
export const AUTO_ACTIVATE_STORAGE_KEY = "autoActivateEnabled"
export const DEFAULT_AUTO_ACTIVATE_ENABLED = true

export async function getAutoActivateEnabled(): Promise<boolean> {
  const stored = await chrome.storage.local.get(AUTO_ACTIVATE_STORAGE_KEY)
  return stored[AUTO_ACTIVATE_STORAGE_KEY] ?? DEFAULT_AUTO_ACTIVATE_ENABLED
}

export async function setAutoActivateEnabled(enabled: boolean): Promise<void> {
  await chrome.storage.local.set({ [AUTO_ACTIVATE_STORAGE_KEY]: enabled })
}
