---
paperflow_prompt: paper-map
version: 1
---

# Map one paper

Inputs: `state.json`, `structure.json`, Zotero abstract in state, and only the bounded chunks containing title, abstract, section headings, figure/table captions, conclusion, and limitations. Do not load `source.md` in full.

Outputs: `paper-map.md` with Problem, Method sections, Experiment sections, Important tables/figures, Limitations, and Reading plan; `paper-map.json` with `reading_sections` as an ordered array of exact IDs from `structure.json`. Include all sections needed for claims you intend to make. This is a reading plan, not a final paper summary.

Evidence boundary: distinguish an author-stated problem from your planned research angle. Flag unreadable or missing captions. Do not assert a result before reading its section and table.
