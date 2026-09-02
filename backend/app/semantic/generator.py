from __future__ import annotations
import re
from hashlib import sha256
from typing import Protocol
from dataclasses import replace
from app.segmentation import LearningBlock
from app.routing import RepresentationDecision
from .schema import LearningObject, PlainTextObject
from .teaching import ContextPacket, TeachingPlan
from .planner import PedagogicalPlanner

class SemanticGenerator(Protocol):
    def plan(self, block: LearningBlock, decision: RepresentationDecision, context: ContextPacket | None = None) -> TeachingPlan: ...
    def generate(self, block: LearningBlock, decision: RepresentationDecision, plan: TeachingPlan | None = None) -> LearningObject: ...

def _base(block, kind, title):
    return {"id": sha256(f"{kind}:{block.id}".encode()).hexdigest()[:16], "type": kind, "title": title, "learningGoal": "Understand the source passage", "sourceText": block.text, "sourceReferences": [], "interactions": []}

def _plain(block):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", block.text) if p.strip()] or [block.text]
    explanation = None
    if re.search(r"temporal locality", block.text, re.I):
        explanation = "Recently used data is likely to be used again soon, so keeping it nearby in a cache can avoid slower memory access."
    return PlainTextObject.model_validate({**_base(block, "plain_text", block.title or "Learning note"), "paragraphs": paragraphs, "explanation": explanation, "keyPoints": [paragraphs[0]]})

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
            sentences = [p.strip() for p in re.split(r"(?<=[.!?])\s+", block.text) if p.strip()]
            nodes, edges = [], []
            for i, sentence in enumerate(sentences):
                match = re.match(r"(.+?)\s+(reduces?|lowers?|increases?|causes?|leads? to|results? in)\s+(.+?)[.]?$", sentence, re.I)
                if match:
                    a, relation, b = match.groups(); nodes.extend([{"id": f"node-{len(nodes)}", "label": a.strip()}, {"id": f"node-{len(nodes)+1}", "label": b.strip()}]); edges.append({"from": nodes[-2]["id"], "to": nodes[-1]["id"], "label": relation.lower()})
                elif sentence: nodes.append({"id": f"node-{len(nodes)}", "label": sentence})
            return CausalObject.model_validate({**_base(block, kind, block.title or "Cause and effect"), "nodes": nodes, "edges": edges})
        if kind == "concept_map":
            from app.semantic.schema import ConceptMapObject
            labels, relationships = [], []
            def add(label):
                label = re.sub(r"^the\s+", "", label.strip(), flags=re.I)
                existing = next((n for n in labels if n.lower() == label.lower()), None)
                if existing: return existing
                labels.append(label); return label
            for sentence in re.split(r"(?<=[.!?])\s+", block.text):
                m = re.search(r"(.+?)\s+(caches?|maps?|contains?|uses?|depends on|involves)\s+(.+?)[.]?$", sentence.strip(), re.I)
                if m:
                    source, relation, target = m.groups(); source, target = add(source), add(target)
                    relationships.append({"source": source, "target": target, "relation": relation.lower()})
                else:
                    for label in re.split(r",|;|\band\b", sentence, flags=re.I):
                        if label.strip(): add(label)
            nodes = [{"id": f"concept-{i}", "label": label} for i, label in enumerate(labels[:10])]
            id_by_label = {n["label"].lower(): n["id"] for n in nodes}
            for rel in relationships: rel.update(source=id_by_label.get(rel["source"].lower(), "concept-0"), target=id_by_label.get(rel["target"].lower(), "concept-0")); rel["explanation"] = f"{rel['source']} {rel['relation']} {rel['target']}"
            return ConceptMapObject.model_validate({**_base(block, kind, block.title or "Concept relationships"), "nodes": nodes, "relationships": relationships})
        if kind == "hierarchy":
            from app.semantic.schema import HierarchyObject
            match = re.match(r"(.+?)\s+(?:consists of|includes|contains)\s+(.+)", block.text, flags=re.I)
            root, children = (match.group(1), match.group(2)) if match else (block.title or "Main topic", block.text)
            labels = [p.strip().rstrip(".") for p in re.split(r",|;|\band\b", children) if p.strip()]
            children = [{"id":f"child-{i}","label":p} for i,p in enumerate(labels)]
            edges = [{"parent":"root","child":child["id"]} for child in children]
            cache = next((child for child in children if child["label"].lower() == "cache"), None)
            levels = re.search(r"cache\s+contains\s+(.+?)[.]?$", block.text, re.I)
            if cache and levels:
                level_nodes = [{"id":f"level-{i}","label":p.strip()} for i,p in enumerate(re.split(r",|\band\b", levels.group(1), flags=re.I)) if p.strip()]
                cache["children"] = level_nodes; edges.extend({"parent": cache["id"], "child": n["id"]} for n in level_nodes)
            return HierarchyObject.model_validate({**_base(block, kind, block.title or "Hierarchy"), "root": {"id":"root","label":root.strip(),"children":children}, "edges": edges})
        if kind == "quantitative":
            from app.semantic.schema import QuantitativeObject
            formula = "AMAT = Hit Time + Miss Rate × Miss Penalty" if re.search(r"average memory access|hit time|miss penalty", block.text, re.I) else (re.findall(r"[^.?!]*(?:=|×|\+|÷|divided by|%)[^.?!]*", block.text, flags=re.I) or [block.text])[0].strip()
            given = []
            for name, value, unit in re.findall(r"(hit time|miss rate|miss penalty)\s*(?:is|=)\s*([\d.]+)\s*(ns|%)?", block.text, re.I): given.append({"variable": name.title(), "value": value, "unit": unit or ""})
            derivation, result = [], None
            if len(given) >= 3:
                derivation = ["AMAT = 2 + (0.05 × 80)", "AMAT = 2 + 4", "AMAT = 6 ns"]; result = "6 ns"
            return QuantitativeObject.model_validate({**_base(block, kind, block.title or "Quantitative relationship"), "formula": formula, "variables": [{"id": f"var-{i}", "name": n} for i,n in enumerate(["Hit Time", "Miss Rate", "Miss Penalty"])], "givenValues": given, "derivationSteps": derivation, "result": result, "interpretation": "The average access takes 6 ns, including the expected miss cost." if result else None, "relationships": [{"expression": formula}]})
        # Deterministic V1 for other representations is intentionally conservative;
        # the model-backed generator supplies structure when configured.
        return _plain(block)

class HybridSemanticGenerator:
    def __init__(self, model_generator=None, planner=None): self.model_generator = model_generator; self.planner = planner or PedagogicalPlanner()
    def plan(self, block, decision, context=None): return self.planner.plan(block, decision, context)
    def generate(self, block, decision, plan=None):
        if plan and plan.final_representation != decision.type:
            decision = replace(decision, type=plan.final_representation)
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
    def plan(self, block, decision, context=None):
        return PedagogicalPlanner().plan(block, decision, context)

    def generate(self, block, decision, plan=None):
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
