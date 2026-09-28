# CL:0002336 — buccal mucosa cell

> Stage B ran against Asta `snippet_search`, scoped by `paper_ids`. Stage C (`get_europepmc_full_text`) returned empty output for every identifier tried (see issue #5), so unresolved core assertions could not be escalated to full text.

## Routed targets

| target_id | route | refs in scope | where those refs come from |
|---|---|---|---|
| `text_revision:CL:0002336:1` | text_revision | _none searchable_ | refs on the revised definition axiom |
| `text_revision:CL:0002336:2` | text_revision | _none searchable_ | refs on the revised definition axiom |
| `relationship:CL:0002336:1` | relationship | _none searchable_ | refs on the text definition the axiom formalises |

**Definition xrefs at head:** `GOC:tfm`, `MESH:D009061` — searchable: **none**

## Assertions

| # | Assertion | Cat | Verdict |
|---|---|---|---|
| a1 | Buccal mucosa cells are epithelial cells. | core | **uncertain** |
| a2 | Buccal mucosa cells line the oral cavity, including the mucosa of the gums, palate, lip and cheek. | core | **uncertain** |
| a3 | The term 'buccal mucosa cell' is sometimes used only for the lining of the cheeks, as part of the lining mucosa. | background | **uncertain** |
| a4 | NECESSARY: Every buccal mucosa cell is a keratinocyte that is part of the mouth mucosa. | core | **uncertain** |
| a5 | SUFFICIENT: Every keratinocyte that is part of the mouth mucosa is a buccal mucosa cell. | core | **uncertain** |

## Unresolved

**uncited** (2) — this definition carries no searchable reference (only `GOC:tfm` and `MESH:D009061`). No search was possible.

- `a1` Buccal mucosa cells are epithelial cells.
- `a2` Buccal mucosa cells line the oral cavity, including the mucosa of the gums, palate, lip and cheek.

**uncited** (1) — the comment's only xref is a scielo URL, which is not a `PMID:`/`DOI:` id the search tools accept.

- `a3` The term 'buccal mucosa cell' is sometimes used only for the lining of the cheeks, as part of the lining mucosa.

**uncited** (2) — the definition this axiom formalises carries no searchable reference (only `GOC:tfm`, a curator attribution, and `MESH:D009061`, the MeSH descriptor "Mouth Mucosa"). No search was possible.

- `a4` NECESSARY: Every buccal mucosa cell is a keratinocyte that is part of the mouth mucosa.
- `a5` SUFFICIENT: Every keratinocyte that is part of the mouth mucosa is a buccal mucosa cell.

## Summary

- Assertions: 5 (4 core, 1 background)
- Core: pass 0 · fail 0 · uncertain 4
- Stage C escalation: not available (issue #5)

**Term-level verdict: UNCERTAIN**
