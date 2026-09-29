"""Drive `robot diff` against a git repo and emit stage-1 JSON.

PROTOTYPE — see package docstring. Intended entry point for the GitHub Action
workflow. Given a repo path and two refs (base + head), this extracts the
edit-file from each ref, runs `robot diff`, parses the markdown output, and
writes a JSON change list.

CLI (prototype):
    python -m clara_workflow.stage1.extract \\
        --repo <path> --left <ref> --right <ref> \\
        --edit-file src/ontology/cl-edit.owl \\
        --output changes.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from clara_workflow.stage1.parse import (
    Change,
    decomposable_changes,
    definition_refs,
    parse_diff_markdown,
    reviewable_changes,
    summarise_by_term,
    text_deltas,
)


def _git_show(repo: Path, ref: str, path: str, out: Path) -> None:
    with out.open("wb") as fh:
        subprocess.run(
            ["git", "-C", str(repo), "show", f"{ref}:{path}"],
            stdout=fh, check=True,
        )


# Matches an OBO `import:` line, or an OWL functional-syntax `Import(<iri>)`
# line (the two serializations edit files are known to use).
_IMPORT_LINE_RE = re.compile(r"^(import:\s|Import\()")


def _strip_imports(text: str) -> str:
    """Drop owl:imports declarations from edit-file text.

    Used only as a fallback when ROBOT fails to resolve the real import
    graph (e.g. a moved PURL) — not the default path. Stripping unconditionally
    would also strip label resolution for entities defined only in an import
    (e.g. BFO's `part of`, or an UBERON class referenced from cl-edit.owl),
    degrading axiom text like `part of some mouth mucosa` down to
    `BFO_0000050 some UBERON_0003729`. That's a real quality loss for the
    downstream verification agent, so this is a last resort, not a default.
    """
    return "\n".join(
        line for line in text.splitlines() if not _IMPORT_LINE_RE.match(line)
    ) + "\n"


def _robot_diff(left: Path, right: Path, out: Path, robot: str = "robot") -> None:
    subprocess.run(
        [
            robot, "diff",
            "--left", str(left),
            "--right", str(right),
            "--format", "markdown",
            "--labels", "true",
            "--output", str(out),
        ],
        check=True,
    )


def _robot_diff_with_import_fallback(
    left: Path, right: Path, out: Path, robot: str = "robot"
) -> None:
    """Diff with the edit files as-is first (full import graph -> real
    labels); only fall back to import-stripped copies if that fails (e.g. a
    moved PURL). Keeps today's label quality for every repo whose imports
    still resolve, while not hard-failing for one that doesn't.
    """
    try:
        _robot_diff(left, right, out, robot=robot)
        return
    except subprocess.CalledProcessError:
        pass
    stripped_left = left.with_name(left.name + ".noimports")
    stripped_right = right.with_name(right.name + ".noimports")
    stripped_left.write_text(_strip_imports(left.read_text()))
    stripped_right.write_text(_strip_imports(right.read_text()))
    _robot_diff(stripped_left, stripped_right, out, robot=robot)


# `definition_refs()` scans for the compact `obo:`/`oboInOwl:` curie form (it
# has to — that's what real edit files use), so a conversion must declare the
# same prefixes ROBOT doesn't add by default.
_OFN_PREFIXES = (
    "obo: http://purl.obolibrary.org/obo/",
    "oboInOwl: http://www.geneontology.org/formats/oboInOwl#",
)


def _robot_convert_to_ofn(input_path: Path, output_path: Path, robot: str = "robot") -> None:
    """Convert `input_path` to OWL functional syntax, in the curie form
    `definition_refs()` expects, regardless of the input's own format.

    This is what lets `definition_refs()` work against an OBO edit file: it
    only understands functional-syntax `AnnotationAssertion(...)` lines, so
    non-OWL edit files (e.g. `uberon-edit.obo`) need converting first.
    """
    cmd = [robot, "convert", "-i", str(input_path), "-f", "ofn"]
    for prefix in _OFN_PREFIXES:
        cmd += ["--add-prefix", prefix]
    cmd += ["-o", str(output_path)]
    subprocess.run(cmd, check=True)


def _robot_convert_to_ofn_with_import_fallback(
    input_path: Path, output_path: Path, robot: str = "robot"
) -> None:
    """Same fallback strategy as `_robot_diff_with_import_fallback`: definitions'
    own dbxrefs never depend on an import, so stripping only kicks in when the
    full-import conversion fails outright.
    """
    try:
        _robot_convert_to_ofn(input_path, output_path, robot=robot)
        return
    except subprocess.CalledProcessError:
        pass
    stripped = input_path.with_name(input_path.name + ".noimports")
    stripped.write_text(_strip_imports(input_path.read_text()))
    _robot_convert_to_ofn(stripped, output_path, robot=robot)


def _change_to_dict(c: Change) -> dict:
    d = dataclasses.asdict(c)
    d.pop("raw", None)  # drop the debug field from serialised output
    return d


def extract(
    repo: Path,
    left_ref: str,
    right_ref: str,
    edit_file: str,
    robot: str = "robot",
) -> tuple[list[Change], dict[str, list[str]]]:
    """Resolve two refs against `edit_file`, run robot diff, parse.

    Returns the parsed changes plus the head-state definition refs per term,
    which is where a logical definition's justification lives when the text
    definition itself wasn't touched by the PR.
    """
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        left = tdp / "left.owl"
        right = tdp / "right.owl"
        right_ofn = tdp / "right.ofn"
        diff_md = tdp / "diff.md"
        _git_show(repo, left_ref, edit_file, left)
        _git_show(repo, right_ref, edit_file, right)
        # Full import graph first (real labels on cross-ontology references);
        # only degrade to import-stripped copies if that fails outright (e.g.
        # a moved PURL) -- see _robot_diff_with_import_fallback.
        _robot_diff_with_import_fallback(left, right, diff_md, robot=robot)
        # Read definition refs off a functional-syntax conversion rather than
        # the right file directly, so this also works for non-OWL edit files.
        _robot_convert_to_ofn_with_import_fallback(right, right_ofn, robot=robot)
        return (
            parse_diff_markdown(diff_md.read_text()),
            definition_refs(right_ofn.read_text()),
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--left", required=True, help="base git ref")
    p.add_argument("--right", required=True, help="head git ref")
    p.add_argument("--edit-file", default="src/ontology/cl-edit.owl")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--robot", default=os.environ.get("ROBOT", "robot"))
    args = p.parse_args(argv)

    if shutil.which(args.robot) is None:
        print(f"robot executable not found: {args.robot}", file=sys.stderr)
        return 2

    changes, head_definition_refs = extract(
        repo=args.repo,
        left_ref=args.left,
        right_ref=args.right,
        edit_file=args.edit_file,
        robot=args.robot,
    )
    reviewable = reviewable_changes(changes)
    decomposable = decomposable_changes(changes)
    payload = {
        "left": {"ref": args.left, "file": args.edit_file},
        "right": {"ref": args.right, "file": args.edit_file},
        "changes": [_change_to_dict(c) for c in changes],
        "reviewable": [_change_to_dict(c) for c in reviewable],
        "decomposable": [_change_to_dict(c) for c in decomposable],
        # Removed/added text axioms paired so a ref-only edit is distinguishable
        # from a rewrite; consumed by the router to pick a route.
        "text_deltas": [dataclasses.asdict(d) for d in text_deltas(changes)],
        "by_term": {
            tid: {
                **{k: v for k, v in entry.items() if k != "changes"},
                "changes": [_change_to_dict(c) for c in entry["changes"]],
                # Refs on the term's definition as it stands at the head ref —
                # present whether or not this PR touched the definition.
                "definition_refs": head_definition_refs.get(tid, []),
            }
            for tid, entry in summarise_by_term(changes).items()
        },
    }
    args.output.write_text(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
