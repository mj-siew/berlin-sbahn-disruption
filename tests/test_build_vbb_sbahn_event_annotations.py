from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_vbb_sbahn_event_annotations import (  # noqa: E402
    ANALYSIS_WINDOW_END,
    ANALYSIS_WINDOW_START,
    CURATED_ANNOTATIONS,
    build_annotation_metadata,
    build_annotation_rows,
)


GENERATED_AT = "2026-07-09T20:30:00+00:00"


def test_build_annotation_rows_are_sorted_and_chart_ready() -> None:
    rows = build_annotation_rows(CURATED_ANNOTATIONS)

    assert rows[0]["event_id"] == "cable_theft_landsberger_allee_2024_12"
    assert rows[-1]["event_id"] == "cable_theft_baumschulenweg_2026_05"

    wollank = next(
        row for row in rows if row["event_id"] == "wollankstrasse_full_closure_2025_03"
    )
    assert wollank["annotation_kind"] == "range"
    assert wollank["start_period"] == "2025-03"
    assert wollank["end_period"] == "2025-03"
    assert wollank["affected_lines"] == "S1,S8,S25,S26,S85"
    assert wollank["confidence_level"] == "high"


def test_build_annotation_metadata_keeps_sources_and_caveats() -> None:
    metadata = build_annotation_metadata(
        CURATED_ANNOTATIONS,
        generated_at=GENERATED_AT,
        analysis_window_start=ANALYSIS_WINDOW_START,
        analysis_window_end=ANALYSIS_WINDOW_END,
    )

    assert metadata["generated_at"] == GENERATED_AT
    assert metadata["analysis_window"] == {
        "start_period": ANALYSIS_WINDOW_START,
        "end_period": ANALYSIS_WINDOW_END,
    }
    assert metadata["event_count"] == len(CURATED_ANNOTATIONS)

    gesundbrunnen = next(
        event
        for event in metadata["events"]
        if event["event_id"] == "stellwerk_gesundbrunnen_2025_04"
    )
    assert gesundbrunnen["source_count"] == 1
    assert "cable-damage event" in gesundbrunnen["causal_caveat"]
    assert gesundbrunnen["sources"][0]["publisher"] == "rbb24"

    baumschulenweg = next(
        event
        for event in metadata["events"]
        if event["event_id"] == "cable_theft_baumschulenweg_2026_05"
    )
    assert baumschulenweg["source_count"] == 2
    assert {
        source["publisher"] for source in baumschulenweg["sources"]
    } == {"rbb24", "Tagesspiegel / dpa"}
