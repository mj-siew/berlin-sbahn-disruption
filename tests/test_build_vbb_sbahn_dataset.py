from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_vbb_sbahn_dataset import (  # noqa: E402
    DEFAULT_SOURCE_URL,
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
