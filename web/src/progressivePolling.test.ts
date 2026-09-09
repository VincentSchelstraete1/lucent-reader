import { describe, expect, it } from "vitest"

import type { ProgressivePoll } from "./api/client"
import { pollProgressiveJob } from "./progressivePolling"

const processing = (error: string | null = null): ProgressivePoll => ({
  job_id: "job-1",
  filename: "fixture.pdf",
  status: "processing",
  sections: [],
  result: null,
  error,
})

describe("progressive ingestion polling", () => {
  it("backs off and returns the completed result", async () => {
    const terminal = { ...processing(), status: "complete", result: { filename: "fixture.pdf" } } as ProgressivePoll
    const polls = [processing(), processing(), terminal]
    const delays: number[] = []
    const seen: ProgressivePoll[] = []

    const result = await pollProgressiveJob(async () => polls.shift()!, {
      onProgress: (poll) => seen.push(poll),
      wait: async (milliseconds) => { delays.push(milliseconds) },
      now: () => 0,
    })

    expect(result).toBe(terminal)
    expect(seen).toHaveLength(2)
    expect(delays).toEqual([500, 750])
  })

  it("surfaces a terminal backend failure", async () => {
    const failed = { ...processing("The document could not be processed."), status: "failed" } as ProgressivePoll
    await expect(pollProgressiveJob(async () => failed)).rejects.toThrow("The document could not be processed.")
  })

  it("stops after the configured maximum duration", async () => {
    let time = 0
    await expect(pollProgressiveJob(async () => processing(), {
      maxDurationMs: 10,
      now: () => { time += 10; return time },
      wait: async () => undefined,
    })).rejects.toThrow("Document processing took too long")
  })

  it("returns without updating state when its owning run is cancelled", async () => {
    const result = await pollProgressiveJob(async () => processing(), { shouldContinue: () => false })
    expect(result).toBeNull()
  })
})
