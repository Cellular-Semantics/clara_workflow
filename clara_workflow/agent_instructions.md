# Agent instructions — CLARA routed-target verification

You are verifying factual claims implied by routed CLARA targets against their
cited references.

Work one term at a time, but process **all routed targets for that term**
together.

## Input

Two invocation modes are supported.

### Local / focused

```text
@clara_workflow/agent_instructions.md verify CL_4033094
```

Treat the argument after `verify` as the requested term id. Accept either
`CL_4033094` or `CL:4033094`.

### CI / batch

If no specific term id is supplied, process every routed term present in
`routing.json`.

## Routing payload

Input data comes from the routing payload produced by
`src/scripts/clara_select_targets.py` (for example `routing.json`). Load that
JSON file from the repository root.

Treat this routed payload as the stable consumer contract for PR-triggered
CLARA review.

Normalise ids as follows:

- underscore form (`CL_4033094`) is the runtime `cell_id`
- CURIE form (`CL:4033094`) is the routing payload `term_id`

The routing payload contains `targets`. Each target has one of these routes:

- `ntr` — new term bundle; contains decomposable text plus structural context
- `text_revision` — revised prose on an existing term; decomposable
- `refs_added` — prose on an existing term that did **not** change, with one or
  more references newly attached to it
- `relationship` — a single atomic structural axiom to check
- `synonym` — a single atomic synonym axiom to check

Relevant target fields:

- `target_id`
- `route`
- `validation_mode`
- `term_id`
- `term_label`
- `term_is_new`
- `candidate_refs`
- `term_level_candidate_refs`
- for `ntr`: `textual_changes` (legacy alias `definition_changes`) and
  `relationship_changes`
- for `text_revision`: `textual_changes`, plus `prior_value` on each change
- for `refs_added`: `textual_changes` and `refs_added`
- for `relationship` / `synonym`: `change`

### Contract rules

- The processing unit is one **term group**, not one raw target:
  collect every target whose `term_id` matches the requested term and process
  them together.
- The canonical field for decomposable prose is `textual_changes`.
  `definition_changes` is accepted only as a backward-compatibility alias
  while producer/consumer wiring is being cleaned up.
- `candidate_refs` and `term_level_candidate_refs` should already be filtered
  to searchable literature ids before they reach the agent. Do not invent or
  broaden the ref set beyond what the payload provides.
- Searchable refs are only ids usable by the tools: `PMID:...`, `DOI:...`, or
  `doi:...`.
- Unknown `route` values are contract errors: stop and report them rather
  than guessing.

## Term selection

### Focused mode

- Select all targets whose `term_id` matches the requested term id after
  normalisation.
- If no targets match, stop and say the routing payload does not contain that
  term id.

### Batch mode

- Group all targets by `term_id`.
- Process each term group independently.

For every processed term, write one output bundle under `runs/{cell_id}/`.

## Assertion preparation

For a given term, convert every routed target into one or more assertions.

### Route: `ntr`

For `ntr` targets:

1. Take each `added` change from `textual_changes` (or legacy
   `definition_changes`).
2. Decompose its `value` into atomic assertions.
3. Tag each assertion as:
   - `core` — the subject is the cell type itself
   - `background` — the subject is a molecule, gene, process, or external
     concept rather than the cell type
4. Also take each `added` change from `relationship_changes` and convert it
   into one atomic `core` assertion.

### Route: `text_revision`

The prose changed on an existing term. Treat it like the textual half of an
`ntr` target:

1. Decompose the `added` change's `value` into atomic assertions.
2. Tag each `core` or `background` as above.

`prior_value` is the previous wording, provided as context only. Do not verify
it, and do not report assertions that are unchanged between the two wordings as
new claims — the reviewable content is the current `value`.

### Route: `refs_added`

The prose did **not** change; a reference was attached to it. The claim under
review is that the *newly added* reference supports the existing text.

1. Decompose the `value` into atomic assertions as usual.
2. Verify them **only** against `refs_added` — not the full ref list on the
   axiom. The pre-existing refs were justified when they were added.
3. If every assertion is `uncertain` against the new refs, that is a real
   result: the added reference does not visibly support the definition. Say so
   in the report rather than falling back to the older refs.

Do not re-verify the definition against its whole reference set on this route.

### Route: `relationship`

For `relationship` targets:

- Convert the routed `change` into one atomic `core` assertion.

### Route: `synonym`

For `synonym` targets:

- Convert the routed `change` into one atomic `core` assertion.

### Removed sides

- If a routed change has `side == "removed"`, do not attempt reference
  justification. Record it as skipped and move on.

## How to verbalise atomic routed changes

Use plain natural-language assertions. Prefer labels when present.

Examples:

- `subclass`:
  - "`{term_label}` is a `{value_label}`."
- `relationship`:
  - "`{term_label}` `{predicate_label}` `{value_label}`."
- `synonym_exact`:
  - "`{value}` is an exact synonym of `{term_label}`."
- `synonym_broad`:
  - "`{value}` is a broad synonym of `{term_label}`."
- `synonym_narrow`:
  - "`{value}` is a narrow synonym of `{term_label}`."
- `synonym_related`:
  - "`{value}` is a related synonym of `{term_label}`."

For `equivalent_class` routed as a structural target, `value` carries the bare
axiom in Manchester syntax, e.g.

```text
buccal mucosa cell EquivalentTo keratinocyte and (part of some mouth mucosa)
```

`EquivalentTo` states necessary **and sufficient** conditions, so it makes two
claims. Emit **both** as separate `core` assertions:

- necessary — "Every `{term_label}` is a `{genus}` that `{differentia}`."
- sufficient — "Every `{genus}` that `{differentia}` is a `{term_label}`."

The sufficient direction is the one editors get wrong and the one literature
rarely states outright. Do not mark it `pass` on evidence that only supports
the necessary direction, and do not collapse the two into a single assertion.
If the axiom nests operators too deeply to verbalise faithfully, verbalise what
you can and note the residue — do not silently drop a conjunct.

Only if `value` is absent or empty may you fall back to a single `core`
assertion noting that the equivalent-class axiom requires support, left
`uncertain` with a note that the payload exposed no axiom text.

## Reference scope per assertion

Every assertion must carry its own `refs_in_scope`.

Reference selection rules:

- For assertions derived from an `ntr` target, prefer that target's
  `candidate_refs`.
- If an `ntr` target has no searchable `candidate_refs`, fall back to its
  `term_level_candidate_refs`.
- For `relationship` targets, prefer `candidate_refs`; if empty, fall back to
  `term_level_candidate_refs`.
- For `synonym` targets, use `candidate_refs`.
- For `text_revision` targets, use `candidate_refs`; if empty, fall back to
  `term_level_candidate_refs`.
- For `refs_added` targets, use `refs_added` only. Never widen to the axiom's
  pre-existing refs.
- Assume these ref lists were prefiltered upstream; only normalize case and
  slash formatting needed by the search tools.

If an assertion ends up with zero searchable refs:

- still keep it in the output
- do not call search tools for it
- mark it `uncertain`
- record a note explaining that no searchable refs were available for that
  routed target

## Stage A — Decompose textual changes

For every decomposable `textual_changes` entry:

- One fact per assertion.
- Split conjunctions ("secretes X, Y, and Z" → three assertions).
- Split clauses that bundle identity + location + function.
- Preserve the cell-type subject in every `core` assertion so it stands alone.
- Strip hedges ("crucial for", "key") but keep the factual core.
- Do not invent claims the text does not make.
- Use only the routed textual change's `value` as the prose source of truth.

Emit the assertion list mentally before verification; you do not need to print
it separately unless asked.

## Stage B — Verify each assertion (snippet-first)

For each assertion that has searchable refs in scope:

1. Build a short query capturing the key entities + claim.
2. Call `mcp__Asta_semanticscholar__snippet_search` with:
   - `query`
   - `paper_ids`: the assertion's refs in scope, converted to comma-separated
     Asta ids (`PMID:12345`, `DOI:10.xxxx/yyy` — uppercase the prefix, strip
     any leading slash on `doi:/...`)
   - `limit`: 10 is usually enough
3. Log the call by appending one JSON line to `runs/{cell_id}/tool_calls.jsonl`.
   Include at least:

   ```json
   {"tool":"snippet_search","assertion_id":"a1","target_id":"ntr:CL:...","query":"...","paper_ids":"PMID:...","returned_paper_ids":["PMID:..."],"n_hits":3,"n_leaked":0}
   ```

4. Drop leaked snippets whose paper id is not in the requested set.
5. Decide:
   - `pass` — a non-leaked snippet explicitly supports the assertion
   - `fail` — a non-leaked snippet explicitly contradicts it
   - `uncertain` — no snippet directly addresses it
6. Any-reference-supports rule: one supporting reference is enough for `pass`.

## Stage C — Full-text fallback

Trigger only for `core` assertions still `fail` or `uncertain` after Stage B.
`background` assertions stay at their Stage B verdict.

Group unresolved `core` assertions by reference paper. For each paper:

1. Call `mcp__artl-mcp__get_europepmc_full_text`.
2. Log the call to `runs/{cell_id}/tool_calls.jsonl`:

   ```json
   {"tool":"get_full_text","target_id":"...","identifier":"PMID:...","available":true}
   ```

3. Re-evaluate all unresolved `core` assertions for that paper in one pass.
4. If full text is unavailable, leave those assertions at their Stage B
   verdict and note `full_text_available: false`.

## Output

For each processed term, write:

- `runs/{cell_id}/verdicts.json`
- `runs/{cell_id}/tool_calls.jsonl`
- `runs/{cell_id}/report.md`

### `runs/{cell_id}/verdicts.json`

Use this shape:

```json
{
  "cell_id": "CL_4033094",
  "term_id": "CL:4033094",
  "name": "...",
  "targets_processed": [
    {
      "target_id": "ntr:CL:4033094",
      "route": "ntr",
      "validation_mode": "decompose_definition_and_relationships"
    }
  ],
  "references": ["PMID:...", "DOI:..."],
  "assertions": [
    {
      "id": "a1",
      "target_id": "ntr:CL:4033094",
      "route": "ntr",
      "source_change_kind": "text_def",
      "text": "...",
      "category": "core|background",
      "refs_in_scope": ["PMID:..."],
      "snippet_stage": {
        "verdict": "pass|fail|uncertain",
        "evidence": "...",
        "source": "PMID:...",
        "note": null
      },
      "full_text_stage": null,
      "final_verdict": "pass|fail|uncertain",
      "warn_background": false
    }
  ],
  "summary": {
    "total": 0,
    "total_core": 0,
    "total_background": 0,
    "core_pass_snippet": 0,
    "core_pass_full_text": 0,
    "core_fail": 0,
    "core_uncertain": 0,
    "background_pass": 0,
    "background_warn": 0
  }
}
```

Notes:

- `references` is the aggregate unique searchable ref list across all processed
  targets for that term.
- Every assertion must preserve `target_id`, `route`, and
  `source_change_kind` so the workflow can map results back to routed inputs.
- `final_verdict` is `full_text_stage.verdict` if that stage ran, else
  `snippet_stage.verdict`.
- `warn_background` is `true` iff `category == "background"` and
  `final_verdict` is `fail` or `uncertain`.
- Term-level pass/fail is driven only by `core` assertions.

### `runs/{cell_id}/tool_calls.jsonl`

One JSON object per line, one line per tool invocation.

### `runs/{cell_id}/report.md`

Short human-readable summary:

- term name and id
- processed targets
- final term-level result
- assertion list with final verdict
- trimmed evidence quote for failures and notable uncertainties

Group the report by routed target when that improves readability.

## Context efficiency

- Do not re-load full text you already have in context.
- When you load full text, validate every outstanding `core` assertion for
  that paper at once.
- Do not copy snippets or full text into files beyond quoted evidence in
  `verdicts.json` and `report.md`.

## What not to do

- Do not mark an assertion `pass` from background knowledge alone.
- Do not fabricate snippet text or paper ids.
- Do not make `snippet_search` calls without `paper_ids` set.
- Do not use leaked snippets as evidence.
- Do not edit `routing.json` or the source `changes.json`.
