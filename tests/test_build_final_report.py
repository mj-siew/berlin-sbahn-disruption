from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_final_report import (  # noqa: E402
    build_cross_checks,
    build_line_deltas,
    build_report_summary,
    load_metric_rows,
)


NETWORK_CSV = Path("data/vbb_sbahn_monthly_network_trends_2023_2026.csv")
LINE_CSV = Path("data/vbb_sbahn_monthly_line_trends_2023_2026.csv")


def test_build_report_summary_captures_mixed_headline_conclusion() -> None:
    summary = build_report_summary(
        load_metric_rows(NETWORK_CSV),
        load_metric_rows(LINE_CSV),
        source_urls={
            "primary_quality_tool": "https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaet-berliner-s-bahn/",
            "quality_archive": "https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaetsbilanzen/",
        },
    )

    assert summary.observed_until == "2026-05"
    assert summary.conclusion_label == "mixed"

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


def test_build_cross_checks_matches_tagesspiegel_punctuality_windows() -> None:
    cross_checks = {
        item.slug: item for item in build_cross_checks(load_metric_rows(NETWORK_CSV))
    }

    check_2024 = cross_checks["tagesspiegel_2024_q1_q3"]
    assert check_2024.window_label == "Jan-Sep 2024"
    assert round(check_2024.observed_value, 2) == 93.92
    assert abs(check_2024.difference_percent_points) < 0.05

    check_2025 = cross_checks["tagesspiegel_2025_q1_q3"]
    assert round(check_2025.observed_value, 2) == 92.82
    assert abs(check_2025.difference_percent_points) < 0.1


def test_build_line_deltas_surfaces_largest_punctuality_drop() -> None:
    deltas = [
        item
        for item in build_line_deltas(load_metric_rows(LINE_CSV))
        if item.metric_id == "punctuality_p3"
    ]

    assert deltas[0].entity_id == "S7"
    assert round(deltas[0].delta_percent_points, 2) == -2.69
