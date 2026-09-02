# Deterministic representation router experiment

## Protocol

- Frozen baseline: commit `d448805` (`routeRepresentationBaseline`).
- Dataset: 126 educational passages across seven labels and seven subjects.
- Strict examples: 112 (16 per representation). Ambiguous examples: 14 (two per primary label), with acceptable alternatives recorded before evaluation.
- Split: deterministic stratified 75/25 using seed `lucent-router-evaluation-v1`.
- Development: 84 strict + 7 ambiguous. Holdout: 28 strict + 7 ambiguous.
- Holdout was not evaluated until Candidate D had been selected and encoded in production. No rules were changed after holdout evaluation.

The exact examples, labels, ambiguity annotations, and deterministic split implementation live in `routerDataset.ts`.

## Hypotheses

| Candidate | Hypothesis | Expected benefit | Possible regression |
|---|---|---|---|
| A: lexical coverage | Real educational prose uses more inflections and connectors than the baseline marker list. | Recover causal, comparison, concept, hierarchy, and numeric-change false negatives. | Broad words can match non-structural uses or overpower a better representation. |
| B: class thresholds | Some classes have useful single signals just below `0.42`. | Recover weak but valid process, causal, and concept-map passages. | Promote isolated words and reduce the meaning of confidence. |
| C: structural patterns | Formatting and clause shape can provide evidence without topic-specific vocabulary. | Recover labeled alternatives, category-colon lists, procedural clause lists, and narrated formulas. | Generic lists may be mistaken for hierarchy or concept networks. |
| A+C | Lexical and structural evidence are complementary. | Broader recall without lowering the global threshold. | Carries A's broad-marker regressions. |
| A+B+C | A lower threshold may recover remaining weak cases. | Maximum development recall. | Greater false-positive risk for little incremental gain. |
| D: guarded A+C | Add boundary safeguards and cap generic repeated relations. | Preserve A+C's gains while removing observed broad-marker regressions. | Still misses implicit structure without recognizable language. |

## Development results

| Version | Correct/total | Accuracy | Baseline failures fixed | Baseline correct broken |
|---|---:|---:|---:|---:|
| Baseline | 45/84 | 53.6% | — | — |
| A: lexical coverage | 68/84 | 81.0% | 25 | 2 |
| B: class thresholds | 48/84 | 57.1% | 3 | 0 |
| C: structural patterns | 53/84 | 63.1% | 8 | 0 |
| A+C | 70/84 | 83.3% | 27 | 2 |
| A+B+C | 71/84 | 84.5% | 28 | 2 |
| D: guarded A+C | 75/84 | 89.3% | 30 | 0 |

Candidate D was selected before holdout because it had the best balanced development result, preserved all previously correct strict examples, accepted all seven ambiguous examples, retained the interpretable global threshold, and removed two explainable broad-marker regressions.

## Final untouched holdout

| Version | Correct/total | Accuracy | Ambiguous acceptable |
|---|---:|---:|---:|
| Baseline | 18/28 | 64.3% | 5/7 |
| Candidate D | 21/28 | 75.0% | 7/7 |

Candidate D fixed `causal-09`, `concept_map-09`, and `concept_map-12`, with no strict holdout regressions. The development gain was much larger than the holdout gain, so the result suggests some development-set overfitting or incomplete lexical coverage. Process and implicit comparison remained at 1/4 each on holdout and are the clearest future fallback candidates.

## Production decision

Candidate D was rejected during final regression validation because it broke the pre-existing negative case “The cable is connected to port A,” incorrectly promoting a single relation to `concept_map`. Changing Candidate D after viewing holdout would contaminate the evaluation. Production therefore remains on the frozen baseline. Candidate D is retained only in the evaluation harness; a revised concept-map safeguard requires a new experiment with a new untouched holdout set.
