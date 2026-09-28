"""Stage 1 — term / change extraction for the agentic CLARA replication.

PROTOTYPE. This package exists to unblock harness development against real CL
PR branches (see tests/fixtures/stage1/). The production extractor, output
contract, and advisory-vs-blocking policy are still open design questions —
see ROADMAP.md. Treat everything here as disposable plumbing.
"""

from clara_workflow.stage1.parse import (
    Change,
    CONTENT_KINDS,
    DECOMPOSABLE_KINDS,
    decomposable_changes,
    definition_refs,
    parse_diff_markdown,
    reviewable_changes,
    summarise_by_term,
    text_deltas,
    TextDelta,
)

__all__ = [
    "Change",
    "CONTENT_KINDS",
    "DECOMPOSABLE_KINDS",
    "decomposable_changes",
    "definition_refs",
    "parse_diff_markdown",
    "reviewable_changes",
    "summarise_by_term",
    "text_deltas",
    "TextDelta",
]
