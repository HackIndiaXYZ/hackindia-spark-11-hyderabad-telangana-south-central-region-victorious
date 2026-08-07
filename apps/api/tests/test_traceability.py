"""Traceability: staleness detection and change impact analysis.

Pure domain tests — no database, no event loop. That they need neither is the
point of ADR-0003's layering: the rules that make this platform different from a
code generator are testable in isolation.
"""

from __future__ import annotations

from app.domain.traceability import (
    TraceEdge,
    TraceKind,
    analyse_impact,
    stale_artifact_ids,
    stale_edges,
    upstream_of,
)

PROJECT = "prj_test"


def edge(
    upstream: str,
    downstream: str,
    *,
    version: int = 1,
    kind: TraceKind = TraceKind.DERIVES_FROM,
) -> TraceEdge:
    return TraceEdge(
        project_id=PROJECT,
        upstream_artifact_id=upstream,
        downstream_artifact_id=downstream,
        kind=kind,
        upstream_version=version,
    )


# --- Staleness ----------------------------------------------------------------


def test_edge_is_fresh_when_upstream_has_not_moved() -> None:
    edges = [edge("requirements", "architecture", version=1)]

    assert stale_edges(edges, {"requirements": 1}) == []


def test_edge_is_stale_when_upstream_advances() -> None:
    """The core mechanism: revising requirements makes the architecture stale."""
    edges = [edge("requirements", "architecture", version=1)]

    result = stale_edges(edges, {"requirements": 2})

    assert len(result) == 1
    assert result[0].versions_behind == 1
    assert result[0].edge.downstream_artifact_id == "architecture"


def test_versions_behind_counts_multiple_revisions() -> None:
    edges = [edge("requirements", "architecture", version=1)]

    assert stale_edges(edges, {"requirements": 5})[0].versions_behind == 4


def test_unknown_upstream_is_skipped_rather_than_assumed_stale() -> None:
    """A missing artifact must not manufacture a false staleness alarm."""
    edges = [edge("ghost", "architecture", version=1)]

    assert stale_edges(edges, {}) == []


def test_stale_artifact_ids_deduplicates_across_edges() -> None:
    """An artifact stale via two upstreams is reported once."""
    edges = [
        edge("requirements", "architecture", version=1),
        edge("business_analysis", "architecture", version=1),
    ]

    result = stale_artifact_ids(edges, {"requirements": 2, "business_analysis": 3})

    assert result == {"architecture"}


# --- Impact analysis ----------------------------------------------------------


def test_direct_impact_is_depth_one() -> None:
    edges = [edge("requirements", "architecture")]

    analysis = analyse_impact("requirements", edges)

    assert analysis.artifact_ids == ["architecture"]
    assert analysis.impacted[0].depth == 1
    assert analysis.direct == analysis.impacted


def test_impact_is_transitive() -> None:
    """The question no existing tool answers, per 04_Existing_Solutions.md."""
    edges = [
        edge("requirements", "architecture"),
        edge("architecture", "api_contract"),
        edge("api_contract", "source_file"),
        edge("source_file", "test_cases"),
    ]

    analysis = analyse_impact("requirements", edges)

    assert analysis.artifact_ids == ["architecture", "api_contract", "source_file", "test_cases"]
    assert [item.depth for item in analysis.impacted] == [1, 2, 3, 4]


def test_impact_records_the_path_to_each_artifact() -> None:
    """The path explains *why* an artifact is affected, not merely that it is."""
    edges = [
        edge("requirements", "architecture"),
        edge("architecture", "source_file"),
    ]

    analysis = analyse_impact("requirements", edges)
    source_file = next(i for i in analysis.impacted if i.artifact_id == "source_file")

    assert source_file.path == ["requirements", "architecture", "source_file"]


def test_impact_excludes_unrelated_branches() -> None:
    """Precision matters: over-reporting impact trains users to ignore it."""
    edges = [
        edge("requirements", "architecture"),
        edge("unrelated_doc", "unrelated_child"),
    ]

    analysis = analyse_impact("requirements", edges)

    assert analysis.artifact_ids == ["architecture"]


def test_impact_terminates_on_cyclic_graphs() -> None:
    """Real project graphs contain feedback loops; traversal must not hang."""
    edges = [
        edge("requirements", "architecture"),
        edge("architecture", "decision"),
        edge("decision", "requirements"),
    ]

    analysis = analyse_impact("requirements", edges)

    assert set(analysis.artifact_ids) == {"architecture", "decision"}
    assert "requirements" not in analysis.artifact_ids


def test_impact_reports_shortest_path_when_several_exist() -> None:
    """Breadth-first: the most direct explanation wins."""
    edges = [
        edge("requirements", "architecture"),
        edge("requirements", "api_contract"),
        edge("architecture", "api_contract"),
    ]

    analysis = analyse_impact("requirements", edges)
    api_contract = next(i for i in analysis.impacted if i.artifact_id == "api_contract")

    assert api_contract.depth == 1


def test_max_depth_limits_traversal() -> None:
    edges = [
        edge("a", "b"),
        edge("b", "c"),
        edge("c", "d"),
    ]

    analysis = analyse_impact("a", edges, max_depth=2)

    assert analysis.artifact_ids == ["b", "c"]


def test_leaf_artifact_has_empty_impact() -> None:
    analysis = analyse_impact("test_cases", [edge("source_file", "test_cases")])

    assert analysis.is_empty


def test_edge_kind_is_preserved_through_analysis() -> None:
    """Milestone 8 uses the kind to propose proportionate re-synchronisation."""
    edges = [edge("acceptance_criteria", "test_cases", kind=TraceKind.TESTS)]

    analysis = analyse_impact("acceptance_criteria", edges)

    assert analysis.impacted[0].via_kind is TraceKind.TESTS


# --- Reverse traversal --------------------------------------------------------


def test_upstream_of_answers_why_this_artifact_exists() -> None:
    edges = [
        edge("requirements", "architecture"),
        edge("business_analysis", "architecture"),
        edge("architecture", "source_file"),
    ]

    result = upstream_of("architecture", edges)

    assert {e.upstream_artifact_id for e in result} == {"requirements", "business_analysis"}
