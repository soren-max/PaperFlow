# PaperFlow V3 triage

Status: Phase 1 acceptance completed on 2026-09-18.

## Workflow

```text
paperflow triage <citekey>  -> .paperflow/triage/<key>/packet.md
Codex + prompts/triage.md  -> .paperflow/triage/<key>/paper-card.md
paperflow triage <citekey>  -> validate card and update state.json
```

The Vault Skill contains this workflow and the evidence boundary. `paperflow init` installs it in new Vaults and upgrades byte-for-byte PaperFlow-generated pre-triage Skills. A modified Skill remains untouched.

## Packet and evidence boundary

Triage reads the synced Literature note, Research Areas, Questions, linked knowledge notes, and existing PaperFlow state. It does not read the PDF or require Zotero. Each packet includes metadata, abstract, annotations, section titles if ingested, `reading_status`, `processing_status`, whether the Literature note exists, linked Concept/Synthesis/Question paths, brief Research Area content, and Question titles with one-sentence core concerns. Research Area and Question entries are ranked by direct citekey links and title overlap. Existing Literature appears by citekey and title to reveal overlap and duplicates.

Limits in `triage.py` are deterministic: abstract 4,000 characters, annotations 4,000, section titles 3,000, research context 12,000 and at most 100 Literature entries, eight Research Areas, eight Questions, and 28,000 characters for the entire packet. Truncation and omitted entries are marked. The card may treat Vault context as a research question, never as a claim made by the paper.

## Card and state

The card frontmatter has `research_area`, `priority`, `processing_level`, and `basis`, along with exact paper keys. `priority` is research value (`low`, `medium`, `high`). `processing_level` is warranted depth (`triage_only`, `quick`, `normal`, `deep`). They are independent. Older cards with `deep_processing: "yes"/"no"` remain valid and map to `deep`/`triage_only`; new cards use `processing_level`. If both fields are present, they must agree. The five short body sections and evidence-basis rules remain in force. Invalid values produce explicit CLI errors.

The per-paper triage `state.json` stores the validated card and two status fields: `reading_status` (`unread`, `read`) and `processing_status` (`unprocessed`, `triaged`, `processed`). Existing completed V2 pipeline state raises these to `read` and `processed`. Manually recorded state is preserved. These statuses stay in PaperFlow, not Zotero. `paperflow status` reports the level counts and processing counts in two compact rows.

## Real Vault acceptance

On `E:\Obsidian\Research`, the generated Skill was upgraded and both paper cards were validated after packet regeneration. BRINK (`zhoundwhat`) remains `high / deep`; KG-Agent (`jiangndkg`) is `medium / triage_only`. Both packets show `read / processed`, so neither calls for another deep pass. The Questions now contribute their core concerns: retrieval versus reasoning failure for BRINK, and whether local KG completeness should govern routing for KG-Agent. The packet also exposes existing Concept and Question links for both papers. The third synced duplicate remains pending.

Triage is a recommendation and does not lock the V2 pipeline. Its quality depends on the research context the Vault actually contains. Section titles are structural hints, not evidence of paper findings.
