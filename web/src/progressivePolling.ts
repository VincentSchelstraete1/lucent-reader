import type { ProgressivePoll } from "./api/client"

export const PROGRESSIVE_POLL_TIMEOUT_MS = 5 * 60 * 1000
const INITIAL_POLL_DELAY_MS = 500
const MAX_POLL_DELAY_MS = 3_000

type PollOptions = {
  onProgress?: (poll: ProgressivePoll) => void
  shouldContinue?: () => boolean
  maxDurationMs?: number
  now?: () => number
  wait?: (milliseconds: number) => Promise<void>
}

/** Poll a progressive ingestion job with a bounded, gently increasing delay.
 * A null result means the owning component cancelled the run; terminal backend
 * failures and timeouts are explicit errors rather than endless polling.
 */
export async function pollProgressiveJob(
  fetchPoll: () => Promise<ProgressivePoll>,
  options: PollOptions = {},
): Promise<ProgressivePoll | null> {
  const shouldContinue = options.shouldContinue ?? (() => true)
  const now = options.now ?? Date.now
  const wait = options.wait ?? ((milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds)))
  const maxDurationMs = options.maxDurationMs ?? PROGRESSIVE_POLL_TIMEOUT_MS
  const startedAt = now()
  let delayMs = INITIAL_POLL_DELAY_MS

  while (shouldContinue()) {
    const poll = await fetchPoll()
    if (poll.status === "failed") {
      throw new Error(poll.error || "Lucent could not finish processing this document. Please try again.")
    }
    if (poll.status === "complete") return poll
    options.onProgress?.(poll)
    if (now() - startedAt >= maxDurationMs) {
      throw new Error("Document processing took too long. Please try again.")
    }
    await wait(delayMs)
    delayMs = Math.min(MAX_POLL_DELAY_MS, Math.ceil(delayMs * 1.5))
  }
  return null
}
