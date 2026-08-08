export async function getInstallId(): Promise<string> {
  const stored = await chrome.storage.local.get("installId")
  if (stored.installId) return stored.installId

  const newId = crypto.randomUUID()
  await chrome.storage.local.set({ installId: newId })
  return newId
}