import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import {
  StepThroughMechanism,
  summarizeVisualProgram,
  type StepThroughMechanismData,
} from "./StepThroughMechanism"
import { gramSchmidtGolden } from "./goldenExamples"

const ordered: StepThroughMechanismData = {
  sceneType: "ordered_items_scene",
  learningGoal: "Understand a reasoned change in an ordered collection.",
  entities: [{ id: "elem1", label: "5" }, { id: "elem2", label: "3" }, { id: "elem3", label: "8" }],
  stages: [
    {
      title: "Compare",
      explanation: "Compare the selected values.",
      visual: {
        type: "ordered_items_scene",
        before: { items: [{ entityId: "elem1", status: "compared" }, { entityId: "elem2", status: "compared" }, { entityId: "elem3", status: "default" }], regions: [] },
        operation: { type: "compare", entityIds: ["elem1", "elem2"], reason: "5 > 3, so the pair is out of ascending order." },
      },
    },
    {
      title: "Swap",
      explanation: "Exchange the pair.",
      visual: {
        type: "ordered_items_scene",
        before: { items: [{ entityId: "elem1", status: "selected" }, { entityId: "elem2", status: "selected" }, { entityId: "elem3", status: "default" }], regions: [] },
        operation: { type: "swap", entityIds: ["elem1", "elem2"], reason: "Ascending order requires 3 before 5.", result: "3 now precedes 5." },
        after: { items: [{ entityId: "elem2", status: "changed" }, { entityId: "elem1", status: "changed" }, { entityId: "elem3", status: "default" }], regions: [] },
      },
    },
  ],
  conclusion: "The semantic operation explains both what changed and why.",
}

const sequence: StepThroughMechanismData = {
  sceneType: "sequence_exchange_scene",
  learningGoal: "Understand an ordered exchange.",
  entities: [{ id: "client", label: "Client" }, { id: "server", label: "Server" }],
  stages: [
    { title: "Initiate", explanation: "The first actor initiates.", visual: { type: "sequence_exchange_scene", actors: [{ id: "client", label: "Client" }, { id: "server", label: "Server" }], messages: [{ id: "syn", sender: "client", receiver: "server", label: "SYN", reason: "Initiate the connection." }], visibleMessageIds: ["syn"], emphasizedMessageId: "syn" } },
    { title: "Complete", explanation: "The exchange completes.", visual: { type: "sequence_exchange_scene", actors: [{ id: "client", label: "Client" }, { id: "server", label: "Server" }], messages: [{ id: "syn", sender: "client", receiver: "server", label: "SYN" }, { id: "ack", sender: "server", receiver: "client", label: "ACK" }], visibleMessageIds: ["syn", "ack"], emphasizedMessageId: "ack" } },
  ],
  conclusion: "Direction and order are explicit.",
}

function render(data: StepThroughMechanismData) {
  return renderToStaticMarkup(createElement(StepThroughMechanism, { data }))
}

describe("StepThroughMechanism visual DSL", () => {
  it("uses learner-facing labels and not internal IDs for ordered operations", () => {
    const html = render(ordered)
    expect(html).toContain("Compare 5 and 3")
    expect(html).toContain("5 &gt; 3")
    expect(html).not.toContain("elem1")
    expect(html).not.toContain("elem2")
  })

  it("renders a coherent before/after state for state-changing operations", () => {
    const secondStage = { ...ordered, stages: [ordered.stages[1], ordered.stages[1]] }
    const html = render(secondStage)
    expect(html).toContain("Before")
    expect(html).toContain("After")
    expect(html).toContain("Swap 5 and 3")
    expect(html).toContain("3 now precedes 5")
  })

  it("keeps sequence exchanges out of the Cartesian grammar", () => {
    const html = render(sequence)
    expect(html).toContain("Client")
    expect(html).toContain("Server")
    expect(html).toContain("SYN")
    expect(html).toContain("sequence-lifeline")
    expect(html).not.toContain('class="axis"')
  })

  it("preserves deterministic vector rendering for the golden mechanism", () => {
    const html = render(gramSchmidtGolden)
    expect(html).toContain("vector-v1")
    expect(html).toContain("vector-v2")
    expect(html).toContain('class="axis"')
  })

  it("declines unsupported and empty visual programs without vector fallback", () => {
    const unsupported = { ...ordered, sceneType: "future_scene" }
    const unsupportedHtml = render(unsupported)
    expect(unsupportedHtml).toContain("Visual unavailable")
    expect(unsupportedHtml).not.toContain('class="axis"')

    const emptySequence = { ...sequence, stages: sequence.stages.map((stage) => ({ ...stage, visual: undefined })) }
    const emptyHtml = render(emptySequence)
    expect(emptyHtml).toContain("This stage has no visual semantic program")
    expect(emptyHtml).not.toContain("sequence-lifeline")
  })

  it("summarizes semantic and state-changing operations", () => {
    const summary = summarizeVisualProgram(ordered)
    expect(summary).toMatchObject({ scene: "ordered_items_scene", entities: 3, stages: 2, operations: 2, stateChangingOperations: 1, availableStages: 2 })
  })
})
