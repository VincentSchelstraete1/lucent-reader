// Whether Reading Mode highlights a thin band around the line under the
// cursor - same chrome.storage.local boolean pattern as
// extension-settings.ts's two toggles.

export const FOCUS_LINE_STORAGE_KEY = "focusLineEnabled"
export const DEFAULT_FOCUS_LINE_ENABLED = false

export async function getFocusLineEnabled(): Promise<boolean> {
  const stored = await chrome.storage.local.get(FOCUS_LINE_STORAGE_KEY)
  return stored[FOCUS_LINE_STORAGE_KEY] ?? DEFAULT_FOCUS_LINE_ENABLED
}

export async function setFocusLineEnabled(enabled: boolean): Promise<void> {
  await chrome.storage.local.set({ [FOCUS_LINE_STORAGE_KEY]: enabled })
}
