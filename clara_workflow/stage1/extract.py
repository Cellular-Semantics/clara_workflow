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


def _robot_diff(
    left: Path,
    right: Path,
    out: Path,
    catalog: Path | None = None,
    robot: str = "robot",
) -> None:
    cmd = [robot, "diff", "--left", str(left)]
    if catalog is not None:
        cmd += ["--left-catalog", str(catalog)]
    cmd += ["--right", str(right)]
    if catalog is not None:
        cmd += ["--right-catalog", str(catalog)]
    cmd += ["--format", "markdown", "--labels", "true", "--output", str(out)]
    subprocess.run(cmd, check=True)


# `definition_refs()` scans for the compact `obo:`/`oboInOwl:` curie form (it
# has to — that's what real edit files use), so a conversion must declare the
# same prefixes ROBOT doesn't add by default.
_OFN_PREFIXES = (
    "obo: http://purl.obolibrary.org/obo/",
    "oboInOwl: http://www.geneontology.org/formats/oboInOwl#",
)


def _robot_convert_to_ofn(
    input_path: Path,
    output_path: Path,
    catalog: Path | None = None,
    robot: str = "robot",
) -> None:
    """Convert `input_path` to OWL functional syntax, in the curie form
    `definition_refs()` expects, regardless of the input's own format.

    This is what lets `definition_refs()` work against an OBO edit file: it
    only understands functional-syntax `AnnotationAssertion(...)` lines, so
    non-OWL edit files (e.g. `uberon-edit.obo`) need converting first.
    """
    cmd = [robot, "convert", "-i", str(input_path)]
    if catalog is not None:
        cmd += ["--catalog", str(catalog)]
    cmd += ["-f", "ofn"]
    for prefix in _OFN_PREFIXES:
        cmd += ["--add-prefix", prefix]
    cmd += ["-o", str(output_path)]
    subprocess.run(cmd, check=True)


def _change_to_dict(c: Change) -> dict:
    d = dataclasses.asdict(c)
    d.pop("raw", None)  # drop the debug field from serialised output
    return d


def extract(
    repo: Path,
    left_ref: str,
    right_ref: str,
    edit_file: str,
    catalog: Path | None = None,
    robot: str = "robot",
) -> tuple[list[Change], dict[str, list[str]]]:
    """Resolve two refs against `edit_file`, run robot diff, parse.

    `catalog` is an ODK-style `catalog-v001.xml` (same file used for both
    refs, since the import graph practically never changes within a single
    reviewed PR): it lets ROBOT resolve every `owl:imports` from the locally
    committed files it maps to, rather than fetching each one over the
    network. That's what makes this work at all for an edit file whose
    imports include a moved/broken PURL, and it also preserves label
    resolution for any entity defined only in an import (e.g. BFO's
    `part of`, or a cross-referenced UBERON/CL class) -- label text that
    `--labels true` can't produce if those imports go unresolved. The caller
    (the GitHub Action) is expected to pass the repo's own catalog file;
    `robot` falls back to its normal (network) import resolution if omitted.

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
        _robot_diff(left, right, diff_md, catalog=catalog, robot=robot)
        # Read definition refs off a functional-syntax conversion rather than
        # the right file directly, so this also works for non-OWL edit files.
        _robot_convert_to_ofn(right, right_ofn, catalog=catalog, robot=robot)
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
    p.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help=(
            "ODK-style catalog-v001.xml, used for both refs, so ROBOT resolves "
            "owl:imports from the locally-committed files it maps to instead of "
            "the network. Omit to fall back to ROBOT's normal import resolution."
        ),
    )
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
        catalog=args.catalog,
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
