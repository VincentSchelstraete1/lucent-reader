// Manual override for browsers where chrome.sidePanel exists and
// resolves successfully but never actually shows anything (confirmed in
// Arc) - there's no reliable way to detect this automatically (the API
// call itself reports success either way), so this is a one-time
// user-set toggle instead, surfaced on the standalone options page
// (reachable regardless of whether the panel/popup ever opens, unlike
// the side panel itself). Same chrome.storage.local pattern as
// extension-settings.ts.

export const USE_POPUP_FALLBACK_STORAGE_KEY = "usePopupFallback"
export const DEFAULT_USE_POPUP_FALLBACK = false

export async function getUsePopupFallback(): Promise<boolean> {
  const stored = await chrome.storage.local.get(USE_POPUP_FALLBACK_STORAGE_KEY)
  return stored[USE_POPUP_FALLBACK_STORAGE_KEY] ?? DEFAULT_USE_POPUP_FALLBACK
}

export async function setUsePopupFallback(enabled: boolean): Promise<void> {
  await chrome.storage.local.set({ [USE_POPUP_FALLBACK_STORAGE_KEY]: enabled })
}
