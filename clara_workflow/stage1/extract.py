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
) -> list[Change]:
    """Resolve two refs against `edit_file`, run robot diff, parse, return changes."""
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        left = tdp / "left.owl"
        right = tdp / "right.owl"
        diff_md = tdp / "diff.md"
        _git_show(repo, left_ref, edit_file, left)
        _git_show(repo, right_ref, edit_file, right)
        _robot_diff(left, right, diff_md, robot=robot)
        return parse_diff_markdown(diff_md.read_text())


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

    changes = extract(
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
            }
            for tid, entry in summarise_by_term(changes).items()
        },
    }
    args.output.write_text(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
