# CL:0000312 — keratinocyte

> Stage B ran against Asta `snippet_search`, scoped by `paper_ids`. Stage C (`get_europepmc_full_text`) returned empty output for every identifier tried (see issue #5), so unresolved core assertions could not be escalated to full text.

## Routed targets

| target_id | route | refs in scope | where those refs come from |
|---|---|---|---|
| `refs_added:CL:0000312:1` | refs_added | `PMID:21316034` | refs newly attached to the definition by this PR (delta only) |

**Definition xrefs at head:** `PMID:15749908`, `PMID:19256306`, `PMID:19727116`, `PMID:29713660`, `PMID:37873034`, `PMID:21316034` — searchable: `PMID:15749908`, `PMID:19256306`, `PMID:19727116`, `PMID:29713660`, `PMID:37873034`, `PMID:21316034`

## Assertions

| # | Assertion | Cat | Verdict |
|---|---|---|---|
| a1 | Keratinocytes are epithelial cells of stratified squamous tissues. | core | **uncertain** |
| a2 | Keratinocytes are present in skin. | core | **pass** |
| a3 | Keratinocytes are present in oral mucosa. | core | **pass** |
| a4 | Keratinocytes are present in esophagus. | core | **uncertain** |
| a5 | Keratinocytes produce keratin proteins. | core | **uncertain** |
| a6 | Keratinocytes secrete antimicrobial peptides. | core | **pass** |
| a7 | Keratinocytes form a barrier against environmental damage. | core | **uncertain** |
| a8 | Keratinocytes form a barrier against dehydration. | core | **uncertain** |
| a9 | Keratinocytes form a barrier against pathogens and microbial invasion. | core | **pass** |
| a10 | Keratinocytes undergo successive stages of differentiation marked by changes in keratin expression. | core | **uncertain** |
| a11 | Keratinocyte differentiation supports tissue integrity and wound repair. | core | **uncertain** |
| a12 | Keratinocytes contribute to immune defense. | core | **pass** |

## Supporting evidence

**a2, a3, a6, a9, a12** — PMID:21316034:

> In the oral cavity, mucosal keratinocytes resist bacterial infection, in part, by producing broad-spectrum antimicrobial peptides (AMPs) including defensin, adrenomedullin and calprotectin. Epidermal keratinocyte expression of many AMPs increases in response to interleukin-1α (IL-1α). IL-1α is produced by epidermal keratinocytes and regulates cell differentiation. To better understand innate immunity in the oral cavity, we sought to determine how IL-1α might regulate expression of AMPs by human gingival keratinocytes (HGKs) using DNA microarray and western blot analyses. HGKs from three subjects expressed eleven AMPs, including S100A7, S100A8, S100A9, S100A12, secretory leukocyte protease inhibitor, lipocalin 2 (LCN2), cystatin C and β-defensin 2. Of the expressed AMPs, S100A7, S100A12 and LCN2 were up-regulated by IL-1α (inducible AMPs); the other AMPs were considered to be constitutive. Human gingival keratinocytes, therefore, express constitutive and IL-1α-inducible AMPs to provide a rapid and robust innate response to microbial infection.

- `a2`: Snippet refers to epidermal keratinocytes.

## Unresolved

**searched** (6) — no snippet in PMID:21316034 addresses this claim.

- `a1` Keratinocytes are epithelial cells of stratified squamous tissues.
- `a4` Keratinocytes are present in esophagus.
- `a5` Keratinocytes produce keratin proteins.
- `a7` Keratinocytes form a barrier against environmental damage.
- `a8` Keratinocytes form a barrier against dehydration.
- `a11` Keratinocyte differentiation supports tissue integrity and wound repair.

**searched** (1) — the snippet states IL-1a regulates cell differentiation but says nothing about keratin-marked stages.

- `a10` Keratinocytes undergo successive stages of differentiation marked by changes in keratin expression.

## Summary

- Assertions: 12 (12 core, 0 background)
- Core: pass 5 · fail 0 · uncertain 7
- Stage C escalation: not available (issue #5)

**Term-level verdict: UNCERTAIN**
