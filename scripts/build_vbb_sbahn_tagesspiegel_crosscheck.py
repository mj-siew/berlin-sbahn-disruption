from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


DEFAULT_INPUT_CSV = Path("data/vbb_sbahn_monthly_network_trends_2023_2026.csv")
DEFAULT_OUTPUT_JSON = Path("data/vbb_sbahn_tagesspiegel_crosscheck_2025.json")

PUNCTUALITY_P3 = "punctuality_p3"
RELIABILITY_ZG = "reliability_zg"

METRIC_DEFINITIONS = {
    PUNCTUALITY_P3: "Share of arrivals no more than 3:59 minutes late.",
    RELIABILITY_ZG: (
        "Delivered train-km divided by scheduled train-km on the day-current timetable."
    ),
}


@dataclass(frozen=True)
class SourceReference:
    title: str
    url: str
    publisher: str
    published_date: str
    access_role: str
    note: str


@dataclass(frozen=True)
class MetricWindowSummary:
    metric_id: str
    start_period: str
    end_period: str
    month_count: int
    average_percent: str
    inverse_percent: str
    rounded_inverse_percent: str


SOURCE_CHAIN = {
    "secondary_reporting": (
        SourceReference(
            title=(
                "Lage hat sich 2025 verschaerft: 135.298 Zuege kamen zu spaet - die "
                "Berliner S-Bahn wird immer unzuverlaessiger"
            ),
            url=(
                "https://www.tagesspiegel.de/berlin/"
                "lage-hat-sich-2025-verscharft-135298-zuge-kamen-zu-spat--die-"
                "berliner-s-bahn-wird-immer-unzuverlassiger-15087045.html"
            ),
            publisher="Tagesspiegel",
            published_date="2025-12-30",
            access_role="secondary_reporting",
            note=(
                "Reports Jan-Sep 2025 punctuality at 92.9%, 29,390 cancelled trains, "
                "and 34,414 operational disruptions from an S-Bahn report to the Berlin "
                "parliament."
            ),
        ),
        SourceReference(
            title=(
                "Schon wieder Stoerung im Betriebsablauf? Wo die Berliner S-Bahn am "
                "haeufigsten aus dem Takt geraet"
            ),
            url=(
                "https://interaktiv.tagesspiegel.de/lab/"
                "schon-wieder-stoerung-im-betriebsablauf-wo-die-berliner-s-bahn-am-"
                "haeufigsten-aus-dem-takt-geraet/"
            ),
            publisher="Tagesspiegel",
            published_date="2026-06-17",
            access_role="secondary_reporting",
            note=(
                "States that 7.1% of trains arrived more than four minutes late in 2025, "
                "about 6% fell out, about 46,000 disruptions were recorded in 2025, and "
                "Tagesspiegel's filtered rider-facing notice sample contained 831 notices "
                "from 2025-12-01 through 2026-04-30."
            ),
        ),
    ),
    "public_primary_sources": (
        SourceReference(
            title=(
                "Projektbericht Qualitaetsoffensive S-Bahn Plus fuer das zweite und "
                "dritte Quartal 2025"
            ),
            url="https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-0054.J-v.pdf",
            publisher="Abgeordnetenhaus Berlin / SenUMVK",
            published_date="2025-11-20",
            access_role="public_primary_source",
            note=(
                "Public PDF trace for the Jan-Sep 2025 figures: 92.9% punctuality, a "
                "5.28% operational cancellation-km rate, and 34,414 operational "
                "disruptions."
            ),
        ),
        SourceReference(
            title=(
                "Projektbericht Qualitaetsoffensive S-Bahn Plus fuer das vierte Quartal "
                "2025 und das erste Quartal 2026"
            ),
            url="https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-0054.K-v.pdf",
            publisher="Abgeordnetenhaus Berlin / SenUMVK",
            published_date="2026-05-26",
            access_role="public_primary_source",
            note=(
                "Explains that the report's disruption count records every operational "
                "irregularity once, regardless of duration or impact, which matters for "
                "metric comparability."
            ),
        ),
    ),
}


def quantize(value: Decimal, pattern: str) -> Decimal:
    return value.quantize(Decimal(pattern), rounding=ROUND_HALF_UP)


def format_decimal(value: Decimal, pattern: str) -> str:
    return f"{quantize(value, pattern)}"


def load_network_rows(input_csv: Path) -> list[dict[str, str]]:
    with input_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            row
            for row in reader
            if row["entity_scope"] == "network" and row["metric_id"] in METRIC_DEFINITIONS
        ]


def summarize_metric_window(
    rows: list[dict[str, str]],
    *,
    metric_id: str,
    start_period: str,
    end_period: str,
) -> MetricWindowSummary:
    values = [
        Decimal(row["value_percent"])
        for row in rows
        if row["metric_id"] == metric_id and start_period <= row["period"] <= end_period
    ]
    if not values:
        raise ValueError(
            f"No network rows found for metric {metric_id} between {start_period} and {end_period}"
        )

    average = sum(values) / Decimal(len(values))
    inverse = Decimal("100") - average
    return MetricWindowSummary(
        metric_id=metric_id,
        start_period=start_period,
        end_period=end_period,
        month_count=len(values),
        average_percent=format_decimal(average, "0.001"),
        inverse_percent=format_decimal(inverse, "0.001"),
        rounded_inverse_percent=format_decimal(inverse, "0.1"),
    )


def source_dicts(key: str) -> list[dict[str, str]]:
    return [asdict(source) for source in SOURCE_CHAIN[key]]


def build_tagesspiegel_crosscheck(
    rows: list[dict[str, str]],
    *,
    generated_at: str,
    input_csv: Path,
) -> dict[str, object]:
    annual_punctuality = summarize_metric_window(
        rows,
        metric_id=PUNCTUALITY_P3,
        start_period="2025-01",
        end_period="2025-12",
    )
    annual_reliability = summarize_metric_window(
        rows,
        metric_id=RELIABILITY_ZG,
        start_period="2025-01",
        end_period="2025-12",
    )
    jan_sep_punctuality = summarize_metric_window(
        rows,
        metric_id=PUNCTUALITY_P3,
        start_period="2025-01",
        end_period="2025-09",
    )
    jan_sep_reliability = summarize_metric_window(
        rows,
        metric_id=RELIABILITY_ZG,
        start_period="2025-01",
        end_period="2025-09",
    )

    return {
        "comparison_id": "tagesspiegel_2025_kpi_crosscheck",
        "generated_at": generated_at,
        "project_metric_reference": {
            "source_csv": str(input_csv).replace("\\", "/"),
            "entity_scope": "network",
            "headline_metrics": [PUNCTUALITY_P3, RELIABILITY_ZG],
            "metric_definitions": METRIC_DEFINITIONS,
            "method_note": (
                "Derived comparison figures use equal-weight averages of the published "
                "monthly VBB network percentages because this repo does not store the "
                "underlying train-count or train-km weights needed for an exact annual "
                "re-aggregation."
            ),
        },
        "source_chain": {
            "secondary_reporting": source_dicts("secondary_reporting"),
            "public_primary_sources": source_dicts("public_primary_sources"),
            "traceability_note": (
                "The Jan-Sep 2025 figures trace cleanly to the public parliamentary PDF. "
                "The calendar-year 2025 7.1%-late and roughly-6%-cancelled figures appear "
                "in Tagesspiegel's June 17, 2026 interactive and cite 'S-Bahn Berlin "
                "(2026)', but the underlying annual source is not linked directly in that "
                "article."
            ),
        },
        "claim_checks": [
            {
                "claim_id": "tagesspiegel_2025_late_trains_share",
                "reported_period": "2025-01 to 2025-12",
                "reported_value": "7.1% of trains arrived more than four minutes late",
                "source_reference": SOURCE_CHAIN["secondary_reporting"][1].url,
                "project_derived_value": (
                    f"{annual_punctuality.inverse_percent}% inverse of monthly "
                    f"{PUNCTUALITY_P3} ({annual_punctuality.rounded_inverse_percent}% "
                    f"rounded; {annual_punctuality.average_percent}% on time)"
                ),
                "comparison_validity": "approximate",
                "alignment": "aligns",
                "explanation": (
                    "This is the closest valid comparison because both figures describe "
                    "whole-network trains missing the 3:59 punctuality threshold. It is "
                    "still approximate because the repo only stores monthly percentages, "
                    "not the weights required to reproduce an exact annual aggregate."
                ),
            },
            {
                "claim_id": "tagesspiegel_2025_cancelled_trains_share",
                "reported_period": "2025-01 to 2025-12",
                "reported_value": "about 6% of trains fell out",
                "source_reference": SOURCE_CHAIN["secondary_reporting"][1].url,
                "project_derived_value": (
                    f"{annual_reliability.inverse_percent}% inverse of monthly "
                    f"{RELIABILITY_ZG} ({annual_reliability.rounded_inverse_percent}% "
                    f"rounded)"
                ),
                "comparison_validity": "not_direct",
                "alignment": "directionally_similar_but_metric_mismatched",
                "explanation": (
                    "The repo's reliability metric is delivered train-km over scheduled "
                    "train-km, while a cancelled-train share uses train runs as the unit. "
                    "The percentages are numerically close, but they should not be treated "
                    "as an exact match."
                ),
            },
            {
                "claim_id": "tagesspiegel_jan_sep_2025_punctuality",
                "reported_period": "2025-01 to 2025-09",
                "reported_value": "92.9% on time in the first nine months of 2025",
                "source_reference": SOURCE_CHAIN["secondary_reporting"][0].url,
                "project_derived_value": (
                    f"{jan_sep_punctuality.average_percent}% equal-weight monthly average "
                    f"({jan_sep_punctuality.inverse_percent}% more than four minutes late)"
                ),
                "comparison_validity": "approximate",
                "alignment": "aligns",
                "explanation": (
                    "This is the cleanest overlap between the repo's KPI layer and a "
                    "public primary-source chain. The threshold and network scope match, "
                    "but the repo still lacks the weights needed for a mathematically exact "
                    "Jan-Sep annualization."
                ),
            },
            {
                "claim_id": "tagesspiegel_jan_sep_2025_disruptions",
                "reported_period": "2025-01 to 2025-09",
                "reported_value": "34,414 operational disruptions",
                "source_reference": SOURCE_CHAIN["public_primary_sources"][0].url,
                "project_derived_value": (
                    "No direct analogue in the repo's KPI layer; the closest separate "
                    "metric is the 6.350% inverse of Jan-Sep network reliability_zg."
                ),
                "comparison_validity": "not_direct",
                "alignment": "cannot_compare_directly",
                "explanation": (
                    "The repo tracks monthly KPI percentages and a curated annotation "
                    "layer, not the full operational incident log. The parliamentary report "
                    "counts each operational irregularity once, regardless of duration or "
                    "impact."
                ),
            },
            {
                "claim_id": "issue_target_900_plus_disruptions",
                "reported_period": "issue target claim without article/date attached",
                "reported_value": "900+ disruptions",
                "source_reference": SOURCE_CHAIN["secondary_reporting"][1].url,
                "project_derived_value": (
                    "Closest located Tagesspiegel figures were about 46,000 disruptions "
                    "for calendar 2025, 34,414 operational disruptions for Jan-Sep 2025, "
                    "and 831 rider-facing website notices for 2025-12-01 to 2026-04-30."
                ),
                "comparison_validity": "not_verified",
                "alignment": "cannot_compare_directly",
                "explanation": (
                    "A bare 900+ figure could not be confirmed as the 2025 annual "
                    "disruption count in the located sources. The available Tagesspiegel "
                    "reporting uses multiple disruption concepts with different periods and "
                    "filters, so the narrative should cite the exact article and date "
                    "instead of a floating count."
                ),
            },
        ],
        "supporting_period_summaries": {
            "annual_2025": {
                PUNCTUALITY_P3: asdict(annual_punctuality),
                RELIABILITY_ZG: asdict(annual_reliability),
            },
            "jan_to_sep_2025": {
                PUNCTUALITY_P3: asdict(jan_sep_punctuality),
                RELIABILITY_ZG: asdict(jan_sep_reliability),
            },
        },
        "comparison_note": {
            "verdict": "mixed_comparability",
            "alignment_statement": (
                "The repo's headline KPI trend aligns with Tagesspiegel's 2025 "
                "punctuality reporting at an approximate level."
            ),
            "non_alignment_statement": (
                "Disruption counts do not compare directly to the repo's KPI series, and "
                "the located Tagesspiegel coverage uses at least three different count "
                "concepts: 34,414 operational disruptions (Jan-Sep 2025), about 46,000 "
                "disruptions (calendar 2025), and 831 rider-facing notices "
                "(2025-12-01 to 2026-04-30)."
            ),
            "narrative_safe_use": (
                "It is safe to say that external reporting supports the repo's story that "
                "2025 punctuality deteriorated materially, but any comparison to "
                "disruption-count reporting must be framed as a separate incident-count "
                "lens rather than the same KPI."
            ),
        },
    }


def write_json(payload: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Tagesspiegel-versus-VBB 2025 cross-check note."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_INPUT_CSV,
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows = load_network_rows(args.input_csv)
    payload = build_tagesspiegel_crosscheck(
        rows,
        generated_at=generated_at,
        input_csv=args.input_csv,
    )
    write_json(payload, args.output_json)
    print(f"Wrote Tagesspiegel cross-check note to {args.output_json}")


if __name__ == "__main__":
    main()
