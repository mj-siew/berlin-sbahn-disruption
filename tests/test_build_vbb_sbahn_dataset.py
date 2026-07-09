from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_vbb_sbahn_dataset import (  # noqa: E402
    DEFAULT_SOURCE_URL,
    KpiRow,
    aggregate_monthly_rows,
    parse_filter_config,
    parse_line_rows,
    parse_network_rows,
    soup_from_html,
)


FIXTURE = Path(__file__).parent / "fixtures" / "vbb_sbahn_overview_fixture.html"
EXTRACTED_AT = "2026-07-09T20:00:00+00:00"


def read_fixture() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_filter_config_reads_action_years_and_months() -> None:
    config = parse_filter_config(read_fixture(), source_url=DEFAULT_SOURCE_URL)

    assert config.action_url.startswith(DEFAULT_SOURCE_URL)
    assert config.years == [2026, 2025]
    assert config.months == [13, 2, 1]
    assert (
        config.hidden_fields["tx_sbahnqualitaet_sbahnoverview[__trustedProperties]"]
        == "fixture"
    )


def test_parse_network_rows_skips_aggregate_and_missing_values() -> None:
    soup = soup_from_html(read_fixture())

    rows = parse_network_rows(
        soup,
        year=2026,
        months=[13, 1, 2, 3],
        extracted_at=EXTRACTED_AT,
    )

    values = {(row.period, row.metric_id): row.value_percent for row in rows}
    assert values[("2026-01", "punctuality_p0")] == "70.10"
    assert values[("2026-02", "punctuality_p3")] == "94.34"
    assert values[("2026-02", "reliability_zg")] == "96.20"
    assert ("2026-03", "punctuality_p3") not in values
    assert all(row.entity_scope == "network" for row in rows)


def test_parse_line_rows_emits_drilldown_metrics() -> None:
    soup = soup_from_html(read_fixture())

    rows = parse_line_rows(soup, extracted_at=EXTRACTED_AT)

    assert len(rows) == 6
    s1 = {
        row.metric_id: row.value_percent
        for row in rows
        if row.entity_id == "S1" and row.period == "2026-02"
    }
    assert s1 == {
        "overall_ranking": "97.29",
        "punctuality_p3": "96.46",
        "reliability_zg": "98.11",
    }
    assert {row.comparability_class for row in rows} == {"primary_drilldown"}


def test_aggregate_monthly_rows_filters_range_and_preserves_monthly_values() -> None:
    rows = [
        KpiRow(
            period="2022-12",
            year=2022,
            month=12,
            entity_scope="network",
            entity_id="Gesamtnetz",
            metric_id="punctuality_p3",
            value_percent="95.00",
            comparability_class="primary_headline",
            source_artifact="VBB Berlin S-Bahn quality tool",
            source_url=DEFAULT_SOURCE_URL,
            extracted_at=EXTRACTED_AT,
            notes="Network punctuality, arrivals no more than 3:59 minutes late.",
        ),
        KpiRow(
            period="2023-01",
            year=2023,
            month=1,
            entity_scope="network",
            entity_id="Gesamtnetz",
            metric_id="punctuality_p3",
            value_percent="96.10",
            comparability_class="primary_headline",
            source_artifact="VBB Berlin S-Bahn quality tool",
            source_url=DEFAULT_SOURCE_URL,
            extracted_at=EXTRACTED_AT,
            notes="Network punctuality, arrivals no more than 3:59 minutes late.",
        ),
        KpiRow(
            period="2023-01",
            year=2023,
            month=1,
            entity_scope="line",
            entity_id="S1",
            metric_id="reliability_zg",
            value_percent="97.20",
            comparability_class="primary_drilldown",
            source_artifact="VBB Berlin S-Bahn quality tool",
            source_url=DEFAULT_SOURCE_URL,
            extracted_at=EXTRACTED_AT,
            notes="Line reliability, delivered train-km over scheduled train-km.",
        ),
        KpiRow(
            period="2026-05",
            year=2026,
            month=5,
            entity_scope="line",
            entity_id="S1",
            metric_id="overall_ranking",
            value_percent="98.40",
            comparability_class="primary_drilldown",
            source_artifact="VBB Berlin S-Bahn quality tool",
            source_url=DEFAULT_SOURCE_URL,
            extracted_at=EXTRACTED_AT,
            notes="Line overall score published by VBB for comparison.",
        ),
    ]

    monthly_rows = aggregate_monthly_rows(rows)

    assert [(row.period, row.entity_scope, row.metric_id) for row in monthly_rows] == [
        ("2023-01", "network", "punctuality_p3"),
        ("2023-01", "line", "reliability_zg"),
        ("2026-05", "line", "overall_ranking"),
    ]
    assert [row.value_percent for row in monthly_rows] == ["96.10", "97.20", "98.40"]
    assert {row.coverage_status for row in monthly_rows} == {"observed"}
    assert monthly_rows[0].metric_definition == (
        "Share of arrivals no more than 3:59 minutes late."
    )
