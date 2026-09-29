---
paperflow_prompt: cards
version: 1
---

# Build reusable paper cards

Inputs: validated `evidence.jsonl` and `paper-map.md`; consult only a cited source chunk when a card is ambiguous.

Outputs: `method-card.md` covering Problem, Input, Output, Architecture, Components, Training, Inference, Tools, Memory, Objective, Complexity, Dependencies, Assumptions; `result-card.md` covering Datasets, Baselines, Metrics, Main Results, Ablations, Generalization, Efficiency, Failure Cases, Limitations. Omit unknown details explicitly. Attach `[E001]` style evidence IDs to each factual statement.

Evidence boundary: distinguish a reported measurement from an author interpretation. Do not collapse different datasets or metrics into one score. Do not treat an untested scenario as a limitation the authors measured.
