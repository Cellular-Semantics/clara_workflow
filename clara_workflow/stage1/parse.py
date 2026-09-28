"""Parse `robot diff --format markdown` output into per-change records.

PROTOTYPE — see package docstring. Handles only the bullet shapes observed in
the fixtures under tests/fixtures/stage1/; unrecognised shapes yield
`kind="unknown"` rather than silently dropping.

The key design choice is granularity: one `Change` per axiom (added or removed),
carrying its own dbxref list. Stage-2/3 can then decide what justification is
required per change kind (NTR → whole term, synonym → that synonym, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator


# --- predicate IRI → change kind -------------------------------------------

_ANNOTATION_KINDS: dict[str, str] = {
    "http://purl.obolibrary.org/obo/IAO_0000115": "text_def",
    "http://www.w3.org/2000/01/rdf-schema#label": "label",
    "http://www.w3.org/2000/01/rdf-schema#comment": "comment",
    "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym": "synonym_exact",
    "http://www.geneontology.org/formats/oboInOwl#hasBroadSynonym": "synonym_broad",
    "http://www.geneontology.org/formats/oboInOwl#hasNarrowSynonym": "synonym_narrow",
    "http://www.geneontology.org/formats/oboInOwl#hasRelatedSynonym": "synonym_related",
    "http://www.w3.org/2002/07/owl#deprecated": "deprecated",
}

_DBXREF_PRED = "http://www.geneontology.org/formats/oboInOwl#hasDbXref"

# Change kinds whose content must be justified by a reference. Stage-2/3 only
# review changes in this set. Everything else in the diff (housekeeping,
# declarations, obsoletion bookkeeping) is kept in the output for traceability
# but is NOT reviewable.
#
# Explicitly *not* in this set:
#   class_declaration  — the fact that a class IRI exists is not a content claim;
#                        the actual content of a new term comes in via its
#                        text_def / synonyms / subclass / relationship axioms.
#   label              — a rename is not a content claim.
#   deprecated, replaced_by, term_tracker_item — obsoletion bookkeeping.
#   annotation (generic) — contributor, date, creator, editor_note, etc.
CONTENT_KINDS: frozenset[str] = frozenset({
    "text_def",
    "synonym_exact",
    "synonym_broad",
    "synonym_narrow",
    "synonym_related",
    "comment",
    "subclass",
    "relationship",
    "equivalent_class",
})

# The subset of CONTENT_KINDS whose value is a block of prose that must be
# broken into atomic assertions before reference checking. Other content kinds
# (synonym, subclass, relationship, equivalent_class) are already atomic — each
# is a single claim and can be checked as-is.
DECOMPOSABLE_KINDS: frozenset[str] = frozenset({
    "text_def",
    "comment",
})

# Predicate IRIs that unambiguously mark a term as being obsoleted / merged
# away. If any of these is **added** to a term, the term's other changes are
# obsoletion bookkeeping and are not reviewable.
_OBSOLETION_PREDICATES: frozenset[str] = frozenset({
    "http://www.w3.org/2002/07/owl#deprecated",
    "http://purl.obolibrary.org/obo/IAO_0100001",  # term replaced by
})


# --- data model ------------------------------------------------------------

@dataclass
class Change:
    term_id: str                    # CURIE form, e.g. CL:4052001
    term_label: str
    side: str                       # "added" | "removed"
    kind: str                       # see CONTENT_KINDS + {"annotation", "unknown"}
    predicate_iri: str | None = None
    predicate_label: str | None = None
    value: str | None = None        # literal text, or target IRI for class axioms
    value_label: str | None = None  # human label for class-axiom targets
    refs: list[str] = field(default_factory=list)   # dbxrefs attached to axiom
    raw: str = ""                   # original bullet line — keep for debugging

    @property
    def is_content(self) -> bool:
        return self.kind in CONTENT_KINDS


# --- parsing ---------------------------------------------------------------

_IRI_CURIE_PREFIXES = [
    ("http://purl.obolibrary.org/obo/", lambda s: s.replace("_", ":", 1)),
]


def _iri_to_curie(iri: str) -> str:
    for prefix, fn in _IRI_CURIE_PREFIXES:
        if iri.startswith(prefix):
            return fn(iri.removeprefix(prefix))
    return iri


# Header of a per-term block. Label may contain spaces & punctuation; IRI is in backticks.
_TERM_HEADER_RE = re.compile(r"^###\s+(?P<label>.+?)\s+`(?P<iri>[^`]+)`\s*$")
_SUBSECTION_RE = re.compile(r"^####\s+(?P<name>Added|Removed)\s*$")

# Markdown link: [text](url)
_LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<url>[^)]+)\)")


def _iter_links(s: str) -> Iterator[tuple[str, str]]:
    for m in _LINK_RE.finditer(s):
        yield m.group("text"), m.group("url")


def _bare_axiom(body: str) -> str:
    """Reduce a diff bullet to a bare Manchester-syntax axiom.

    `robot diff --format markdown --labels true` already emits class expressions
    in Manchester syntax; the labels just arrive wrapped in markdown links.
    Dropping the links leaves the axiom as an editor would write it, e.g.

        buccal mucosa cell EquivalentTo keratinocyte and (part of some mouth mucosa)
    """
    return re.sub(r"\s+", " ", _LINK_RE.sub(lambda m: m.group("text"), body)).strip()


def _parse_bullet(line: str, term_id: str, term_label: str, side: str) -> Change:
    """Parse one top-level `- ...` bullet into a Change.

    Observed shapes (see fixtures):
      - Class: [label](IRI)                         → new/removed class declaration
      - [subj] SubClassOf [target](IRI)             → plain subclass
      - [subj] SubClassOf [rel](IRI) some [tgt](IRI) → relationship restriction
      - [subj] [pred](IRI) "literal"                → annotation assertion
      - [subj] [pred](IRI) "literal"^^[type](IRI)   → typed literal
    """
    body = line.lstrip("- ").rstrip()
    raw = body

    # Class declaration.
    if body.startswith("Class:"):
        links = list(_iter_links(body))
        if links:
            label, iri = links[0]
            return Change(
                term_id=term_id, term_label=term_label, side=side,
                kind="class_declaration", value=iri, value_label=label, raw=raw,
            )

    # SubClassOf (plain or with restriction).
    if " SubClassOf " in body:
        _, _, rhs = body.partition(" SubClassOf ")
        links = list(_iter_links(rhs))
        if " some " in rhs and len(links) >= 2:
            rel_label, rel_iri = links[0]
            tgt_label, tgt_iri = links[1]
            return Change(
                term_id=term_id, term_label=term_label, side=side,
                kind="relationship",
                predicate_iri=rel_iri, predicate_label=rel_label,
                value=tgt_iri, value_label=tgt_label, raw=raw,
            )
        if links:
            tgt_label, tgt_iri = links[0]
            return Change(
                term_id=term_id, term_label=term_label, side=side,
                kind="subclass", value=tgt_iri, value_label=tgt_label, raw=raw,
            )

    # EquivalentClasses.
    if " EquivalentClasses " in body or "EquivalentTo" in body:
        # The logical definition is the claim to verify, so carry the axiom
        # itself rather than dropping it (issue #2).
        return Change(
            term_id=term_id, term_label=term_label, side=side,
            kind="equivalent_class", value=_bare_axiom(body), raw=raw,
        )

    # Annotation-style: [subj] [pred](IRI) <value>
    links = list(_iter_links(body))
    if len(links) >= 2:
        # First link is the subject (term); second is the predicate.
        pred_label, pred_iri = links[1]
        kind = _ANNOTATION_KINDS.get(pred_iri, "annotation")

        # Value is whatever trails after the predicate link.
        after = body.split(f"]({pred_iri})", 1)[1].strip() if f"]({pred_iri})" in body else ""
        value: str | None
        m = re.match(r'^"(?P<lit>(?:\\.|[^"\\])*)"', after)
        if m:
            value = m.group("lit")
        elif len(links) >= 3:
            value = links[2][1]            # use third link's URL as value
        else:
            value = after or None

        return Change(
            term_id=term_id, term_label=term_label, side=side, kind=kind,
            predicate_iri=pred_iri, predicate_label=pred_label,
            value=value, raw=raw,
        )

    return Change(
        term_id=term_id, term_label=term_label, side=side, kind="unknown", raw=raw,
    )


def _extract_dbxrefs(sub_bullets: list[str]) -> list[str]:
    """Pull `hasDbXref "PMID:xxx"` values from indented sub-bullets."""
    refs: list[str] = []
    for sb in sub_bullets:
        if _DBXREF_PRED not in sb:
            continue
        m = re.search(r'"([^"]+)"', sb)
        if m:
            refs.append(m.group(1))
    return refs


def parse_diff_markdown(text: str) -> list[Change]:
    """Parse a `robot diff --format markdown` document into a flat list of changes.

    Skips the preamble (`## Left`, `## Right`, `### Ontology imports`,
    `### Ontology annotations`) — per-term blocks are H3 headers whose label
    ends with a backtick-quoted IRI.
    """
    changes: list[Change] = []

    current_term_id: str | None = None
    current_term_label: str | None = None
    current_side: str | None = None
    pending: Change | None = None
    pending_sub: list[str] = []

    def flush() -> None:
        nonlocal pending, pending_sub
        if pending is not None:
            pending.refs = _extract_dbxrefs(pending_sub)
            changes.append(pending)
        pending = None
        pending_sub = []

    for line in text.splitlines():
        header = _TERM_HEADER_RE.match(line)
        if header:
            flush()
            iri = header.group("iri")
            # Skip preamble pseudo-sections (Ontology imports/annotations have no IRI).
            current_term_id = _iri_to_curie(iri)
            current_term_label = header.group("label")
            current_side = None
            continue

        sub = _SUBSECTION_RE.match(line)
        if sub:
            flush()
            current_side = sub.group("name").lower()
            continue

        if current_term_id is None or current_side is None:
            continue

        if line.startswith("- "):
            flush()
            pending = _parse_bullet(
                line, current_term_id, current_term_label or "", current_side,
            )
        elif line.startswith("  - ") or line.startswith("    - "):
            pending_sub.append(line)
        # blank / other lines: ignored (robot emits blank lines between sub-bullets)

    flush()
    return changes


# --- rollups ---------------------------------------------------------------

def summarise_by_term(changes: list[Change]) -> dict[str, dict]:
    """Group changes by term and tag per-term status.

    Adds three flags per term:
      is_new_term   — a class declaration was added for this IRI
      is_obsoleted  — owl:deprecated or IAO:0100001 (replaced_by) was added
      is_reviewable — term has at least one change in CONTENT_KINDS and is
                      not obsoleted (i.e. stage-2/3 should look at it)
    """
    out: dict[str, dict] = {}
    for c in changes:
        entry = out.setdefault(c.term_id, {
            "term_id": c.term_id,
            "term_label": c.term_label,
            "is_new_term": False,
            "is_obsoleted": False,
            "is_reviewable": False,
            "changes": [],
        })
        if c.kind == "class_declaration" and c.side == "added":
            entry["is_new_term"] = True
        if c.side == "added" and c.predicate_iri in _OBSOLETION_PREDICATES:
            entry["is_obsoleted"] = True
        entry["changes"].append(c)

    for entry in out.values():
        entry["is_reviewable"] = (
            not entry["is_obsoleted"]
            and any(c.is_content for c in entry["changes"])
        )
    return out


def reviewable_changes(changes: list[Change]) -> list[Change]:
    """Return only the changes that stages 2/3 should actually review.

    Drops:
      - all changes on obsoleted terms (nothing to justify — the term is going away)
      - non-content changes (declarations, labels, housekeeping annotations)
    """
    by_term = summarise_by_term(changes)
    obsoleted = {tid for tid, e in by_term.items() if e["is_obsoleted"]}
    return [
        c for c in changes
        if c.term_id not in obsoleted and c.is_content
    ]


def decomposable_changes(changes: list[Change]) -> list[Change]:
    """Subset of reviewable changes whose prose must be split into assertions.

    The verify-change skill only takes decomposable changes as input. Other
    reviewable changes (synonyms, subclass axioms, relationship restrictions,
    equivalent-class axioms) are atomic claims and get checked directly,
    without an intermediate decomposition step.
    """
    return [c for c in reviewable_changes(changes) if c.kind in DECOMPOSABLE_KINDS]


# --- text change pairing ---------------------------------------------------

@dataclass
class TextDelta:
    """One decomposable text axiom, paired across the removed/added sides.

    `robot diff` reports an annotated axiom as an independent removed + added
    bullet, and an OWL axiom's identity includes its annotations. So adding a
    dbxref to an untouched definition looks exactly like a definition rewrite
    unless the two sides are paired and their values compared.

    status:
      revised    — the prose changed (verify the new prose)
      refs_only  — the prose is byte-identical; only the refs changed (verify
                   the existing prose against `refs_added`, nothing else)
      added      — no matching removed side (new axiom on an existing term)
      removed    — no matching added side (axiom deleted)
    """
    term_id: str
    term_label: str
    kind: str                        # text_def | comment
    status: str                      # revised | refs_only | added | removed
    value: str | None = None         # the added (current) prose
    prior_value: str | None = None   # the removed (previous) prose
    refs: list[str] = field(default_factory=list)          # refs on the added side
    refs_added: list[str] = field(default_factory=list)
    refs_removed: list[str] = field(default_factory=list)


def text_deltas(changes: list[Change]) -> list[TextDelta]:
    """Pair removed/added decomposable text axioms per (term, kind).

    Obsoleted terms and non-content kinds are excluded, matching
    `reviewable_changes`.
    """
    grouped: dict[tuple[str, str], dict[str, list[Change]]] = {}
    for c in reviewable_changes(changes):
        if c.kind not in DECOMPOSABLE_KINDS:
            continue
        sides = grouped.setdefault((c.term_id, c.kind), {"added": [], "removed": []})
        sides[c.side].append(c)

    def _delta(kind: str, added: Change | None, removed: Change | None) -> TextDelta:
        src = added or removed
        assert src is not None
        if added is not None and removed is not None:
            status = "refs_only" if added.value == removed.value else "revised"
        else:
            status = "added" if added is not None else "removed"
        before = set(removed.refs) if removed is not None else set()
        after = set(added.refs) if added is not None else set()
        return TextDelta(
            term_id=src.term_id,
            term_label=src.term_label,
            kind=kind,
            status=status,
            value=added.value if added is not None else None,
            prior_value=removed.value if removed is not None else None,
            refs=list(added.refs) if added is not None else [],
            refs_added=sorted(after - before),
            refs_removed=sorted(before - after),
        )

    out: list[TextDelta] = []
    for (_term_id, kind), sides in grouped.items():
        added = list(sides["added"])
        removed = list(sides["removed"])

        # Pair identical prose first — those are ref-only edits, and matching
        # them by value keeps a genuine rewrite from stealing the partner.
        for a in list(added):
            match = next((r for r in removed if r.value == a.value), None)
            if match is not None:
                added.remove(a)
                removed.remove(match)
                out.append(_delta(kind, a, match))

        # Then pair what's left positionally; a term rarely carries more than
        # one definition, so this only matters for multi-comment edits.
        while added and removed:
            out.append(_delta(kind, added.pop(0), removed.pop(0)))

        out.extend(_delta(kind, a, None) for a in added)
        out.extend(_delta(kind, None, r) for r in removed)

    return out

# --- head-state definition refs -------------------------------------------

# One axiom per line in ROBOT's functional syntax, so a definition's dbxrefs are
# whatever `hasDbXref` annotations sit to the left of the IAO_0000115 predicate.
_DEF_PREDICATE_RE = re.compile(r"obo:IAO_0000115 obo:([A-Za-z]+_\d+)")
_XREF_VALUE_RE = re.compile(r'oboInOwl:hasDbXref "([^"]+)"')


def definition_refs(owl_text: str) -> dict[str, list[str]]:
    """Map term CURIE -> refs on that term's definition, from an edit file.

    `robot diff` only reports axioms that changed, so a PR that adds a logical
    definition to an untouched term carries no definition axiom at all. The
    references that justify a logical definition are the ones on the text
    definition it formalises, which means reading them out of the head state
    rather than the diff.

    Parsed line-wise on purpose: a nested-paren regex misses definitions whose
    dbxref values contain brackets (e.g. Wikipedia URLs with parenthesised
    disambiguators).
    """
    out: dict[str, list[str]] = {}
    for line in owl_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("AnnotationAssertion("):
            continue
        match = _DEF_PREDICATE_RE.search(stripped)
        if match is None:
            continue
        term_id = match.group(1).replace("_", ":", 1)
        out[term_id] = _XREF_VALUE_RE.findall(stripped[: match.start()])
    return out
