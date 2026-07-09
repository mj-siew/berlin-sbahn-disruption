from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_final_report import (  # noqa: E402
    build_annual_network_svg,
    build_event_legend,
    build_line_deltas,
    build_line_comparison_svg,
    build_report_summary,
    build_network_svg,
    build_route_comparison_svg,
    load_annotation_rows,
    load_metric_rows,
    render_html,
)


NETWORK_CSV = Path("data/vbb_sbahn_monthly_network_trends_2023_2026.csv")
LINE_CSV = Path("data/vbb_sbahn_monthly_line_trends_2023_2026.csv")
QUALITY_CSV = Path("data/vbb_sbahn_quality_2019_onward.csv")
ANNOTATIONS_CSV = Path("data/vbb_sbahn_event_annotations_2023_2026.csv")


def build_test_summary():
    return build_report_summary(
        load_metric_rows(NETWORK_CSV),
        load_metric_rows(LINE_CSV),
        source_urls={
            "primary_quality_tool": "https://example.com/vbb-quality",
            "quality_archive": "https://example.com/vbb-archive",
        },
    )


def test_build_report_summary_captures_mixed_headline_conclusion() -> None:
    summary = build_test_summary()

    assert summary.observed_until == "2026-05"
    assert summary.conclusion_label == "divergence"

    full_year_values = {
        (item.metric_id, item.label): round(item.value_percent, 2)
        for item in summary.full_year_summaries
    }
    assert full_year_values[("punctuality_p3", "2025")] == 92.94
    assert full_year_values[("reliability_zg", "2024")] == 92.14

    ytd_values = {
        (item.metric_id, item.label): round(item.value_percent, 2)
        for item in summary.comparable_ytd_summaries
    }
    assert ytd_values[("punctuality_p3", "2026 YTD (Jan-May)")] == 94.14
    assert ytd_values[("reliability_zg", "2026 YTD (Jan-May)")] == 94.99


def test_full_history_surfaces_diverging_network_and_personal_route_signals() -> None:
    quality_rows = load_metric_rows(QUALITY_CSV)
    summary = build_report_summary(
        [row for row in quality_rows if row.entity_scope == "network"],
        [row for row in quality_rows if row.entity_scope == "line"],
        source_urls={
            "primary_quality_tool": "https://example.com/vbb-quality",
            "quality_archive": "https://example.com/vbb-archive",
        },
    )

    assert summary.conclusion_label == "divergence"
    assert len(summary.full_year_summaries) == 14
    assert {
        item.year: item.months_below_reference
        for item in summary.punctuality_exposures
        if item.year in {2023, 2024, 2025}
    } == {2023: 3, 2024: 4, 2025: 6}

    route_scores = {
        (item.entity_id, item.metric_id): item for item in summary.route_scorecards
    }
    assert round(route_scores[("S25", "punctuality_p3")].network_gap_percent_points, 2) == -1.95
    assert round(route_scores[("S25", "reliability_zg")].delta_percent_points, 2) == 0.11
    assert round(route_scores[("S26", "reliability_zg")].delta_percent_points, 2) == 5.45
    overall_scores = {item.entity_id: item for item in summary.route_overall_scores}
    assert round(overall_scores["S25"].delta_percent_points, 2) == -0.74
    assert round(overall_scores["S26"].delta_percent_points, 2) == 2.11


def test_report_summary_exposes_a_configurable_comparison_window() -> None:
    quality_rows = load_metric_rows(QUALITY_CSV)
    summary = build_report_summary(
        [row for row in quality_rows if row.entity_scope == "network"],
        [row for row in quality_rows if row.entity_scope == "line"],
        source_urls={
            "primary_quality_tool": "https://example.com/vbb-quality",
            "quality_archive": "https://example.com/vbb-archive",
        },
        baseline_year=2024,
        comparison_year=2025,
        punctuality_reference_percent=92.5,
    )

    assert summary.baseline_year == 2024
    assert summary.comparison_year == 2025
    assert summary.punctuality_reference_percent == 92.5
    assert all(delta.baseline_year == 2024 for delta in summary.line_deltas)


def test_build_line_deltas_surfaces_largest_punctuality_drop() -> None:
    deltas = [
        item
        for item in build_line_deltas(load_metric_rows(LINE_CSV))
        if item.metric_id == "punctuality_p3"
    ]

    assert deltas[0].entity_id == "S7"
    assert round(deltas[0].delta_percent_points, 2) == -2.69


def test_render_html_is_offline_svg_first_and_surfaces_full_window() -> None:
    summary = build_test_summary()
    html = render_html(
        summary,
        network_svg=build_network_svg(
            load_metric_rows(NETWORK_CSV),
            load_annotation_rows(ANNOTATIONS_CSV),
        ),
        annual_svg=build_annual_network_svg(summary),
        line_svg=build_line_comparison_svg(summary.line_deltas),
        route_svg=build_route_comparison_svg(
            load_metric_rows(QUALITY_CSV),
            summary.route_scorecards,
        ),
        network_rows=load_metric_rows(NETWORK_CSV),
        annotations=load_annotation_rows(ANNOTATIONS_CSV),
    )

    assert "plotly" not in html.lower()
    assert "cdn" not in html.lower()
    assert "<script" not in html.lower()
    assert "network-svg" in html
    assert "annual-svg" in html
    assert "line-svg" in html
    assert 'viewBox="0 0 1160 570"' in html
    assert "2023 mean" in html
    assert "2025 mean" in html
    assert "2026 Jan-May" in html
    assert "2026 has 5 observed months" in html
    assert 'aria-labelledby="network-chart-title network-chart-desc"' in html
    assert "Personal route deep dive" in html
    assert "S25" in html
    assert "S26" in html
    assert "External check" not in html
    assert "Tagesspiegel" not in html


def test_event_legend_exposes_loaded_context_without_hovering_chart_markers() -> None:
    annotations = load_annotation_rows(ANNOTATIONS_CSV)
    legend = build_event_legend(annotations)

    assert "event-legend" in legend
    assert "Cable theft: Landsberger Allee" in legend
    assert "S41, S42, S8, S85" in legend
    assert "Wollankstrasse full closure" in legend
