// Whether the user has ever seen the first-run onboarding tooltip that
// points at the simplify badge. Set once, the first time the badge ever
// appears after a fresh install - see maybeShowOnboardingTooltip() in
// contents/struggle-detector.ts. background.ts explicitly marks this
// true (not just left unset) for existing users on an update, so
// shipping this feature doesn't surface the tooltip to people who
// already know what the badge does.

const STORAGE_KEY = "hasSeenOnboarding"

export async function getHasSeenOnboarding(): Promise<boolean> {
  const stored = await chrome.storage.local.get(STORAGE_KEY)
  return stored[STORAGE_KEY] === true
}

export async function markOnboardingSeen(): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEY]: true })
}
