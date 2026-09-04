# clara_workflow

Agentic replication of the CLARA ontology-term verification workflow.

> **Status:** rough proof-of-concept. The pipeline currently lives as a set of
> agent instructions plus a small Python helper for parsing `robot diff`
> output. Treat everything here as disposable plumbing — see
> [ROADMAP.md](ROADMAP.md).

## What's in this repo

- **[clara_workflow/agent_instructions.md](clara_workflow/agent_instructions.md)** —
  the agent's runbook for verifying routed CLARA targets grouped by ontology
  term against their cited references. This is the only "implementation" of
  the verification loop; there is no Python orchestrator yet. You run it by
  pointing Claude at the file (see *How to run* below).
- **[clara_workflow/stage1/](clara_workflow/stage1/)** — Python parser for
  `robot diff --format markdown` output. Extracts the structured list of
  changes from a PR, classifies each by kind (`text_def`, `comment`,
  `synonym_*`, `subclass`, `relationship`, `equivalent_class`, …), and
  filters out housekeeping noise. Calls `robot` via `subprocess` — hacky, but
  serviceable. See [clara_workflow/stage1/README.md](clara_workflow/stage1/README.md)
  for what counts as a reviewable change.
- **[clara_workflow/validation/](clara_workflow/validation/)** — schema +
  metrics for scoring agent output against the CLARA gold standard.
- **[fixtures/stage1/](fixtures/stage1/)** — five cached `robot diff`
  outputs from real CL PRs (NTRs, def revisions, merges). Used by the unit
  tests so you don't need ROBOT installed to run them.
- **[runs/](runs/)** — example outputs from the previous (programmatic)
  CLARA implementation, kept as reference for the expected schema:
  `verdicts.json`, `tool_calls.jsonl`, `report.md`.
- **[clara_workflow/test_set.yaml](clara_workflow/test_set.yaml)** — 20 CL
  terms selected from the gold set as a small benchmark.
- **[agentic-pipeline-testdata/](agentic-pipeline-testdata/)** — submodule
  ([`Cellular-Semantics/agentic-pipeline-testdata`](https://github.com/Cellular-Semantics/agentic-pipeline-testdata),
  **private**) with `cells_data.json` (term metadata + references) and
  reference PDFs. The agent reads from `cells_data.json`; PDFs are not
  currently used. Nothing else in the repo depends on it — the tests and the
  stage-1 extractor run fine without it.

## Workflow

Three stages, mapped onto how the code is split today:

1. **Stage 1 — Term / change extraction (programmatic).** Parses
   `robot diff` to pick out the axiom-level changes that need
   reference-justification. Decomposable changes (`text_def`, `comment`)
   are routed to the agent for atomic-assertion checking; atomic changes
   (`synonym_*`, `subclass`, `relationship`, `equivalent_class`) are
   already single claims and would be checked directly (skill TBD).
2. **Stage 2 — Assertion decomposition (agentic).** The agent reads routed
   term-level targets from `routing.json`, breaks decomposable text into
   atomic, independently-verifiable claims, and tags each as `core` or
   `background`.
3. **Stage 3 — Assertion checking (agentic).** Snippet search via Asta
   (Semantic Scholar), with a full-text fallback via Europe PMC for any
   `core` assertion still unresolved. See `agent_instructions.md` for the
   exact protocol.

Stages 2 and 3 are both driven by `clara_workflow/agent_instructions.md`.
The consumer contract for that agentic step is the routed payload generated
from stage-1 output in the ontology repo.

## How to run

### Prerequisites

- Python ≥ 3.11
- [`uv`](https://docs.astral.sh/uv/) for environment / dependency
  management
- For the stage-1 extractor only: [ROBOT](http://robot.obolibrary.org/)
  on `PATH` and a local clone of the ontology (e.g. `cell-ontology`).
  Not needed for the unit tests (they use cached fixtures).
- For the agent run: [Claude Code](https://docs.claude.com/en/docs/claude-code)
  with the Asta and `artl-mcp` MCP servers configured (`snippet_search`
  for Stage B, `get_europepmc_full_text` for Stage C).

### Install

```bash
uv venv
uv pip install -e ".[dev]"
```

The `agentic-pipeline-testdata` submodule is private to the Cellular Semantics
org; if you have access, pull it with `git submodule update --init`. Skip it
otherwise — nothing else in the repo needs it.

### Run the tests

```bash
uv run pytest
```

Covers the stage-1 parser against the cached fixtures and the validation
schema. No network, no ROBOT.

### Run stage 1 against a real PR (optional)

```bash
uv run python -m clara_workflow.stage1.extract \
    --repo /path/to/cell-ontology \
    --left  $(git -C /path/to/cell-ontology merge-base <pr-branch> upstream/master) \
    --right <pr-branch> \
    --edit-file src/ontology/cl-edit.owl \
    --output  parsed.json
```

Writes a JSON payload with `changes`, `reviewable`, `decomposable`, and a
per-term summary. Requires ROBOT on `PATH`.

### Run the verification agent

The verification loop is currently invoked by pointing Claude at the
instructions file. First generate a routed target payload (for example
`routing.json`) from stage-1 output using the ontology repo's routing helper,
then from a Claude Code session in this repo run:

```
@clara_workflow/agent_instructions.md verify CL_4033094
```

The agent will:

1. Load `routing.json` and resolve the requested term id to its routed
   validation targets.
2. Decompose routed textual changes into atomic assertions and convert routed
   structural / synonym targets into atomic claims.
3. Run Asta `snippet_search` against each assertion's references
   (Stage B), then fall back to Europe PMC full text for any `core`
   assertion still unresolved (Stage C).
4. Write `runs/{cell_id}/verdicts.json`,
   `runs/{cell_id}/tool_calls.jsonl`, and
   `runs/{cell_id}/report.md`.

`runs/CL_4033094/` and `runs/CL_4052008/` are legacy outputs from the
previous CLARA implementation showing the general verdict/report shape.

## Repo layout

```
clara_workflow/
├── agent_instructions.md      # the agent's runbook (Stages 2 + 3)
├── stage1/                    # robot-diff parser + CLI
├── validation/                # schema + scoring against CLARA gold set
└── test_set.yaml              # 20-term benchmark subset
fixtures/stage1/               # cached robot-diff outputs for tests
runs/                          # example agent outputs (legacy CLARA runs)
tests/                         # pytest unit tests
examples/github-actions/       # draft GHA wiring (not yet active)
agentic-pipeline-testdata/     # submodule (private): term metadata + ref PDFs
```

## Caveats

- The stage-1 extractor shells out to ROBOT — that's intentional for now
  but ugly. A pure-Python diff is a possible future direction.
- The agent instructions assume specific MCP servers (Asta,
  `artl-mcp`). Without those tools the verification loop won't run.
- No CI gating yet — output is advisory. The GHA template under
  `examples/github-actions/` is a sketch, not wired up.
- Full-text retrieval is unreliable (paywalls, partial PMC coverage).
  The benchmark set is biased toward terms with retrievable refs.

## Gold standard

The previous CLARA test set is reused as ground truth. It has:

- Existing per-assertion scoring from the CLARA run (see `runs/`).
- Known retrievable full text for all cited references.

That makes it usable both for automated scoring and for apples-to-apples
comparison against CLARA itself.

See [ROADMAP.md](ROADMAP.md) for planned experiments and milestones.
