from __future__ import annotations
import re
from hashlib import sha256
from typing import Protocol
from app.segmentation import LearningBlock
from app.routing import RepresentationDecision
from .schema import LearningObject, PlainTextObject

class SemanticGenerator(Protocol):
    def generate(self, block: LearningBlock, decision: RepresentationDecision) -> LearningObject: ...

def _base(block, kind, title):
    return {"id": sha256(f"{kind}:{block.id}".encode()).hexdigest()[:16], "type": kind, "title": title, "learningGoal": "Understand the source passage", "sourceText": block.text, "sourceReferences": [], "interactions": []}

def _plain(block):
    return PlainTextObject.model_validate({**_base(block, "plain_text", block.title or "Learning note"), "paragraphs": [p.strip() for p in re.split(r"\n\s*\n", block.text) if p.strip()] or [block.text]})

def plain_text_fallback(block):
    return _plain(block)

class DeterministicSemanticGenerator:
    def generate(self, block, decision):
        kind = decision.type
        if kind == "plain_text": return _plain(block)
        if kind == "process":
            from app.semantic.schema import ProcessObject
            parts = [p.strip() for p in re.split(r"\b(?:then|next|finally|afterward|followed by)\b|\s*→\s*", block.text, flags=re.I) if p.strip()]
            if len(parts) < 2: return _plain(block)
            return ProcessObject.model_validate({**_base(block, kind, block.title or "Process"), "steps": [{"id": f"step-{i}", "label": p, "explanation": p} for i,p in enumerate(parts)], "connections": [{"from": f"step-{i}", "to": f"step-{i+1}"} for i in range(len(parts)-1)]})
        if kind == "comparison":
            from app.semantic.schema import ComparisonObject
            parts = re.split(r"\bwhereas\b|\bversus\b|\bvs\.?\b", block.text, maxsplit=1, flags=re.I)
            if len(parts) != 2: return _plain(block)
            return ComparisonObject.model_validate({**_base(block, kind, block.title or "Comparison"), "items": [{"id":"item-0","name":parts[0].split(" allows")[0].strip(),"attributes":[{"label":"description","value":parts[0].strip()}]},{"id":"item-1","name":parts[1].split(" allows")[0].strip(),"attributes":[{"label":"description","value":parts[1].strip()}]}]})
        if kind == "causal":
            from app.semantic.schema import CausalObject
            parts = [p.strip() for p in re.split(r"\b(?:because|which leads? to|causes?|results? in|therefore)\b", block.text, flags=re.I) if p.strip()]
            return CausalObject.model_validate({**_base(block, kind, block.title or "Cause and effect"), "nodes": [{"id": f"node-{i}", "label": p} for i,p in enumerate(parts)], "edges": [{"from": f"node-{i}", "to": f"node-{i+1}", "label": "causes"} for i in range(max(0, len(parts)-1))]})
        if kind == "concept_map":
            from app.semantic.schema import ConceptMapObject
            labels = [p.strip() for p in re.split(r",|;|\band\b", block.text, flags=re.I) if p.strip()][:8]
            return ConceptMapObject.model_validate({**_base(block, kind, block.title or "Concept relationships"), "nodes": [{"id": f"concept-{i}", "label": p} for i,p in enumerate(labels)], "relationships": [{"from": "concept-0", "to": f"concept-{i}", "label": "related to"} for i in range(1, len(labels))]})
        if kind == "hierarchy":
            from app.semantic.schema import HierarchyObject
            match = re.match(r"(.+?)\s+(?:consists of|includes|contains)\s+(.+)", block.text, flags=re.I)
            root, children = (match.group(1), match.group(2)) if match else (block.title or "Main topic", block.text)
            labels = [p.strip().rstrip(".") for p in re.split(r",|;|\band\b", children) if p.strip()]
            return HierarchyObject.model_validate({**_base(block, kind, block.title or "Hierarchy"), "root": {"id":"root","label":root.strip(),"children":[{"id":f"child-{i}","label":p} for i,p in enumerate(labels)]}})
        if kind == "quantitative":
            from app.semantic.schema import QuantitativeObject
            expressions = [p.strip() for p in re.findall(r"[^.?!]*(?:=|×|\+|÷|divided by|%)[^.?!]*", block.text, flags=re.I)] or [block.text]
            return QuantitativeObject.model_validate({**_base(block, kind, block.title or "Quantitative relationship"), "variables": [], "relationships": [{"expression": p} for p in expressions]})
        # Deterministic V1 for other representations is intentionally conservative;
        # the model-backed generator supplies structure when configured.
        return _plain(block)

class HybridSemanticGenerator:
    def __init__(self, model_generator=None): self.model_generator = model_generator
    def generate(self, block, decision):
        deterministic = DeterministicSemanticGenerator().generate(block, decision)
        reliable = decision.type in {"process", "comparison", "plain_text"}
        if reliable or self.model_generator is None: return deterministic
        try:
            candidate = self.model_generator.generate(block, decision)
            if candidate.type == decision.type: return candidate
        except Exception:
            pass
        return _plain(block)

class AnthropicSemanticGenerator:
    """Server-only structured extractor. Importing the Anthropic client is lazy so
    deterministic tests and local routing do not require a provider key."""
    def generate(self, block, decision):
        from app.services.anthropic_service import _run_structured_tool
        from .schema import ProcessObject, ComparisonObject, CausalObject, ConceptMapObject, HierarchyObject, QuantitativeObject, PlainTextObject
        schemas = {
            "process": {"type":"object","properties":{"id":{"type":"string"},"type":{"const":"process"},"title":{"type":"string"},"learningGoal":{"type":"string"},"sourceText":{"type":"string"},"steps":{"type":"array","items":{"type":"object"}},"connections":{"type":"array","items":{"type":"object"}}},"required":["id","type","title","learningGoal","sourceText","steps","connections"]},
            "comparison": {"type":"object","properties":{"id":{"type":"string"},"type":{"const":"comparison"},"title":{"type":"string"},"learningGoal":{"type":"string"},"sourceText":{"type":"string"},"items":{"type":"array","items":{"type":"object"}}},"required":["id","type","title","learningGoal","sourceText","items"]},
        }
        common = {"id":{"type":"string"},"title":{"type":"string"},"learningGoal":{"type":"string"},"sourceText":{"type":"string"}}
        schemas.update({
            "causal": {"type":"object","properties":{**common,"type":{"const":"causal"},"nodes":{"type":"array","items":{"type":"object"}},"edges":{"type":"array","items":{"type":"object"}}},"required":[*common,"type","nodes","edges"]},
            "concept_map": {"type":"object","properties":{**common,"type":{"const":"concept_map"},"nodes":{"type":"array","items":{"type":"object"}},"relationships":{"type":"array","items":{"type":"object"}}},"required":[*common,"type","nodes","relationships"]},
            "hierarchy": {"type":"object","properties":{**common,"type":{"const":"hierarchy"},"root":{"type":"object"}},"required":[*common,"type","root"]},
            "quantitative": {"type":"object","properties":{**common,"type":{"const":"quantitative"},"variables":{"type":"array","items":{"type":"object"}},"relationships":{"type":"array","items":{"type":"object"}}},"required":[*common,"type","variables","relationships"]},
        })
        schema = schemas.get(decision.type)
        if schema is None: raise ValueError("structured schema not configured")
        raw = _run_structured_tool(f"Extract only grounded {decision.type} structure from this passage. Do not invent facts. Passage:\n{block.text}", f"learning_{decision.type}", schema, 700, timeout=8)
        classes = {"process": ProcessObject, "comparison": ComparisonObject, "causal": CausalObject, "concept_map": ConceptMapObject, "hierarchy": HierarchyObject, "quantitative": QuantitativeObject, "plain_text": PlainTextObject}
        return classes[decision.type].model_validate(raw)
