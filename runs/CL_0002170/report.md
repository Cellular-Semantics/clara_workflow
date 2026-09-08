# CL:0002170 — keratinized cell of the oral mucosa

> Stage B ran against Asta `snippet_search`, scoped by `paper_ids`. Stage C (`get_europepmc_full_text`) returned empty output for every identifier tried (see issue #5), so unresolved core assertions could not be escalated to full text.

## Routed targets

| target_id | route | refs in scope | where those refs come from |
|---|---|---|---|
| `text_revision:CL:0002170:1` | text_revision | `PMID:12014572` | refs on the revised definition axiom |

**Definition xrefs at head:** `GOC:tfm`, `PMID:12014572` — searchable: `PMID:12014572`

## Assertions

| # | Assertion | Cat | Verdict |
|---|---|---|---|
| a1 | A keratinized cell of the oral mucosa is a keratinized buccal mucosa cell. | core | **uncertain** |
| a2 | Keratinized cells of the oral mucosa are mostly located in the hard palate. | core | **uncertain** |
| a3 | Keratinized cells of the oral mucosa are mostly located in the gingiva. | core | **uncertain** |

## Unresolved

**not retrievable** (3) — `snippet_search` returned 0 hits because PMID:12014572 is absent from the Asta corpus, and the paper is `inEPMC=N` so Stage C cannot reach it either. The reference was in scope but could not be read.

- `a1` A keratinized cell of the oral mucosa is a keratinized buccal mucosa cell.
- `a2` Keratinized cells of the oral mucosa are mostly located in the hard palate.
- `a3` Keratinized cells of the oral mucosa are mostly located in the gingiva.

## Summary

- Assertions: 3 (3 core, 0 background)
- Core: pass 0 · fail 0 · uncertain 3
- Stage C escalation: not available (issue #5)

**Term-level verdict: UNCERTAIN**
