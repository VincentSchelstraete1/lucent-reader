import { describe, expect, it } from "vitest"
import { routeRepresentation } from "./representationRouter"
import type { RepresentationType } from "./representationTypes"

const examples: Record<RepresentationType, string[]> = {
  process: [
    "The client sends SYN. Then the server responds with SYN-ACK. Finally the client sends ACK.",
    "First collect the sample. Next heat it gently. Finally record the result.",
    "1. Open the valve\n2. Start the pump\n3. Close the valve"
  ],
  comparison: [
    "A direct-mapped cache allows one possible location, whereas a four-way set-associative cache allows four.",
    "Unlike RAM, storage retains information without power.",
    "The similarities and differences between TCP and UDP determine which protocol fits."
  ],
  causal: [
    "Insulin causes cells to increase glucose uptake, which leads to lower blood glucose.",
    "The road flooded because heavy rain blocked the drains.",
    "The mutation results in less protein; consequently the pathway slows."
  ],
  concept_map: [
    "Photosynthesis is related to chlorophyll and connected to cellular respiration.",
    "Attention is associated with working memory and connected to learning.",
    "The API depends on authentication, which interacts with session storage."
  ],
  hierarchy: [
    "Memory consists of registers, cache, main memory, and secondary storage.",
    "The nervous system contains the brain, spinal cord, and peripheral nerves.",
    "Types of networks include local networks, wide-area networks, and personal networks."
  ],
  quantitative: [
    "Average memory access time is hit time + miss rate × miss penalty.",
    "The processor completes 80% of requests in 12 ms.",
    "The ratio equals successful requests / total requests."
  ],
  plain_text: [
    "Cache memory is a small, fast memory located close to the processor.",
    "A compiler translates source code for a computer.",
    "The hippocampus supports memory formation."
  ]
}

describe("routeRepresentation", () => {
  for (const [expectedType, texts] of Object.entries(examples) as [RepresentationType, string[]][]) {
    it.each(texts)(`routes ${expectedType}: %s`, (text) => {
      const result = routeRepresentation(text)
      expect(result.type).toBe(expectedType)
      expect(result.confidence).toBeGreaterThanOrEqual(0)
      expect(result.confidence).toBeLessThanOrEqual(1)
      expect(result.reasons.length).toBeGreaterThan(0)
    })
  }

  it("returns identical output for identical input", () => {
    const text = examples.process[0]
    expect(routeRepresentation(text)).toEqual(routeRepresentation(text))
  })

  it("preserves secondary scores while choosing the strongest type", () => {
    const result = routeRepresentation("First compare A versus B, then choose one because it is faster.")
    expect(result.scores.process).toBeGreaterThan(0)
    expect(result.scores.comparison).toBeGreaterThan(0)
    expect(result.scores.causal).toBeGreaterThan(0)
  })

  it("uses plain text for empty input", () => {
    expect(routeRepresentation("").type).toBe("plain_text")
  })
})
