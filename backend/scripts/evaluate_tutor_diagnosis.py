#!/usr/bin/env python3
"""NEW (not a pre-existing product eval): scores the real Anthropic-backed
learn_response_evaluation tool call (app.services.learn_tutor.diagnose_response)
against an authored scenario set (tests/fixtures/tutor_eval/scenarios_v1.json).

This exercises the production model path directly -- LEARN_TUTOR_MODEL_ENABLED
is forced on and no FakeTutorProvider is installed, so every call is a live
Anthropic request through app.services.anthropic_service._run_structured_tool.

"Action accuracy" here = the model's returned `result` (diagnosis) matches the
scenario's authored expectedResult AND, when the response is not fully correct,
its `remediationCategory` falls in the authored acceptableRemediation set. Both
must hold for a scenario to count as correct -- this operationalizes "tool
calling, misconception diagnosis, and adaptive remediation" as one combined,
gradeable decision per scenario.

Ground truth (expectedResult / acceptableRemediation) is this script's authored
judgment call, not an independently reviewed labelset -- read the `rationale`
field per scenario before treating a resulting percentage as authoritative.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
os.environ.setdefault("LEARN_TUTOR_MODEL_ENABLED", "1")
os.environ["LEARN_TUTOR_MODEL_ENABLED"] = "1"  # backend/.env may pin this off; force it on for this eval

from app.schemas.learn import LearnEvaluation  # noqa: E402
from app.services.learn_tutor import diagnose_response  # noqa: E402


FALLBACK = LearnEvaluation(
    result="insufficient_evidence", confidence=0.0, misconception=None,
    evidence="fallback", studentMessage="Let's look at this together.",
    remediationCategory="example",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", default=str(Path(__file__).parent.parent / "tests/fixtures/tutor_eval/scenarios_v1.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.scenarios).read_text())
    scenarios = payload["scenarios"]

    rows = []
    for scenario in scenarios:
        evaluation = diagnose_response(
            prompt=scenario["prompt"],
            expected=scenario["expected"],
            response=scenario["response"],
            source_context=scenario["sourceContext"],
            fallback=FALLBACK,
        )
        diagnosis_correct = evaluation.result == scenario["expectedResult"]
        remediation_correct = evaluation.remediation_category in scenario["acceptableRemediation"]
        action_correct = diagnosis_correct and remediation_correct
        rows.append({
            "id": scenario["id"],
            "domain": scenario["domain"],
            "expectedResult": scenario["expectedResult"],
            "actualResult": evaluation.result,
            "diagnosisCorrect": diagnosis_correct,
            "acceptableRemediation": scenario["acceptableRemediation"],
            "actualRemediation": evaluation.remediation_category,
            "remediationCorrect": remediation_correct,
            "actionCorrect": action_correct,
            "misconception": evaluation.misconception,
            "usedFallback": evaluation.evidence == "fallback",
        })

    total = len(rows)
    diagnosis_accuracy = sum(row["diagnosisCorrect"] for row in rows) / total
    remediation_accuracy = sum(row["remediationCorrect"] for row in rows) / total
    action_accuracy = sum(row["actionCorrect"] for row in rows) / total
    fallback_count = sum(row["usedFallback"] for row in rows)

    summary = {
        "version": "tutor-diagnosis-eval-run-v1",
        "totalScenarios": total,
        "diagnosisAccuracy": diagnosis_accuracy,
        "remediationAccuracy": remediation_accuracy,
        "actionAccuracy": action_accuracy,
        "fallbackCount": fallback_count,
        "modelEnabledFlag": os.environ.get("LEARN_TUTOR_MODEL_ENABLED"),
        "rows": rows,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({
        "totalScenarios": total,
        "diagnosisAccuracy": diagnosis_accuracy,
        "remediationAccuracy": remediation_accuracy,
        "actionAccuracy": action_accuracy,
        "fallbackCount": fallback_count,
        "failing": [row["id"] for row in rows if not row["actionCorrect"]],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
