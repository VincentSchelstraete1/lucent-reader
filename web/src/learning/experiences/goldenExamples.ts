import type { StepThroughMechanismData } from "./StepThroughMechanism"

export const gramSchmidtGolden: StepThroughMechanismData = {
  sceneType: "vector_scene",
  learningGoal: "Understand geometrically why subtracting projections produces orthogonal directions.",
  entities: [
    { id: "v1", label: "u₁ = v₁", color: "#1d9e75" },
    { id: "v2", label: "v₂", color: "#bf6b3a" },
    { id: "projection", label: "projᵤ₁(v₂)", color: "#9a7b27" },
    { id: "u2", label: "u₂ (orthogonal remainder)", color: "#26215c" },
  ],
  stages: [
    { title: "Start with overlapping directions", explanation: "v₁ and v₂ share some direction. We keep v₁ as the first basis direction and compare v₂ against it.", activeEntityIds: ["v1", "v2"], vectors: [{ id: "v1", x: 220, y: 0, color: "#1d9e75", label: "u₁ = v₁" }, { id: "v2", x: 185, y: 105, color: "#bf6b3a", label: "v₂" }], visual: { type: "vector_scene", activeEntityIds: ["v1", "v2"], operations: [{ type: "highlight", entityIds: ["v1", "v2"], reason: "Compare the new vector with the direction already kept." }] } },
    { title: "Expose the shared component", explanation: "The projection is the part of v₂ already pointing along u₁. It is the overlap we need to remove.", equation: "projᵤ₁(v₂)", activeEntityIds: ["v2", "projection"], vectors: [{ id: "v2", x: 185, y: 105, color: "#bf6b3a", label: "v₂" }, { id: "projection", x: 185, y: 0, color: "#9a7b27", dashed: true, label: "projection" }], visual: { type: "vector_scene", activeEntityIds: ["v2", "projection"], operations: [{ type: "project", entityIds: ["v2", "v1", "projection"], reason: "Identify the component already along u₁." }], relationships: [{ source: "projection", target: "v1", relation: "parallel_to" }] } },
    { title: "Subtract the overlap", explanation: "Subtracting projᵤ₁(v₂) removes the part of v₂ parallel to u₁, leaving only the new direction.", equation: "u₂ = v₂ − projᵤ₁(v₂)", activeEntityIds: ["v2", "projection", "u2"], vectors: [{ id: "v2", x: 185, y: 105, color: "#bf6b3a", dashed: true, label: "v₂ (before)" }, { id: "projection", x: 185, y: 0, color: "#9a7b27", dashed: true, label: "projection" }, { id: "u2", x: 0, y: 105, color: "#26215c", label: "u₂" }], visual: { type: "vector_scene", activeEntityIds: ["v2", "projection", "u2"], operations: [{ type: "subtract", entityIds: ["v2", "projection", "u2"], reason: "Remove the component already pointing along u₁.", result: "u₂ is the remaining direction." }] } },
    { title: "The remainder is perpendicular", explanation: "The remaining component has no u₁ direction left, so u₂ is orthogonal to u₁. For later vectors, remove projections onto every earlier orthogonal direction.", equation: "uₖ = vₖ − Σ projᵤⱼ(vₖ)", activeEntityIds: ["v1", "u2"], vectors: [{ id: "v1", x: 220, y: 0, color: "#1d9e75", label: "u₁" }, { id: "u2", x: 0, y: 125, color: "#26215c", label: "u₂" }], visual: { type: "vector_scene", activeEntityIds: ["v1", "u2"], operations: [{ type: "reveal", entityIds: ["u2"], result: "The remainder becomes the next basis direction." }], relationships: [{ source: "u2", target: "v1", relation: "perpendicular_to", explanation: "u₂ has no component left along u₁." }] } },
  ],
  prediction: { prompt: "For v₃, which previous directions must be removed?", options: ["u₁", "u₂", "Both u₁ and u₂"], answer: 2, reveal: "Each previous orthogonal direction can contribute an overlap, so Gram–Schmidt subtracts both projections before continuing." },
  conclusion: "Gram–Schmidt builds new orthogonal directions by removing the components already explained by earlier basis vectors; normalization only changes their length.",
}
