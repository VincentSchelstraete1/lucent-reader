import { describe, expect, it } from "vitest"
import { routeRepresentation } from "./representationRouter"
import type { RepresentationType } from "./representationTypes"

const positiveExamples: Record<RepresentationType, string[]> = {
  process: [
    "The client sends SYN. Then the server responds with SYN-ACK. Finally the client sends ACK.",
    "First collect the sample. Next heat it gently. Finally record the result.",
    "1. Open the valve\n2. Start the pump\n3. Close the valve",
    "The process begins with intake, followed by validation, followed by storage.",
    "Request → validation → processing → response"
  ],
  comparison: [
    "A direct-mapped cache allows one possible location, whereas a four-way set-associative cache allows four.",
    "Unlike RAM, storage retains information without power.",
    "The similarities and differences between TCP and UDP determine which protocol fits.",
    "A fiber connection is faster than a copper connection.",
    "Both mitosis and meiosis divide cells, but they produce different outcomes."
  ],
  causal: [
    "Smoking causes damage to lung tissue, which leads to reduced lung function.",
    "Because demand increased while supply remained fixed, prices rose.",
    "Insulin causes cells to increase glucose uptake, which leads to lower blood glucose.",
    "Heavy rain blocked the drains; therefore the road flooded.",
    "The mutation results in less protein and consequently the pathway slows."
  ],
  concept_map: [
    "Photosynthesis involves chlorophyll, sunlight, carbon dioxide, water, glucose, and oxygen, which are related through several biological mechanisms.",
    "Attention is associated with working memory and connected to learning.",
    "The API depends on authentication, interacts with session storage, and is linked to authorization.",
    "Ecology connects populations, communities, ecosystems, and climate, which are related through energy flows.",
    "Language is connected to cognition and associated with culture."
  ],
  hierarchy: [
    "Computer memory consists of registers, cache, main memory, and secondary storage.",
    "There are three main types of cache misses: compulsory, capacity, and conflict.",
    "The nervous system is composed of the brain, spinal cord, and peripheral nerves.",
    "The platform includes accounts, projects, settings, and reports.",
    "Animals are divided into vertebrates, invertebrates, and other major groups."
  ],
  quantitative: [
    "Average memory access time = hit time + miss rate × miss penalty.",
    "Velocity is distance divided by time.",
    "Force = mass × acceleration.",
    "The ratio of successful requests to total requests determines reliability.",
    "Latency rose from 12 ms to 18 ms, an increase of 50%."
  ],
  plain_text: [
    "Cache memory is a small, fast memory located close to the processor.",
    "The hippocampus is a structure located in the medial temporal lobe.",
    "A compiler translates source code for a computer.",
    "Coral reefs support a wide variety of marine life.",
    "The library is quiet during the afternoon."
  ]
}

describe("routeRepresentation positive behavior", () => {
  for (const [expectedType, texts] of Object.entries(positiveExamples) as [RepresentationType, string[]][]) {
    it.each(texts)(`routes ${expectedType}: %s`, (text) => {
      const result = routeRepresentation(text)
      expect(result.type).toBe(expectedType)
      expect(result.confidence).toBeGreaterThanOrEqual(0)
      expect(result.confidence).toBeLessThanOrEqual(1)
      expect(result.reasons.length).toBeGreaterThan(0)
      for (const score of Object.values(result.scores)) {
        expect(score).toBeGreaterThanOrEqual(0)
        expect(score).toBeLessThanOrEqual(1)
      }
    })
  }
})

describe("marker false positives", () => {
  it.each([
    ["process", "First principles are useful in physics."],
    ["comparison", "The heading contains the word versus."],
    ["causal", "The glossary defines the term because."],
    ["concept_map", "The cable is connected to port A."],
    ["hierarchy", "The guide includes a short introduction."],
    ["quantitative", "The well-known state-of-the-art cache is fast."]
  ] as [Exclude<RepresentationType, "plain_text">, string][])(
    "does not let an isolated %s marker win: %s",
    (type, text) => {
      const result = routeRepresentation(text)
      expect(result.type).not.toBe(type)
    }
  )
})

describe("overlapping structural signals", () => {
  it("chooses process for a procedural comparison while retaining comparison", () => {
    const result = routeRepresentation(
      "Unlike main memory, the cache first checks whether the requested block is present and then returns the data."
    )
    expect(result.type).toBe("process")
    expect(result.scores.process).toBeGreaterThan(result.scores.comparison)
    expect(result.scores.comparison).toBeGreaterThan(0)
  })

  it("chooses causal for a cause followed by one transition", () => {
    const result = routeRepresentation("Because a cache miss occurs, the processor then accesses main memory.")
    expect(result.type).toBe("causal")
    expect(result.scores.causal).toBeGreaterThan(result.scores.process)
    expect(result.scores.process).toBeGreaterThan(0)
  })

  it("chooses hierarchy for categorized quantities while retaining quantitative", () => {
    const result = routeRepresentation(
      "There are three types of storage: cache at 2 ms, memory at 20 ms, and disk at 8 ms."
    )
    expect(result.type).toBe("hierarchy")
    expect(result.scores.hierarchy).toBeGreaterThan(result.scores.quantitative)
    expect(result.scores.quantitative).toBeGreaterThan(0)
  })

  it("chooses causal for a conceptual relationship with an explicit cause", () => {
    const result = routeRepresentation(
      "Sleep is connected to memory because poor sleep causes weaker recall."
    )
    expect(result.type).toBe("causal")
    expect(result.scores.causal).toBeGreaterThan(result.scores.concept_map)
    expect(result.scores.concept_map).toBeGreaterThan(0)
  })

  it("keeps every competing score in the result", () => {
    const result = routeRepresentation("First compare A versus B, then choose one because it is faster.")
    expect(result.scores.process).toBeGreaterThan(0)
    expect(result.scores.comparison).toBeGreaterThan(0)
    expect(result.scores.causal).toBeGreaterThan(0)
    expect(Object.keys(result.scores)).toHaveLength(7)
  })
})

describe("fallback and determinism", () => {
  it.each(positiveExamples.plain_text)("uses plain text for ordinary description: %s", (text) => {
    expect(routeRepresentation(text).type).toBe("plain_text")
  })

  it("uses plain text for empty input", () => {
    expect(routeRepresentation("").type).toBe("plain_text")
  })

  it.each(Object.values(positiveExamples).flat())("returns identical output every time: %s", (text) => {
    expect(routeRepresentation(text)).toEqual(routeRepresentation(text))
  })
})
