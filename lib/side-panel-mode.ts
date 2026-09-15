// Browser-profile preference for the separate-window presentation. People can
// select it explicitly, and Lucent also enables it after a browser such as Arc
// reports native-panel success without creating a SIDE_PANEL context. Once
// detected, later toolbar clicks open the fallback immediately.

export const USE_POPUP_FALLBACK_STORAGE_KEY = "usePopupFallback"
export const DEFAULT_USE_POPUP_FALLBACK = false

export async function getUsePopupFallback(): Promise<boolean> {
  const stored = await chrome.storage.local.get(USE_POPUP_FALLBACK_STORAGE_KEY)
  return stored[USE_POPUP_FALLBACK_STORAGE_KEY] ?? DEFAULT_USE_POPUP_FALLBACK
}

export async function setUsePopupFallback(enabled: boolean): Promise<void> {
  await chrome.storage.local.set({ [USE_POPUP_FALLBACK_STORAGE_KEY]: enabled })
}
