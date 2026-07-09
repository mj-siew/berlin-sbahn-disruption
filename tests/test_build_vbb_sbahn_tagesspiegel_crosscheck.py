from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_vbb_sbahn_tagesspiegel_crosscheck import (  # noqa: E402
    PUNCTUALITY_P3,
    RELIABILITY_ZG,
    build_tagesspiegel_crosscheck,
    summarize_metric_window,
)


GENERATED_AT = "2026-07-09T21:30:00+00:00"


def sample_rows() -> list[dict[str, str]]:
    punctuality = [
        "94.32",
        "92.59",
        "93.45",
        "93.33",
        "92.49",
        "91.92",
        "91.44",
        "93.15",
        "92.66",
        "92.86",
        "93.23",
        "93.88",
    ]
    reliability = [
        "95.26",
        "94.28",
        "94.40",
        "91.98",
        "94.42",
        "92.14",
        "93.17",
        "94.11",
        "93.09",
        "94.57",
        "95.00",
        "94.94",
    ]

    rows: list[dict[str, str]] = []
    for month, value in enumerate(punctuality, start=1):
        rows.append(
            {
                "period": f"2025-{month:02d}",
                "entity_scope": "network",
                "metric_id": PUNCTUALITY_P3,
                "value_percent": value,
            }
        )
    for month, value in enumerate(reliability, start=1):
        rows.append(
            {
                "period": f"2025-{month:02d}",
                "entity_scope": "network",
                "metric_id": RELIABILITY_ZG,
                "value_percent": value,
            }
        )
    return rows


def test_summarize_metric_window_uses_equal_weight_monthly_average() -> None:
    summary = summarize_metric_window(
        sample_rows(),
        metric_id=PUNCTUALITY_P3,
        start_period="2025-01",
        end_period="2025-09",
    )

    assert summary.month_count == 9
    assert summary.average_percent == "92.817"
    assert summary.inverse_percent == "7.183"
    assert summary.rounded_inverse_percent == "7.2"


def test_build_tagesspiegel_crosscheck_flags_direct_and_non_direct_matches() -> None:
    payload = build_tagesspiegel_crosscheck(
        sample_rows(),
        generated_at=GENERATED_AT,
        input_csv=Path("data/vbb_sbahn_monthly_network_trends_2023_2026.csv"),
    )

    assert payload["generated_at"] == GENERATED_AT
    assert payload["comparison_note"]["verdict"] == "mixed_comparability"

    checks = {check["claim_id"]: check for check in payload["claim_checks"]}
    assert checks["tagesspiegel_2025_late_trains_share"]["comparison_validity"] == (
        "approximate"
    )
    assert checks["tagesspiegel_2025_late_trains_share"]["alignment"] == "aligns"
    assert checks["tagesspiegel_2025_cancelled_trains_share"]["comparison_validity"] == (
        "not_direct"
    )
    assert checks["tagesspiegel_jan_sep_2025_disruptions"]["alignment"] == (
        "cannot_compare_directly"
    )
    assert checks["issue_target_900_plus_disruptions"]["comparison_validity"] == (
        "not_verified"
    )

    annual = payload["supporting_period_summaries"]["annual_2025"]
    assert annual[PUNCTUALITY_P3]["rounded_inverse_percent"] == "7.1"
    assert annual[RELIABILITY_ZG]["rounded_inverse_percent"] == "6.1"
