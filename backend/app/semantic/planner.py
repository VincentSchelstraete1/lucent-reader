from .teaching import DeterministicPedagogicalPlanner, TeachingPlan, ContextPacket

class AnthropicPedagogicalPlanner:
    def plan(self, block, decision, context=None):
        from app.services.anthropic_service import _run_structured_tool
        schema = {"type":"object","properties":{"learningGoal":{"type":"string"},"recommendedRepresentation":{"type":"string"},"finalRepresentation":{"type":"string"},"rationale":{"type":"string"},"coreIdeas":{"type":"array","items":{"type":"string"}},"usefulContext":{"type":"array","items":{"type":"string"}},"omittedNoise":{"type":"array","items":{"type":"string"}},"representationPlan":{"type":"array","items":{"type":"string"}},"override":{"type":"boolean"}},"required":["learningGoal","recommendedRepresentation","finalRepresentation","rationale","coreIdeas","usefulContext","omittedNoise","representationPlan","override"]}
        prompt = "Choose the clearest grounded way to teach this one learning block. Keep the final representation within the recommended taxonomy, do not invent facts, and use only the bounded context supplied. Return only the structured plan.\n\nRecommendation: " + decision.type + "\nContext:\n" + (context.model_dump_json() if context else block.text[:6000])
        raw = _run_structured_tool(prompt, "plan_teaching_representation", schema, 900, timeout=8)
        return TeachingPlan.model_validate({**raw, "contextPacket": context})

class PedagogicalPlanner:
    def __init__(self, model_planner=None): self.model_planner = model_planner
    def plan(self, block, decision, context: ContextPacket | None = None) -> TeachingPlan:
        deterministic = DeterministicPedagogicalPlanner().plan(block, decision, context)
        if self.model_planner is None: return deterministic
        try:
            candidate = self.model_planner.plan(block, decision, context)
            if candidate.final_representation in {"plain_text", "process", "comparison", "causal", "concept_map", "hierarchy", "quantitative"}:
                return candidate
        except Exception: pass
        return deterministic
