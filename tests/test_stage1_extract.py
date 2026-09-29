"""Tests for the stage-1 extractor's ROBOT-facing plumbing.

Unlike test_stage1_parse.py (pure functions over cached fixtures), these
exercise the parts of extract.py that actually shell out to `robot`, so they
skip outright if `robot` isn't on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from clara_workflow.stage1.extract import (
    _robot_convert_to_ofn,
    _strip_imports,
    extract,
)
from clara_workflow.stage1.parse import definition_refs

ROBOT = shutil.which("robot")
requires_robot = pytest.mark.skipif(ROBOT is None, reason="robot not on PATH")


# --- _strip_imports ----------------------------------------------------

def test_strip_imports_drops_obo_import_lines():
    text = (
        "format-version: 1.2\n"
        "import: http://purl.obolibrary.org/obo/uberon/components/foo.owl\n"
        "ontology: uberon/test\n"
    )
    stripped = _strip_imports(text)
    assert "import:" not in stripped
    assert "ontology: uberon/test" in stripped


def test_strip_imports_drops_owl_functional_import_lines():
    text = (
        "Prefix(obo:=<http://purl.obolibrary.org/obo/>)\n"
        "Ontology(<http://purl.obolibrary.org/obo/cl.owl>\n"
        "Import(<http://purl.obolibrary.org/obo/cl/components/foo.owl>)\n"
        "Declaration(Class(obo:CL_0000001))\n"
        ")\n"
    )
    stripped = _strip_imports(text)
    assert "Import(" not in stripped
    assert "Declaration(Class(obo:CL_0000001))" in stripped


def test_strip_imports_leaves_unrelated_lines_untouched():
    text = "def: \"An import-related structure.\" [GOC:test]\n"
    assert _strip_imports(text) == text


# --- _robot_convert_to_ofn ----------------------------------------------

_OBO_TERM = """format-version: 1.2
ontology: uberon/test

[Term]
id: UBERON:0004177
name: hemopoietic organ
def: "Organ that produces blood cells." [GOC:Obol, DOI:10.9999/test.uberon.4177]
"""


@requires_robot
def test_robot_convert_to_ofn_preserves_dbxrefs_from_obo(tmp_path: Path):
    """OBO input, once converted, must still yield refs via definition_refs().

    This is the crux of the OBO-support fix: definition_refs() only
    understands functional-syntax AnnotationAssertion(...) lines, so an OBO
    edit file needs converting first, with the obo:/oboInOwl: curie prefixes
    it expects.
    """
    src = tmp_path / "right.obo"
    src.write_text(_OBO_TERM)
    out = tmp_path / "right.ofn"

    _robot_convert_to_ofn(src, out, robot=ROBOT)

    refs = definition_refs(out.read_text())
    assert refs["UBERON:0004177"] == ["DOI:10.9999/test.uberon.4177", "GOC:Obol"]


# --- extract() end to end -------------------------------------------------

def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.org"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    return repo


@requires_robot
def test_extract_end_to_end_against_obo_edit_file_with_broken_import(tmp_path: Path):
    """Regression test for two real-world failures found reviewing uberon:

    1. `robot diff` fails outright on an edit file with an unresolvable
       `import:` PURL, unless imports are stripped first.
    2. Without converting to functional syntax first, `definition_refs()`
       silently returns nothing for an OBO edit file.
    """
    repo = _init_repo(tmp_path)
    edit_file = repo / "uberon-edit.obo"

    base = """format-version: 1.2
ontology: uberon/test
import: http://purl.obolibrary.org/obo/uberon/components/does-not-exist.owl

[Term]
id: UBERON:0004177
name: hemopoietic organ
def: "Organ that is part of the hematopoietic system." [GOC:Obol]
"""
    edit_file.write_text(base)
    subprocess.run(["git", "add", "uberon-edit.obo"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    revised = base.replace(
        'def: "Organ that is part of the hematopoietic system." [GOC:Obol]',
        'def: "Organ that produces, stores, or regulates the maturation of '
        'blood cells, and is part of the hematopoietic system." '
        '[GOC:Obol, DOI:10.9999/test.uberon.4177]',
    )
    edit_file.write_text(revised)
    subprocess.run(["git", "add", "uberon-edit.obo"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "revise def"], cwd=repo, check=True)
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    changes, head_definition_refs = extract(
        repo=repo,
        left_ref=base_sha,
        right_ref=head_sha,
        edit_file="uberon-edit.obo",
        robot=ROBOT,
    )

    added_defs = [c for c in changes if c.kind == "text_def" and c.side == "added"]
    assert len(added_defs) == 1
    assert added_defs[0].term_id == "UBERON:0004177"
    assert "DOI:10.9999/test.uberon.4177" in added_defs[0].refs

    # This term's definition wasn't left untouched, but the fallback path
    # (used when a *different* axiom needs justifying from an existing,
    # unchanged definition) must be populated too, proving OBO input reaches
    # definition_refs() correctly rather than silently returning {}.
    assert head_definition_refs.get("UBERON:0004177") == [
        "DOI:10.9999/test.uberon.4177",
        "GOC:Obol",
    ]
