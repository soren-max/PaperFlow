---
paperflow_prompt: knowledge-integration
version: 1
---

# Integrate a processed paper

Inputs: final Literature note, its evidence cards, and existing relevant Concepts, Questions, Research Area MOCs, and Synthesis. Search titles and aliases before creating anything.

Outputs: update only relevant existing knowledge notes, add exact `[[citekey]]` links, and write `knowledge-integration.md` in the paper artifact folder listing changed files, claim links, and unresolved issues. Research Areas remain navigation pages. Update cross-paper Synthesis only when multiple papers support it.

Evidence boundary: cite the Literature note for paper claims; explicitly label every cross-paper inference, proposed hypothesis, and missing evaluation. Do not modify `## My Notes` or PaperFlow-managed blocks.
