from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from html import escape
from pathlib import Path
from statistics import mean
from typing import Iterable


REPORT_TITLE = "Berlin S-Bahn reliability trend"
DEFAULT_QUALITY_CSV = Path("data/vbb_sbahn_quality_2019_onward.csv")
DEFAULT_NETWORK_CSV = DEFAULT_QUALITY_CSV
DEFAULT_LINE_CSV = DEFAULT_QUALITY_CSV
DEFAULT_ANNOTATIONS_CSV = Path("data/vbb_sbahn_event_annotations_2023_2026.csv")
DEFAULT_NOTES_JSON = Path("data/vbb_sbahn_monthly_trend_notes_2023_2026.json")
DEFAULT_SOURCES_JSON = Path("data/vbb_sbahn_quality_sources.json")
DEFAULT_HTML_OUTPUT = Path("reports/berlin_sbahn_reliability_trend.html")
DEFAULT_MARKDOWN_OUTPUT = Path("reports/berlin_sbahn_reliability_conclusion.md")
DEFAULT_ASSET_DIR = Path("reports/assets")

HEADLINE_METRICS = ("punctuality_p3", "reliability_zg")
LINE_BASELINE_YEAR = 2023
LINE_COMPARISON_YEAR = 2025
ROUTE_LINES = ("S25", "S26")
PUNCTUALITY_REFERENCE_PERCENT = 93.0

METRIC_LABELS = {
    "punctuality_p3": "Punctuality <= 3:59 late",
    "reliability_zg": "Reliability train-km delivered",
}

METRIC_COLORS = {
    "punctuality_p3": "#0f766e",
    "reliability_zg": "#1d4ed8",
}

ANNOTATION_COLORS = {
    "cable_theft": "#b91c1c",
    "signal_or_stellwerk_failure": "#7c3aed",
    "wollankstrasse_closure": "#d97706",
}

@dataclass(frozen=True)
class MetricRow:
    period: str
    year: int
    month: int
    entity_scope: str
    entity_id: str
    metric_id: str
    value_percent: float

    @property
    def chart_date(self) -> str:
        return f"{self.period}-01"


@dataclass(frozen=True)
class AnnotationRow:
    event_id: str
    event_family: str
    annotation_kind: str
    chart_label: str
    summary: str
    start_date: str
    end_date: str
    affected_lines: tuple[str, ...]
    context_note: str
    causal_caveat: str

    @property
    def chart_position(self) -> str:
        if self.annotation_kind == "range":
            start = self.start_date
            end = self.end_date
            return midpoint_date(start, end)
        return self.start_date


@dataclass(frozen=True)
class MetricWindowSummary:
    metric_id: str
    label: str
    start_period: str
    end_period: str
    month_count: int
    value_percent: float


@dataclass(frozen=True)
class LineDelta:
    metric_id: str
    entity_id: str
    baseline_year: int
    comparison_year: int
    baseline_value: float
    comparison_value: float
    delta_percent_points: float


@dataclass(frozen=True)
class PunctualityExposure:
    year: int
    reference_percent: float
    months_below_reference: int
    observed_months: int


@dataclass(frozen=True)
class RouteScorecard:
    entity_id: str
    metric_id: str
    baseline_year: int
    baseline_value: float
    comparison_year: int
    comparison_value: float
    delta_percent_points: float
    network_gap_percent_points: float
    latest_ytd_label: str
    latest_ytd_value: float
    comparison_ytd_value: float


@dataclass(frozen=True)
class RouteOverallScore:
    entity_id: str
    baseline_year: int
    baseline_value: float
    comparison_year: int
    comparison_value: float
    delta_percent_points: float
    latest_ytd_label: str
    latest_ytd_value: float
    comparison_ytd_value: float


@dataclass(frozen=True)
class ReportSummary:
    observed_until: str
    baseline_year: int
    comparison_year: int
    punctuality_reference_percent: float
    conclusion_label: str
    conclusion_text: str
    key_findings: tuple[str, ...]
    caveats: tuple[str, ...]
    full_year_summaries: tuple[MetricWindowSummary, ...]
    comparable_ytd_summaries: tuple[MetricWindowSummary, ...]
    line_deltas: tuple[LineDelta, ...]
    punctuality_exposures: tuple[PunctualityExposure, ...]
    route_scorecards: tuple[RouteScorecard, ...]
    route_overall_scores: tuple[RouteOverallScore, ...]
    source_urls: dict[str, str]


def midpoint_date(start_date: str, end_date: str) -> str:
    start_year, start_month, start_day = (int(part) for part in start_date.split("-"))
    end_year, end_month, end_day = (int(part) for part in end_date.split("-"))
    start_ordinal = date_ordinal(start_year, start_month, start_day)
    end_ordinal = date_ordinal(end_year, end_month, end_day)
    mid_ordinal = (start_ordinal + end_ordinal) // 2
    year, month, day = date_from_ordinal(mid_ordinal)
    return f"{year:04d}-{month:02d}-{day:02d}"


def date_ordinal(year: int, month: int, day: int) -> int:
    month_lengths = [31, 28 + int(is_leap_year(year)), 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    ordinal = day
    for current_month in range(1, month):
        ordinal += month_lengths[current_month - 1]
    for current_year in range(1, year):
        ordinal += 365 + int(is_leap_year(current_year))
    return ordinal


def date_from_ordinal(ordinal: int) -> tuple[int, int, int]:
    year = 1
    remaining = ordinal
    while True:
        year_length = 365 + int(is_leap_year(year))
        if remaining <= year_length:
            break
        remaining -= year_length
        year += 1

    month_lengths = [31, 28 + int(is_leap_year(year)), 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    month = 1
    while remaining > month_lengths[month - 1]:
        remaining -= month_lengths[month - 1]
        month += 1
    return year, month, remaining


def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def load_metric_rows(csv_path: Path) -> list[MetricRow]:
    rows: list[MetricRow] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for raw_row in csv.DictReader(handle):
            rows.append(
                MetricRow(
                    period=raw_row["period"],
                    year=int(raw_row["year"]),
                    month=int(raw_row["month"]),
                    entity_scope=raw_row["entity_scope"],
                    entity_id=raw_row["entity_id"],
                    metric_id=raw_row["metric_id"],
                    value_percent=float(raw_row["value_percent"]),
                )
            )
    return rows


def load_annotation_rows(csv_path: Path) -> list[AnnotationRow]:
    rows: list[AnnotationRow] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for raw_row in csv.DictReader(handle):
            affected_lines = tuple(
                line for line in raw_row["affected_lines"].split(",") if line.strip()
            )
            rows.append(
                AnnotationRow(
                    event_id=raw_row["event_id"],
                    event_family=raw_row["event_family"],
                    annotation_kind=raw_row["annotation_kind"],
                    chart_label=raw_row["chart_label"],
                    summary=raw_row["summary"],
                    start_date=raw_row["start_date"],
                    end_date=raw_row["end_date"],
                    affected_lines=affected_lines,
                    context_note=raw_row["context_note"],
                    causal_caveat=raw_row["causal_caveat"],
                )
            )
    return rows


def load_json(json_path: Path) -> dict[str, object]:
    with json_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def metric_rows_for(
    rows: Iterable[MetricRow],
    *,
    metric_id: str,
    year: int | None = None,
    end_month: int | None = None,
) -> list[MetricRow]:
    filtered = [row for row in rows if row.metric_id == metric_id]
    if year is not None:
        filtered = [row for row in filtered if row.year == year]
    if end_month is not None:
        filtered = [row for row in filtered if row.month <= end_month]
    return sorted(filtered, key=lambda row: (row.year, row.month))


def summarize_window(
    rows: Iterable[MetricRow],
    *,
    metric_id: str,
    label: str,
    year: int,
    end_month: int | None = None,
) -> MetricWindowSummary:
    metric_rows = metric_rows_for(rows, metric_id=metric_id, year=year, end_month=end_month)
    if not metric_rows:
        raise ValueError(f"No rows available for {metric_id} in {label}")
    return MetricWindowSummary(
        metric_id=metric_id,
        label=label,
        start_period=metric_rows[0].period,
        end_period=metric_rows[-1].period,
        month_count=len(metric_rows),
        value_percent=mean(row.value_percent for row in metric_rows),
    )


def build_full_year_summaries(network_rows: list[MetricRow]) -> tuple[MetricWindowSummary, ...]:
    complete_years = sorted(
        {
            row.year
            for row in network_rows
            if all(
                len(metric_rows_for(network_rows, metric_id=metric_id, year=row.year)) == 12
                for metric_id in HEADLINE_METRICS
            )
        }
    )
    summaries: list[MetricWindowSummary] = []
    for year in complete_years:
        for metric_id in HEADLINE_METRICS:
            summaries.append(
                summarize_window(
                    network_rows,
                    metric_id=metric_id,
                    label=str(year),
                    year=year,
                )
            )
    return tuple(summaries)


def build_comparable_ytd_summaries(
    network_rows: list[MetricRow],
    *,
    latest_year: int,
    latest_month: int,
) -> tuple[MetricWindowSummary, ...]:
    summaries: list[MetricWindowSummary] = []
    years = sorted({row.year for row in network_rows if row.year <= latest_year})
    for year in years:
        for metric_id in HEADLINE_METRICS:
            label = (
                f"{year} YTD (Jan-{month_label(latest_month)})"
                if year == latest_year
                else f"{year} Jan-{month_label(latest_month)}"
            )
            summaries.append(
                summarize_window(
                    network_rows,
                    metric_id=metric_id,
                    label=label,
                    year=year,
                    end_month=latest_month,
                )
            )
    return tuple(summaries)


def build_line_deltas(
    line_rows: list[MetricRow],
    *,
    baseline_year: int = LINE_BASELINE_YEAR,
    comparison_year: int = LINE_COMPARISON_YEAR,
) -> tuple[LineDelta, ...]:
    deltas: list[LineDelta] = []
    line_ids = sorted({row.entity_id for row in line_rows})
    for metric_id in HEADLINE_METRICS:
        for line_id in line_ids:
            baseline_rows = metric_rows_for(
                [row for row in line_rows if row.entity_id == line_id],
                metric_id=metric_id,
                year=baseline_year,
            )
            comparison_rows = metric_rows_for(
                [row for row in line_rows if row.entity_id == line_id],
                metric_id=metric_id,
                year=comparison_year,
            )
            if not baseline_rows or not comparison_rows:
                continue
            if len(baseline_rows) != 12 or len(comparison_rows) != 12:
                continue
            baseline_value = mean(row.value_percent for row in baseline_rows)
            comparison_value = mean(row.value_percent for row in comparison_rows)
            deltas.append(
                LineDelta(
                    metric_id=metric_id,
                    entity_id=line_id,
                    baseline_year=baseline_year,
                    comparison_year=comparison_year,
                    baseline_value=baseline_value,
                    comparison_value=comparison_value,
                    delta_percent_points=comparison_value - baseline_value,
                )
            )
    return tuple(
        sorted(deltas, key=lambda delta: (delta.metric_id, delta.delta_percent_points, delta.entity_id))
    )


def build_punctuality_exposures(
    network_rows: list[MetricRow],
    *,
    reference_percent: float = PUNCTUALITY_REFERENCE_PERCENT,
) -> tuple[PunctualityExposure, ...]:
    complete_years = sorted(
        {
            row.year
            for row in network_rows
            if len(
                metric_rows_for(
                    network_rows,
                    metric_id="punctuality_p3",
                    year=row.year,
                )
            )
            == 12
        }
    )
    return tuple(
        PunctualityExposure(
            year=year,
            reference_percent=reference_percent,
            months_below_reference=sum(
                row.value_percent < reference_percent
                for row in metric_rows_for(
                    network_rows,
                    metric_id="punctuality_p3",
                    year=year,
                )
            ),
            observed_months=12,
        )
        for year in complete_years
    )


def build_route_scorecards(
    network_rows: list[MetricRow],
    line_rows: list[MetricRow],
    *,
    latest_year: int,
    latest_month: int,
    baseline_year: int = LINE_BASELINE_YEAR,
    comparison_year: int = LINE_COMPARISON_YEAR,
    route_lines: tuple[str, ...] = ROUTE_LINES,
) -> tuple[RouteScorecard, ...]:
    latest_label = f"{latest_year} YTD (Jan-{month_label(latest_month)})"
    scores: list[RouteScorecard] = []
    for line_id in route_lines:
        route_rows = [row for row in line_rows if row.entity_id == line_id]
        for metric_id in HEADLINE_METRICS:
            baseline = summarize_window(
                route_rows,
                metric_id=metric_id,
                label=str(baseline_year),
                year=baseline_year,
            )
            comparison = summarize_window(
                route_rows,
                metric_id=metric_id,
                label=str(comparison_year),
                year=comparison_year,
            )
            network_comparison = summarize_window(
                network_rows,
                metric_id=metric_id,
                label=str(comparison_year),
                year=comparison_year,
            )
            latest_ytd = summarize_window(
                route_rows,
                metric_id=metric_id,
                label=latest_label,
                year=latest_year,
                end_month=latest_month,
            )
            comparison_ytd = summarize_window(
                route_rows,
                metric_id=metric_id,
                label=f"{comparison_year} Jan-{month_label(latest_month)}",
                year=comparison_year,
                end_month=latest_month,
            )
            scores.append(
                RouteScorecard(
                    entity_id=line_id,
                    metric_id=metric_id,
                    baseline_year=baseline_year,
                    baseline_value=baseline.value_percent,
                    comparison_year=comparison_year,
                    comparison_value=comparison.value_percent,
                    delta_percent_points=comparison.value_percent - baseline.value_percent,
                    network_gap_percent_points=(
                        comparison.value_percent - network_comparison.value_percent
                    ),
                    latest_ytd_label=latest_label,
                    latest_ytd_value=latest_ytd.value_percent,
                    comparison_ytd_value=comparison_ytd.value_percent,
                )
            )
    return tuple(scores)


def build_route_overall_scores(
    line_rows: list[MetricRow],
    *,
    latest_year: int,
    latest_month: int,
    baseline_year: int = LINE_BASELINE_YEAR,
    comparison_year: int = LINE_COMPARISON_YEAR,
    route_lines: tuple[str, ...] = ROUTE_LINES,
) -> tuple[RouteOverallScore, ...]:
    latest_label = f"{latest_year} YTD (Jan-{month_label(latest_month)})"
    scores: list[RouteOverallScore] = []
    for line_id in route_lines:
        route_rows = [row for row in line_rows if row.entity_id == line_id]
        baseline = summarize_window(
            route_rows,
            metric_id="overall_ranking",
            label=str(baseline_year),
            year=baseline_year,
        )
        comparison = summarize_window(
            route_rows,
            metric_id="overall_ranking",
            label=str(comparison_year),
            year=comparison_year,
        )
        latest_ytd = summarize_window(
            route_rows,
            metric_id="overall_ranking",
            label=latest_label,
            year=latest_year,
            end_month=latest_month,
        )
        comparison_ytd = summarize_window(
            route_rows,
            metric_id="overall_ranking",
            label=f"{comparison_year} Jan-{month_label(latest_month)}",
            year=comparison_year,
            end_month=latest_month,
        )
        scores.append(
            RouteOverallScore(
                entity_id=line_id,
                baseline_year=baseline_year,
                baseline_value=baseline.value_percent,
                comparison_year=comparison_year,
                comparison_value=comparison.value_percent,
                delta_percent_points=comparison.value_percent - baseline.value_percent,
                latest_ytd_label=latest_label,
                latest_ytd_value=latest_ytd.value_percent,
                comparison_ytd_value=comparison_ytd.value_percent,
            )
        )
    return tuple(scores)


def month_label(month: int) -> str:
    labels = {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Aug",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dec",
    }
    return labels[month]


def build_report_summary(
    network_rows: list[MetricRow],
    line_rows: list[MetricRow],
    *,
    source_urls: dict[str, str],
    baseline_year: int = LINE_BASELINE_YEAR,
    comparison_year: int = LINE_COMPARISON_YEAR,
    punctuality_reference_percent: float = PUNCTUALITY_REFERENCE_PERCENT,
) -> ReportSummary:
    observed_until = max(row.period for row in network_rows)
    latest_year, latest_month = (int(part) for part in observed_until.split("-"))
    full_year_summaries = build_full_year_summaries(network_rows)
    comparable_ytd_summaries = build_comparable_ytd_summaries(
        network_rows,
        latest_year=latest_year,
        latest_month=latest_month,
    )
    line_deltas = build_line_deltas(
        line_rows,
        baseline_year=baseline_year,
        comparison_year=comparison_year,
    )
    punctuality_exposures = build_punctuality_exposures(
        network_rows,
        reference_percent=punctuality_reference_percent,
    )
    route_scorecards = build_route_scorecards(
        network_rows,
        line_rows,
        latest_year=latest_year,
        latest_month=latest_month,
        baseline_year=baseline_year,
        comparison_year=comparison_year,
    )
    route_overall_scores = build_route_overall_scores(
        line_rows,
        latest_year=latest_year,
        latest_month=latest_month,
        baseline_year=baseline_year,
        comparison_year=comparison_year,
    )

    summary_lookup = {(item.metric_id, item.label): item for item in full_year_summaries}
    ytd_lookup = {(item.metric_id, item.label): item for item in comparable_ytd_summaries}
    prior_year = comparison_year - 1
    punctuality_prior = summary_lookup[("punctuality_p3", str(prior_year))].value_percent
    punctuality_comparison = summary_lookup[
        ("punctuality_p3", str(comparison_year))
    ].value_percent
    reliability_prior = summary_lookup[("reliability_zg", str(prior_year))].value_percent
    reliability_comparison = summary_lookup[
        ("reliability_zg", str(comparison_year))
    ].value_percent
    latest_ytd_label = f"{latest_year} YTD (Jan-{month_label(latest_month)})"
    punctuality_latest_ytd = ytd_lookup[("punctuality_p3", latest_ytd_label)].value_percent
    reliability_latest_ytd = ytd_lookup[("reliability_zg", latest_ytd_label)].value_percent

    weakest_punctuality = min(
        (item for item in full_year_summaries if item.metric_id == "punctuality_p3"),
        key=lambda item: item.value_percent,
    )
    exposure_lookup = {item.year: item for item in punctuality_exposures}
    punctuality_declines = sum(
        delta.metric_id == "punctuality_p3" and delta.delta_percent_points < 0
        for delta in line_deltas
    )
    reliability_improvements = sum(
        delta.metric_id == "reliability_zg" and delta.delta_percent_points > 0
        for delta in line_deltas
    )
    line_count = len({delta.entity_id for delta in line_deltas})

    conclusion_text = (
        "The VBB series shows a divergence that a single service-quality score would hide: "
        "train-km delivery increased after its preceding annual low, while punctual running "
        "remained weaker. "
        f"{weakest_punctuality.label} was the weakest complete-year punctuality result in "
        f"the observed series at {weakest_punctuality.value_percent:.2f}%, while reliability "
        f"rose from {reliability_prior:.2f}% in {prior_year} to {reliability_comparison:.2f}% "
        f"in {comparison_year}. The {latest_year} Jan-{month_label(latest_month)} result "
        f"is higher than the same months of {comparison_year}, but "
        f"punctuality ({punctuality_latest_ytd:.2f}%) remains below the same months of "
        f"{baseline_year} ({ytd_lookup[('punctuality_p3', f'{baseline_year} Jan-{month_label(latest_month)}')].value_percent:.2f}%)."
    )

    key_findings = (
        f"Punctuality fell from {punctuality_prior:.2f}% in {prior_year} to {punctuality_comparison:.2f}% "
        f"in {comparison_year}, even as reliability increased by {reliability_comparison - reliability_prior:+.2f} pp.",
        f"{exposure_lookup[comparison_year].months_below_reference} of 12 months in {comparison_year} were below "
        f"the explicit {punctuality_reference_percent:.1f}% punctuality reference, versus "
        f"{exposure_lookup[baseline_year].months_below_reference} in {baseline_year} and "
        f"{exposure_lookup[prior_year].months_below_reference} in {prior_year}.",
        f"The movement is not confined to one published line average: {punctuality_declines}/{line_count} "
        f"lines lost punctuality from {baseline_year} to {comparison_year}, while {reliability_improvements}/{line_count} improved reliability.",
        f"The observed {latest_year} Jan-{month_label(latest_month)} window is stronger than "
        f"the same months of {comparison_year} by {punctuality_latest_ytd - ytd_lookup[('punctuality_p3', f'{comparison_year} Jan-{month_label(latest_month)}')].value_percent:+.2f} pp "
        f"on punctuality and {reliability_latest_ytd - ytd_lookup[('reliability_zg', f'{comparison_year} Jan-{month_label(latest_month)}')].value_percent:+.2f} pp on reliability; it is not a full-year result.",
    )

    caveats = (
        f"The current VBB monthly trend window stops at {observed_until}, so {latest_year} is "
        "not yet a full-year comparison.",
        "The core claim is anchored on VBB monthly punctuality and reliability KPIs, not disruption-count proxies.",
        f"The {punctuality_reference_percent:.1f}% punctuality reference is a descriptive threshold for counting weak months, not a VBB target or pass/fail standard.",
        "The VBB overall score in the route view is a secondary comparison only; it does not replace the two primary KPIs.",
        "The S25/S26 view measures line-level service. It cannot describe the experience of a particular station-to-station trip or identify a causal mechanism.",
        "Pre-2019 archive backfill remains outside the headline charts because compatibility with the current VBB tool is not proven.",
    )

    return ReportSummary(
        observed_until=observed_until,
        baseline_year=baseline_year,
        comparison_year=comparison_year,
        punctuality_reference_percent=punctuality_reference_percent,
        conclusion_label="divergence",
        conclusion_text=conclusion_text,
        key_findings=key_findings,
        caveats=caveats,
        full_year_summaries=full_year_summaries,
        comparable_ytd_summaries=comparable_ytd_summaries,
        line_deltas=line_deltas,
        punctuality_exposures=punctuality_exposures,
        route_scorecards=route_scorecards,
        route_overall_scores=route_overall_scores,
        source_urls=source_urls,
    )


def _svg_x(index: int, count: int, left: float, width: float) -> float:
    return left if count <= 1 else left + (index / (count - 1)) * width


def _svg_y(value: float, domain: tuple[float, float], top: float, height: float) -> float:
    lower, upper = domain
    return top + height - ((value - lower) / (upper - lower)) * height


def _svg_path(points: list[tuple[float, float]]) -> str:
    return " ".join(
        f"{'M' if index == 0 else 'L'} {x:.1f} {y:.1f}"
        for index, (x, y) in enumerate(points)
    )


def build_annual_network_svg(summary: ReportSummary) -> str:
    full_years = sorted({int(item.label) for item in summary.full_year_summaries})
    latest_year = int(summary.observed_until[:4])
    latest_month = int(summary.observed_until[5:])
    years = full_years + [latest_year]
    values = {
        metric_id: {
            int(item.label): item.value_percent
            for item in summary.full_year_summaries
            if item.metric_id == metric_id
        }
        for metric_id in HEADLINE_METRICS
    }
    for metric_id in HEADLINE_METRICS:
        values[metric_id][latest_year] = latest_ytd_metric(summary, metric_id).value_percent
    all_values = [value for metric_values in values.values() for value in metric_values.values()]
    lower = math.floor(min(all_values) - 1)
    upper = math.ceil(max(all_values) + 1)
    width = 1080
    height = 410
    left = 78
    right = 30
    top = 88
    plot_height = 220
    plot_width = width - left - right
    colors = {"punctuality_p3": "#0f766e", "reliability_zg": "#1d4ed8"}
    labels = {"punctuality_p3": "punctuality", "reliability_zg": "reliability"}
    parts = [
        (
            f'<svg class="chart-svg annual-svg" viewBox="0 0 {width} {height}" '
            'role="img" aria-labelledby="annual-chart-title annual-chart-desc" '
            'preserveAspectRatio="xMidYMid meet">'
        ),
        '<title id="annual-chart-title">Annual network KPI divergence</title>',
        '<desc id="annual-chart-desc">Complete-year means of VBB monthly punctuality and reliability, followed by the observed current year-to-date window. The two KPIs follow different patterns and are not a combined score.</desc>',
        '<rect width="100%" height="100%" rx="18" fill="#fbfaf6"/>',
        '<text x="78" y="30" class="svg-kicker">ANNUAL DIAGNOSIS</text>',
        '<line x1="310" y1="25" x2="340" y2="25" class="annual-punctuality"/>',
        '<text x="348" y="30" class="svg-legend">punctuality</text>',
        '<line x1="450" y1="25" x2="480" y2="25" class="annual-reliability"/>',
        '<text x="488" y="30" class="svg-legend">reliability</text>',
        f'<text x="615" y="30" class="svg-legend">{latest_year} is Jan-{month_label(latest_month)}</text>',
    ]
    tick_start = int(math.ceil(lower / 2) * 2)
    for tick in range(tick_start, upper + 1, 2):
        y = _svg_y(tick, (lower, upper), top, plot_height)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid-line"/>'
        )
        parts.append(
            f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="svg-axis">{tick}%</text>'
        )
    for metric_id in HEADLINE_METRICS:
        points = [
            (
                _svg_x(index, len(years), left, plot_width),
                _svg_y(values[metric_id][year], (lower, upper), top, plot_height),
            )
            for index, year in enumerate(years)
        ]
        full_points = points[:-1]
        if full_points:
            parts.append(
                f'<path d="{_svg_path(full_points)}" class="annual-{labels[metric_id]}"/>'
            )
        if len(points) > 1:
            parts.append(
                f'<path d="{_svg_path(points[-2:])}" class="annual-{labels[metric_id]} annual-ytd"/>'
            )
        for year, (x, y) in zip(years, points):
            suffix = " YTD" if year == latest_year else ""
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.2" fill="{colors[metric_id]}">'
                f'<title>{labels[metric_id].title()} {year}{suffix}: {values[metric_id][year]:.2f}%</title></circle>'
            )
    for index, year in enumerate(years):
        x = _svg_x(index, len(years), left, plot_width)
        label = f"{year} YTD" if year == latest_year else str(year)
        parts.append(
            f'<text x="{x:.1f}" y="{top + plot_height + 28}" text-anchor="middle" class="svg-year">{label}</text>'
        )
    parts.append(
        '<text x="78" y="372" class="svg-axis-label">Each point is an unweighted mean of the published monthly percentages; the two KPIs are not a combined score.</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def build_network_svg(
    network_rows: list[MetricRow],
    annotations: list[AnnotationRow],
    *,
    comparison_year: int = LINE_COMPARISON_YEAR,
) -> str:
    periods = sorted({row.period for row in network_rows})
    latest_period = periods[-1]
    latest_year = int(latest_period[:4])
    latest_month = int(latest_period[5:])
    width = 1080
    height = 520
    left = 78
    right = 28
    plot_width = width - left - right
    panel_height = 150
    panel_tops = (82, 302)
    metric_domains = {
        "punctuality_p3": (89.0, 97.0),
        "reliability_zg": (74.0, 98.0),
    }
    metric_titles = {
        "punctuality_p3": "Punctuality",
        "reliability_zg": "Reliability",
    }
    metric_subtitles = {
        "punctuality_p3": "arrivals within 3:59 minutes",
        "reliability_zg": "train-km delivered vs scheduled",
    }
    period_index = {period: index for index, period in enumerate(periods)}
    step = plot_width / max(len(periods) - 1, 1)
    parts = [
        (
            f'<svg class="chart-svg network-svg" viewBox="0 0 {width} {height}" '
            'role="img" aria-labelledby="network-chart-title network-chart-desc" '
            'preserveAspectRatio="xMidYMid meet">'
        ),
        '<title id="network-chart-title">Whole-network monthly KPI trend</title>',
        f'<desc id="network-chart-desc">Monthly punctuality and reliability from {periods[0]} through the latest observed month. The {comparison_year} and current year-to-date periods are shaded for comparison.</desc>',
        '<rect width="100%" height="100%" rx="18" fill="#fbfaf6"/>',
        '<text x="78" y="30" class="svg-kicker">WHOLE-NETWORK PULSE</text>',
        '<line x1="285" y1="25" x2="315" y2="25" class="legend-line"/>',
        '<text x="323" y="30" class="svg-legend">monthly KPI</text>',
        '<rect x="410" y="18" width="18" height="14" rx="3" fill="#fff0df"/>',
        f'<text x="436" y="30" class="svg-legend">{comparison_year}</text>',
        '<rect x="495" y="18" width="18" height="14" rx="3" fill="#e7f5ee"/>',
        f'<text x="521" y="30" class="svg-legend">{latest_year} Jan-{month_label(latest_month)}</text>',
        '<circle cx="680" cy="25" r="4" fill="#d97706"/>',
        '<text x="692" y="30" class="svg-legend">context event</text>',
    ]

    year_groups: dict[int, list[int]] = {}
    for index, period in enumerate(periods):
        year_groups.setdefault(int(period[:4]), []).append(index)
    for year, indices in year_groups.items():
        band_left = max(left, _svg_x(indices[0], len(periods), left, plot_width) - step / 2)
        band_right = min(width - right, _svg_x(indices[-1], len(periods), left, plot_width) + step / 2)
        fill = "#fff0df" if year == comparison_year else "#e7f5ee" if year == max(year_groups) else "#f3f1eb"
        parts.append(
            f'<rect x="{band_left:.1f}" y="62" width="{band_right - band_left:.1f}" '
            f'height="350" fill="{fill}" opacity="0.75"/>'
        )

    for metric_id, panel_top in zip(HEADLINE_METRICS, panel_tops):
        domain = metric_domains[metric_id]
        parts.append(
            f'<text x="{left}" y="{panel_top - 26}" class="svg-panel-title">'
            f'{metric_titles[metric_id]}</text>'
        )
        parts.append(
            f'<text x="{left + 112}" y="{panel_top - 26}" class="svg-panel-subtitle">'
            f'{metric_subtitles[metric_id]}</text>'
        )
        for tick in (90, 92, 94, 96) if metric_id == "punctuality_p3" else (76, 82, 88, 94):
            if domain[0] <= tick <= domain[1]:
                y = _svg_y(tick, domain, panel_top, panel_height)
                parts.append(
                    f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid-line"/>'
                )
                parts.append(
                    f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="svg-axis">{tick}%</text>'
                )
        metric_rows = metric_rows_for(network_rows, metric_id=metric_id)
        points = [
            (
                _svg_x(period_index[row.period], len(periods), left, plot_width),
                _svg_y(row.value_percent, domain, panel_top, panel_height),
            )
            for row in metric_rows
        ]
        parts.append(f'<path d="{_svg_path(points)}" class="network-path"/>')
        for row, (x, y) in zip(metric_rows, points):
            point_class = "network-point current-point" if row.year == max(year_groups) else "network-point"
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" class="{point_class}">'
                f'<title>{row.period}: {row.value_percent:.2f}%</title></circle>'
            )

    x_axis_y = panel_tops[-1] + panel_height + 24
    for year, indices in year_groups.items():
        x = _svg_x(indices[0], len(periods), left, plot_width)
        if year == max(year_groups):
            label = f"{year} Jan-{month_label(max(int(periods[index][5:]) for index in indices))}"
        else:
            label = str(year)
        parts.append(f'<text x="{x:.1f}" y="{x_axis_y}" class="svg-year">{label}</text>')
    parts.append(f'<text x="{left}" y="{height - 28}" class="svg-axis-label">Context events</text>')
    for event_number, annotation in enumerate(annotations, start=1):
        annotation_period = annotation.start_date[:7]
        if annotation_period not in period_index:
            continue
        x = _svg_x(period_index[annotation_period], len(periods), left, plot_width)
        color = ANNOTATION_COLORS.get(annotation.event_family, "#64748b")
        title = f"{annotation.chart_label}: {annotation.summary}"
        parts.append(
            f'<circle cx="{x:.1f}" cy="{height - 33}" r="7" fill="{color}" class="event-point">'
            f'<title>{escape(title)}</title></circle>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{height - 30:.1f}" text-anchor="middle" class="event-number">{event_number}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def build_line_comparison_svg(line_deltas: tuple[LineDelta, ...]) -> str:
    width = 1160
    height = 570
    panel_width = 500
    panel_gap = 46
    panel_lefts = (78, 78 + panel_width + panel_gap)
    top = 92
    row_height = 24
    metric_titles = {
        "punctuality_p3": "Punctuality",
        "reliability_zg": "Reliability",
    }
    parts = [
        (
            f'<svg class="chart-svg line-svg" viewBox="0 0 {width} {height}" '
            'role="img" aria-labelledby="line-chart-title line-chart-desc" '
            'preserveAspectRatio="xMidYMid meet">'
        ),
        '<title id="line-chart-title">Line-level KPI shifts</title>',
        '<desc id="line-chart-desc">Change in each S-Bahn line average between the configured baseline and comparison years, shown in percentage points. Bars left of zero indicate deterioration.</desc>',
        '<rect width="100%" height="100%" rx="18" fill="#fbfaf6"/>',
        '<text x="78" y="30" class="svg-kicker">LINE SHIFTS</text>',
        f'<text x="78" y="54" class="svg-caption">{line_deltas[0].comparison_year} average minus {line_deltas[0].baseline_year} average - percentage points</text>',
        '<rect x="755" y="18" width="12" height="12" rx="2" fill="#d6654b"/>',
        '<text x="775" y="28" class="svg-legend">lower</text>',
        '<rect x="828" y="18" width="12" height="12" rx="2" fill="#138a70"/>',
        '<text x="848" y="28" class="svg-legend">higher</text>',
    ]

    for metric_id, panel_left in zip(HEADLINE_METRICS, panel_lefts):
        metric_deltas = [delta for delta in line_deltas if delta.metric_id == metric_id]
        min_delta = min(delta.delta_percent_points for delta in metric_deltas)
        max_delta = max(delta.delta_percent_points for delta in metric_deltas)
        lower = math.floor(min_delta - 0.5)
        upper = math.ceil(max_delta + 0.5)
        plot_left = panel_left + 56
        plot_right = panel_left + panel_width - 78
        plot_width = plot_right - plot_left
        zero_x = plot_left + ((0 - lower) / (upper - lower)) * plot_width
        parts.append(f'<text x="{panel_left}" y="76" class="svg-panel-title">{metric_titles[metric_id]}</text>')
        parts.append(
            f'<line x1="{zero_x:.1f}" y1="{top - 12}" x2="{zero_x:.1f}" '
            f'y2="{top + row_height * len(metric_deltas) - 8}" class="zero-line"/>'
        )
        for index, delta in enumerate(metric_deltas):
            y = top + index * row_height
            end_x = plot_left + ((delta.delta_percent_points - lower) / (upper - lower)) * plot_width
            color = "#d6654b" if delta.delta_percent_points < 0 else "#138a70"
            label = f"{delta.delta_percent_points:+.2f} pp"
            title = (
                f"{delta.entity_id}: {delta.baseline_year} {delta.baseline_value:.2f}%, "
                f"{delta.comparison_year} {delta.comparison_value:.2f}%, {label}"
            )
            parts.append(
                f'<text x="{panel_left}" y="{y + 5}" class="svg-line-label">{escape(delta.entity_id)}</text>'
            )
            parts.append(
                f'<rect x="{min(zero_x, end_x):.1f}" y="{y - 6}" width="{abs(end_x - zero_x):.1f}" '
                f'height="12" rx="6" fill="{color}" opacity="0.9"><title>{escape(title)}</title></rect>'
            )
            parts.append(
                f'<text x="{panel_left + panel_width - 6}" y="{y + 5}" text-anchor="end" '
                f'class="svg-delta {"negative" if delta.delta_percent_points < 0 else "positive"}">{label}</text>'
            )
        for tick in (lower, 0, upper):
            x = plot_left + ((tick - lower) / (upper - lower)) * plot_width
            parts.append(f'<text x="{x:.1f}" y="{top + row_height * len(metric_deltas) + 22}" text-anchor="middle" class="svg-axis">{tick:+d}</text>')

    parts.append('<text x="78" y="546" class="svg-axis-label">Negative means the line average fell; positive means it rose.</text>')
    parts.append("</svg>")
    return "".join(parts)


def build_route_comparison_svg(
    all_rows: list[MetricRow],
    route_scorecards: tuple[RouteScorecard, ...],
) -> str:
    network_rows = [row for row in all_rows if row.entity_scope == "network"]
    line_rows = [row for row in all_rows if row.entity_scope == "line"]
    observed_until = max(row.period for row in network_rows)
    latest_year, latest_month = (int(part) for part in observed_until.split("-"))
    first_year = min(row.year for row in network_rows)
    years = list(range(first_year, latest_year + 1))
    width = 1080
    height = 520
    left = 78
    right = 30
    plot_width = width - left - right
    panel_height = 138
    panel_tops = (96, 316)
    metric_domains = {
        "punctuality_p3": (88.0, 99.0),
        "reliability_zg": (80.0, 100.0),
    }
    metric_titles = {
        "punctuality_p3": "Punctuality",
        "reliability_zg": "Reliability",
    }
    score_lookup = {
        (score.entity_id, score.metric_id): score for score in route_scorecards
    }

    def yearly_values(rows: list[MetricRow], metric_id: str) -> dict[int, float]:
        values: dict[int, float] = {}
        for year in years:
            yearly_rows = metric_rows_for(rows, metric_id=metric_id, year=year)
            if len(yearly_rows) == 12:
                values[year] = mean(row.value_percent for row in yearly_rows)
        return values

    def paths_for(values: dict[int, float], domain: tuple[float, float], panel_top: float) -> list[str]:
        paths: list[str] = []
        segment: list[tuple[float, float]] = []
        for index, year in enumerate(years):
            if year not in values:
                if segment:
                    paths.append(_svg_path(segment))
                    segment = []
                continue
            segment.append(
                (
                    _svg_x(index, len(years), left, plot_width),
                    _svg_y(values[year], domain, panel_top, panel_height),
                )
            )
        if segment:
            paths.append(_svg_path(segment))
        return paths

    parts = [
        (
            f'<svg class="chart-svg route-svg" viewBox="0 0 {width} {height}" '
            'role="img" aria-labelledby="route-chart-title route-chart-desc" '
            'preserveAspectRatio="xMidYMid meet">'
        ),
        '<title id="route-chart-title">S25 and S26 annual service-quality comparison</title>',
        '<desc id="route-chart-desc">Annual line-level punctuality and reliability for S25 and S26 compared with the whole network. The final point is the observed 2026 year-to-date window.</desc>',
        '<rect width="100%" height="100%" rx="18" fill="#fbfaf6"/>',
        '<text x="78" y="30" class="svg-kicker">PERSONAL ROUTE VIEW</text>',
        '<line x1="330" y1="25" x2="360" y2="25" class="route-network"/>',
        '<text x="368" y="30" class="svg-legend">network</text>',
        '<line x1="455" y1="25" x2="485" y2="25" class="route-s25"/>',
        '<text x="493" y="30" class="svg-legend">S25</text>',
        '<line x1="545" y1="25" x2="575" y2="25" class="route-s26"/>',
        '<text x="583" y="30" class="svg-legend">S26</text>',
        f'<text x="664" y="30" class="svg-legend">{latest_year} is Jan-{month_label(latest_month)}</text>',
    ]
    for metric_id, panel_top in zip(HEADLINE_METRICS, panel_tops):
        domain = metric_domains[metric_id]
        parts.append(
            f'<text x="{left}" y="{panel_top - 26}" class="svg-panel-title">'
            f'{metric_titles[metric_id]}</text>'
        )
        for tick in (90, 93, 96, 99) if metric_id == "punctuality_p3" else (80, 85, 90, 95, 100):
            y = _svg_y(tick, domain, panel_top, panel_height)
            parts.append(
                f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" class="grid-line"/>'
            )
            parts.append(
                f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="svg-axis">{tick}%</text>'
            )
        series = {
            "network": yearly_values(network_rows, metric_id),
            "s25": yearly_values(
                [row for row in line_rows if row.entity_id == "S25"], metric_id
            ),
            "s26": yearly_values(
                [row for row in line_rows if row.entity_id == "S26"], metric_id
            ),
        }
        latest_network_rows = metric_rows_for(
            network_rows,
            metric_id=metric_id,
            year=latest_year,
            end_month=latest_month,
        )
        series["network"][latest_year] = mean(
            row.value_percent for row in latest_network_rows
        )
        series["s25"][latest_year] = score_lookup[("S25", metric_id)].latest_ytd_value
        series["s26"][latest_year] = score_lookup[("S26", metric_id)].latest_ytd_value
        for series_name, values in series.items():
            for path in paths_for(values, domain, panel_top):
                parts.append(f'<path d="{path}" class="route-{series_name}"/>')
            for index, year in enumerate(years):
                if year not in values:
                    continue
                x = _svg_x(index, len(years), left, plot_width)
                y = _svg_y(values[year], domain, panel_top, panel_height)
                suffix = " YTD" if year == latest_year else ""
                label = "Network" if series_name == "network" else series_name.upper()
                parts.append(
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" class="route-point route-{series_name}">'
                    f'<title>{label} {year}{suffix}: {values[year]:.2f}%</title></circle>'
                )
    axis_y = panel_tops[-1] + panel_height + 25
    for index, year in enumerate(years):
        x = _svg_x(index, len(years), left, plot_width)
        label = f"{year} YTD" if year == latest_year else str(year)
        parts.append(f'<text x="{x:.1f}" y="{axis_y}" text-anchor="middle" class="svg-year">{label}</text>')
    parts.append(
        '<text x="78" y="492" class="svg-axis-label">Annual means of published monthly values; a broken S26 2020 line denotes incomplete monthly coverage.</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def build_summary_table(
    title: str,
    summaries: Iterable[MetricWindowSummary],
) -> str:
    rows = list(summaries)
    header = (
        "<thead><tr><th>Window</th><th>Metric</th><th>Monthly mean</th>"
        "<th>Observed months</th></tr></thead>"
    )
    body_rows = []
    for summary in rows:
        body_rows.append(
            "<tr>"
            f"<td>{escape(summary.label)}</td>"
            f"<td>{escape(METRIC_LABELS[summary.metric_id])}</td>"
            f"<td>{summary.value_percent:.2f}%</td>"
            f"<td>{summary.start_period} to {summary.end_period}</td>"
            "</tr>"
        )
    body = "<tbody>" + "".join(body_rows) + "</tbody>"
    return (
        f"<section class='table-block'><h3>{escape(title)}</h3>"
        f"<table>{header}{body}</table></section>"
    )


def build_punctuality_exposure_table(exposures: Iterable[PunctualityExposure]) -> str:
    rows = []
    for exposure in exposures:
        rows.append(
            "<tr>"
            f"<td>{exposure.year}</td>"
            f"<td>{exposure.months_below_reference} of {exposure.observed_months}</td>"
            f"<td>Below {exposure.reference_percent:.0f}%</td>"
            "</tr>"
        )
    return (
        "<section class='table-block'><h3>Punctuality exposure by year</h3>"
        "<table><thead><tr><th>Year</th><th>Weak months</th><th>Reference</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def build_route_scorecard_table(scorecards: Iterable[RouteScorecard]) -> str:
    scorecards = tuple(scorecards)
    rows = []
    for scorecard in scorecards:
        rows.append(
            "<tr>"
            f"<td>{escape(scorecard.entity_id)}</td>"
            f"<td>{escape(METRIC_LABELS[scorecard.metric_id])}</td>"
            f"<td>{scorecard.comparison_value:.2f}%</td>"
            f"<td>{scorecard.delta_percent_points:+.2f} pp</td>"
            f"<td>{scorecard.network_gap_percent_points:+.2f} pp</td>"
            f"<td>{scorecard.latest_ytd_value:.2f}%</td>"
            "</tr>"
        )
    return (
        "<section class='table-block'><h3>S25/S26 scorecard</h3>"
        "<table><thead><tr><th>Line</th><th>Metric</th>"
        f"<th>{scorecards[0].comparison_year} mean</th>"
        f"<th>{scorecards[0].comparison_year} vs {scorecards[0].baseline_year}</th>"
        f"<th>{scorecards[0].comparison_year} vs network</th>"
        f"<th>{escape(scorecards[0].latest_ytd_label)}</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def build_route_overall_score_table(scores: Iterable[RouteOverallScore]) -> str:
    scores = tuple(scores)
    rows = []
    for score in scores:
        rows.append(
            "<tr>"
            f"<td>{escape(score.entity_id)}</td>"
            f"<td>{score.comparison_value:.2f}%</td>"
            f"<td>{score.delta_percent_points:+.2f} pp</td>"
            f"<td>{score.latest_ytd_value:.2f}%</td>"
            "</tr>"
        )
    return (
        "<section class='table-block'><h3>Secondary VBB overall score</h3>"
        "<table><thead><tr><th>Line</th>"
        f"<th>{scores[0].comparison_year} mean</th>"
        f"<th>{scores[0].comparison_year} vs {scores[0].baseline_year}</th>"
        f"<th>{escape(scores[0].latest_ytd_label)}</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def build_network_value_table(network_rows: Iterable[MetricRow]) -> str:
    values = {}
    for row in network_rows:
        values.setdefault(row.period, {})[row.metric_id] = row.value_percent
    body_rows = []
    for period in sorted(values):
        punctuality = values[period].get("punctuality_p3")
        reliability = values[period].get("reliability_zg")
        punctuality_text = f"{punctuality:.2f}%" if punctuality is not None else "-"
        reliability_text = f"{reliability:.2f}%" if reliability is not None else "-"
        body_rows.append(
            "<tr>"
            f"<td>{escape(period)}</td>"
            f"<td>{punctuality_text}</td>"
            f"<td>{reliability_text}</td>"
            "</tr>"
        )
    return (
        "<section class='table-block'><h3>Monthly network values</h3>"
        "<table><thead><tr><th>Period</th><th>Punctuality</th><th>Reliability</th></tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table></section>"
    )


def build_line_delta_table(line_deltas: Iterable[LineDelta]) -> str:
    line_deltas = tuple(line_deltas)
    body_rows = []
    for delta in line_deltas:
        body_rows.append(
            "<tr>"
            f"<td>{escape(delta.entity_id)}</td>"
            f"<td>{escape(METRIC_LABELS[delta.metric_id])}</td>"
            f"<td>{delta.baseline_value:.2f}%</td>"
            f"<td>{delta.comparison_value:.2f}%</td>"
            f"<td>{delta.delta_percent_points:+.2f} pp</td>"
            "</tr>"
        )
    return (
        "<section class='table-block'><h3>Line shift values</h3>"
        "<table><thead><tr><th>Line</th><th>Metric</th>"
        f"<th>{line_deltas[0].baseline_year} mean</th>"
        f"<th>{line_deltas[0].comparison_year} mean</th><th>Change</th></tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table></section>"
    )


def build_event_table(annotations: Iterable[AnnotationRow]) -> str:
    rows = list(annotations)
    if not rows:
        return ""
    body_rows = []
    for annotation in rows:
        body_rows.append(
            "<tr>"
            f"<td>{escape(annotation.start_date)}</td>"
            f"<td>{escape(annotation.chart_label)}</td>"
            f"<td>{escape(', '.join(annotation.affected_lines) or 'n/a')}</td>"
            f"<td>{escape(annotation.causal_caveat)}</td>"
            "</tr>"
        )
    return (
        "<section class='table-block'><h3>Context events</h3>"
        "<table><thead><tr><th>Date</th><th>Event</th><th>Lines</th><th>Interpretation guardrail</th></tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table></section>"
    )


def build_event_legend(annotations: Iterable[AnnotationRow]) -> str:
    rows = []
    for event_number, annotation in enumerate(annotations, start=1):
        color = ANNOTATION_COLORS.get(annotation.event_family, "#64748b")
        lines = ", ".join(annotation.affected_lines) or "Network"
        rows.append(
            "<article class='event-item'>"
            f"<span class='event-badge' style='--event-color: {color}'>{event_number}</span>"
            "<div>"
            f"<strong>{escape(annotation.start_date)} / {escape(annotation.chart_label)}</strong>"
            f"<span class='event-lines'>Lines: {escape(lines)}</span>"
            f"<p>{escape(annotation.summary)}</p>"
            "</div></article>"
        )
    if not rows:
        return ""
    return (
        "<section class='event-legend' aria-label='Context event legend'>"
        "<div class='event-legend-heading'><strong>Context events</strong>"
        "<span>Numbered markers match the notes below.</span></div>"
        f"<div class='event-list'>{''.join(rows)}</div></section>"
    )


def render_markdown(summary: ReportSummary) -> str:
    lines = [
        f"# {REPORT_TITLE.title()} conclusion",
        "",
        f"Observed VBB monthly trend window: `2019-01` to `{summary.observed_until}`.",
        "",
        "## Answer",
        "",
        summary.conclusion_text,
        "",
        "## Evidence highlights",
    ]
    lines.extend(f"- {finding}" for finding in summary.key_findings)
    lines.extend(
        [
            "",
            "## Personal route: S25 and S26",
            "",
            "The route view is a line-level comparison, not a claim about a particular journey.",
        ]
    )
    for scorecard in summary.route_scorecards:
        lines.append(
            "- "
            f"{scorecard.entity_id} {METRIC_LABELS[scorecard.metric_id]}: "
            f"{scorecard.comparison_value:.2f}% in {scorecard.comparison_year} "
            f"({scorecard.delta_percent_points:+.2f} pp vs {scorecard.baseline_year}; "
            f"{scorecard.network_gap_percent_points:+.2f} pp vs the network)."
        )
    for overall_score in summary.route_overall_scores:
        lines.append(
            "- "
            f"{overall_score.entity_id} secondary VBB overall score: "
            f"{overall_score.comparison_value:.2f}% in {overall_score.comparison_year} "
            f"({overall_score.delta_percent_points:+.2f} pp vs {overall_score.baseline_year})."
        )
    lines.extend(
        [
            "",
            "## Caveats",
            "",
        ]
    )
    lines.extend(f"- {caveat}" for caveat in summary.caveats)
    lines.extend(
        [
            "",
            "## Primary sources",
            "",
            (
                "- VBB Berlin S-Bahn quality tool: "
                f"{summary.source_urls['primary_quality_tool']}"
            ),
            (
                "- VBB quality archive for older backfill context only: "
                f"{summary.source_urls['quality_archive']}"
            ),
            (
                "- Repo inputs: `data/vbb_sbahn_quality_2019_onward.csv` and "
                "`data/vbb_sbahn_event_annotations_2023_2026.csv`."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def latest_ytd_metric(summary: ReportSummary, metric_id: str) -> MetricWindowSummary:
    latest_year = summary.observed_until[:4]
    return next(
        item
        for item in summary.comparable_ytd_summaries
        if item.metric_id == metric_id and item.label.startswith(f"{latest_year} YTD")
    )


def render_html(
    summary: ReportSummary,
    *,
    network_svg: str,
    annual_svg: str,
    line_svg: str,
    route_svg: str,
    network_rows: Iterable[MetricRow] = (),
    annotations: Iterable[AnnotationRow] = (),
) -> str:
    annotations = tuple(annotations)
    latest_year = int(summary.observed_until[:4])
    latest_month = int(summary.observed_until[5:])
    latest_month_name = month_label(latest_month)
    punctuality_baseline_ytd = next(
        item
        for item in summary.comparable_ytd_summaries
        if item.metric_id == "punctuality_p3"
        and item.label == f"{summary.baseline_year} Jan-{latest_month_name}"
    )
    punctuality_comparison_ytd = next(
        item
        for item in summary.comparable_ytd_summaries
        if item.metric_id == "punctuality_p3"
        and item.label == f"{summary.comparison_year} Jan-{latest_month_name}"
    )
    reliability_baseline_ytd = next(
        item
        for item in summary.comparable_ytd_summaries
        if item.metric_id == "reliability_zg"
        and item.label == f"{summary.baseline_year} Jan-{latest_month_name}"
    )
    reliability_comparison_ytd = next(
        item
        for item in summary.comparable_ytd_summaries
        if item.metric_id == "reliability_zg"
        and item.label == f"{summary.comparison_year} Jan-{latest_month_name}"
    )
    punctuality_ytd = latest_ytd_metric(summary, "punctuality_p3")
    reliability_ytd = latest_ytd_metric(summary, "reliability_zg")
    punctuality_deltas = [
        delta for delta in summary.line_deltas if delta.metric_id == "punctuality_p3"
    ]
    reliability_deltas = [
        delta for delta in summary.line_deltas if delta.metric_id == "reliability_zg"
    ]
    worst_punctuality = min(punctuality_deltas, key=lambda delta: delta.delta_percent_points)
    worst_reliability = min(reliability_deltas, key=lambda delta: delta.delta_percent_points)
    best_reliability = max(reliability_deltas, key=lambda delta: delta.delta_percent_points)
    exposure_lookup = {item.year: item for item in summary.punctuality_exposures}
    route_lookup = {
        (scorecard.entity_id, scorecard.metric_id): scorecard
        for scorecard in summary.route_scorecards
    }
    s25_punctuality = route_lookup[("S25", "punctuality_p3")]
    s25_reliability = route_lookup[("S25", "reliability_zg")]
    s26_punctuality = route_lookup[("S26", "punctuality_p3")]
    s26_reliability = route_lookup[("S26", "reliability_zg")]
    overall_lookup = {
        scorecard.entity_id: scorecard for scorecard in summary.route_overall_scores
    }
    s25_overall = overall_lookup["S25"]
    s26_overall = overall_lookup["S26"]
    caveats_html = "".join(f"<li>{escape(caveat)}</li>" for caveat in summary.caveats)
    full_year_table = build_summary_table(
        "Complete-year mean of monthly published values",
        summary.full_year_summaries,
    )
    comparable_table = build_summary_table(
        f"Jan-{latest_month_name} mean of monthly published values",
        summary.comparable_ytd_summaries,
    )
    exposure_table = build_punctuality_exposure_table(summary.punctuality_exposures)
    route_scorecard_table = build_route_scorecard_table(summary.route_scorecards)
    route_overall_score_table = build_route_overall_score_table(summary.route_overall_scores)
    event_legend = build_event_legend(annotations)
    network_value_table = build_network_value_table(network_rows)
    line_delta_table = build_line_delta_table(summary.line_deltas)
    event_table = build_event_table(annotations)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(REPORT_TITLE.title())}</title>
    <style>
      :root {{
        --bg: #f4f1e8;
        --panel: #fffdf8;
        --ink: #102a43;
        --muted: #627487;
        --border: #d9d4c8;
        --accent: #138a70;
        --coral: #d6654b;
        --gold: #d97706;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        color: #17202b;
        font-family: "Aptos", "Segoe UI", sans-serif;
        background:
          radial-gradient(circle at 8% 0%, rgba(19, 138, 112, 0.14), transparent 28rem),
          linear-gradient(180deg, #f8f6ef 0%, var(--bg) 58%, #eee9dd 100%);
      }}
      main {{ max-width: 1180px; margin: 0 auto; padding: 28px 22px 60px; }}
      h1, h2, h3, p {{ margin-top: 0; }}
      h1 {{
        max-width: 720px;
        margin-bottom: 16px;
        color: #f8f5eb;
        font-size: clamp(2.7rem, 7vw, 5.4rem);
        line-height: 0.93;
        letter-spacing: -0.065em;
      }}
      h2 {{ color: var(--ink); font-size: 1.55rem; letter-spacing: -0.035em; }}
      h3 {{ color: var(--ink); font-size: 1rem; }}
      .hero {{
        position: relative;
        overflow: hidden;
        padding: clamp(28px, 5vw, 58px);
        border-radius: 28px;
        background:
          radial-gradient(circle at 88% 12%, rgba(205, 236, 201, 0.22), transparent 16rem),
          linear-gradient(132deg, #102a43 0%, #153b55 65%, #126f63 100%);
        box-shadow: 0 24px 60px rgba(16, 42, 67, 0.22);
      }}
      .eyebrow, .section-index {{
        color: #bde8cf;
        font-size: 0.73rem;
        font-weight: 800;
        letter-spacing: 0.13em;
        text-transform: uppercase;
      }}
      .eyebrow {{ margin-bottom: 28px; }}
      .lede {{ max-width: 610px; margin-bottom: 22px; color: #dce9e5; font-size: 1.1rem; line-height: 1.45; }}
      .hero-meta {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; color: #b9cbd0; font-size: 0.86rem; }}
      .window-pill {{ padding: 7px 11px; border: 1px solid rgba(255,255,255,0.23); border-radius: 999px; color: #f8f5eb; }}
      .metric-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }}
      .tab-input {{ position: absolute; inline-size: 1px; block-size: 1px; opacity: 0; pointer-events: none; }}
      .tabs {{ display: flex; gap: 8px; margin-top: 22px; padding: 6px; border: 1px solid var(--border); border-radius: 16px; background: rgba(255, 253, 248, 0.76); }}
      .tab-label {{ flex: 1; cursor: pointer; padding: 11px 14px; border-radius: 11px; color: var(--muted); font-size: 0.86rem; font-weight: 800; text-align: center; transition: background 160ms ease, color 160ms ease; }}
      .tab-panel {{ display: none; }}
      #global-tab:checked ~ .tab-content .global-panel, #route-tab:checked ~ .tab-content .route-panel {{ display: block; }}
      #global-tab:checked ~ .tabs label[for="global-tab"], #route-tab:checked ~ .tabs label[for="route-tab"] {{ background: var(--ink); color: #f8f5eb; }}
      .metric-card, .section, .details-card {{
        border: 1px solid var(--border);
        background: rgba(255, 253, 248, 0.9);
        box-shadow: 0 16px 34px rgba(16, 42, 67, 0.08);
      }}
      .metric-card {{ padding: 22px 24px 20px; border-radius: 20px; }}
      .metric-card-top, .section-head, .signal-strip {{ display: flex; justify-content: space-between; gap: 16px; align-items: baseline; }}
      .metric-name {{ color: var(--muted); font-size: 0.9rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }}
      .metric-tag {{ color: var(--accent); font-size: 0.76rem; font-weight: 800; text-transform: uppercase; }}
      .metric-value {{ margin: 10px 0 2px; color: var(--ink); font-size: clamp(2.8rem, 6vw, 4.7rem); font-weight: 800; letter-spacing: -0.07em; line-height: 0.95; }}
      .metric-delta {{ color: var(--accent); font-size: 0.92rem; font-weight: 800; }}
      .metric-history {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--border); }}
      .metric-history span {{ display: grid; gap: 3px; }}
      .metric-history small {{ color: var(--muted); font-size: 0.72rem; }}
      .metric-history strong {{ color: var(--ink); font-size: 0.98rem; }}
      .metric-definition {{ margin-top: 15px; color: var(--muted); font-size: 0.78rem; }}
      .section {{ margin-top: 16px; padding: 24px; border-radius: 22px; }}
      .section-head {{ align-items: end; margin-bottom: 5px; }}
      .section-title {{ display: flex; gap: 12px; align-items: baseline; }}
      .section-index {{ color: var(--accent); }}
      .section-note, .chart-note {{ color: var(--muted); font-size: 0.8rem; }}
      .chart-note {{ margin-bottom: 0; }}
      .chart-frame {{ overflow-x: auto; margin-top: 18px; border-radius: 18px; }}
      .chart-svg {{ display: block; width: 100%; height: auto; min-width: 760px; }}
      .network-svg {{ min-width: 820px; }}
      .line-svg {{ min-width: 900px; }}
      .svg-kicker {{ fill: #138a70; font: 800 11px "Aptos", "Segoe UI", sans-serif; letter-spacing: 1.5px; }}
      .svg-legend, .svg-caption {{ fill: #627487; font: 600 12px "Aptos", "Segoe UI", sans-serif; }}
      .svg-panel-title {{ fill: #102a43; font: 800 17px "Aptos", "Segoe UI", sans-serif; }}
      .svg-panel-subtitle {{ fill: #627487; font: 500 12px "Aptos", "Segoe UI", sans-serif; }}
      .svg-axis, .svg-year, .svg-axis-label, .svg-line-label, .svg-delta {{ fill: #627487; font: 600 11px "Aptos", "Segoe UI", sans-serif; }}
      .svg-year {{ fill: #102a43; font-size: 12px; font-weight: 800; }}
      .svg-axis-label {{ fill: #102a43; font-size: 12px; }}
      .svg-line-label {{ fill: #102a43; font-weight: 800; }}
      .svg-delta {{ font-weight: 800; }}
      .svg-delta.negative {{ fill: #b74e3a; }}
      .svg-delta.positive {{ fill: #0b745e; }}
      .grid-line {{ stroke: #e8e3d8; stroke-width: 1; }}
      .legend-line {{ stroke: #102a43; stroke-width: 3; }}
      .zero-line {{ stroke: #102a43; stroke-width: 1.5; }}
      .network-path {{ fill: none; stroke: #102a43; stroke-linecap: round; stroke-linejoin: round; stroke-width: 3; }}
      .network-point {{ fill: #fbfaf6; stroke: #102a43; stroke-width: 2; }}
      .current-point {{ fill: #138a70; stroke: #fbfaf6; stroke-width: 2.5; }}
      .annual-punctuality, .annual-reliability {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 3; }}
      .annual-punctuality {{ stroke: #0f766e; }}
      .annual-reliability {{ stroke: #1d4ed8; }}
      .annual-ytd {{ stroke-dasharray: 7 6; }}
      .route-network, .route-s25, .route-s26 {{ fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 3; }}
      .route-network {{ stroke: #627487; stroke-dasharray: 7 6; }}
      .route-s25 {{ stroke: #d6654b; }}
      .route-s26 {{ stroke: #138a70; }}
      .route-point {{ stroke-width: 2; }}
      .event-point {{ stroke: #fbfaf6; stroke-width: 2; }}
      .event-number {{ fill: #fff; font: 900 8px "Aptos", "Segoe UI", sans-serif; pointer-events: none; }}
      .signal-strip {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 16px; }}
      .signal {{ padding: 16px; border-radius: 16px; background: #f1ede3; }}
      .signal-label {{ display: block; margin-bottom: 7px; color: var(--muted); font-size: 0.76rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }}
      .signal strong {{ color: var(--ink); font-size: 1.15rem; }}
      .route-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }}
      .route-card {{ padding: 22px 24px; border: 1px solid var(--border); border-radius: 20px; background: #f7f4ec; }}
      .route-card h3 {{ margin-bottom: 10px; font-size: 1.3rem; }}
      .route-card p {{ margin-bottom: 0; color: #43566a; font-size: 0.92rem; line-height: 1.5; }}
      .route-card strong {{ color: var(--ink); }}
      .event-legend {{ margin-top: 18px; padding: 16px; border: 1px solid var(--border); border-radius: 16px; background: #f7f4ec; }}
      .event-legend-heading {{ display: flex; justify-content: space-between; gap: 12px; margin-bottom: 12px; color: var(--ink); font-size: 0.86rem; }}
      .event-legend-heading span {{ color: var(--muted); font-weight: 600; }}
      .event-list {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 16px; }}
      .event-item {{ display: grid; grid-template-columns: 24px 1fr; gap: 9px; align-items: start; }}
      .event-badge {{ display: grid; place-items: center; inline-size: 22px; block-size: 22px; border-radius: 50%; background: var(--event-color); color: #fff; font-size: 0.72rem; font-weight: 800; }}
      .event-item strong {{ display: block; color: var(--ink); font-size: 0.78rem; line-height: 1.25; }}
      .event-lines {{ display: block; margin-top: 3px; color: var(--muted); font-size: 0.7rem; font-weight: 700; }}
      .event-item p {{ margin: 4px 0 0; color: #43566a; font-size: 0.74rem; line-height: 1.35; }}
      .details-card {{ margin-top: 16px; border-radius: 18px; }}
      .details-card summary {{ cursor: pointer; padding: 18px 20px; color: var(--ink); font-weight: 800; }}
      .details-content {{ padding: 0 20px 22px; }}
      .details-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px; }}
      .details-content p, .details-content li {{ color: #43566a; font-size: 0.88rem; line-height: 1.5; }}
      .details-content ul {{ margin: 0; padding-left: 1.1rem; }}
      .table-block {{ overflow-x: auto; margin-top: 18px; }}
      table {{ width: 100%; min-width: 580px; border-collapse: collapse; font-size: 0.8rem; }}
      th, td {{ padding: 9px 8px; border-bottom: 1px solid #e6e1d7; text-align: left; white-space: nowrap; }}
      th {{ color: var(--muted); font-weight: 800; }}
      a {{ color: #0b745e; }}
      code {{ color: #365268; font-size: 0.78rem; }}
      @media (max-width: 720px) {{
        main {{ padding: 14px 12px 36px; }}
        .hero {{ border-radius: 22px; padding: 28px 22px; }}
        .metric-grid, .signal-strip, .details-grid, .route-grid, .event-list {{ grid-template-columns: 1fr; }}
        .event-legend-heading {{ align-items: start; flex-direction: column; gap: 3px; }}
        .section {{ padding: 18px; border-radius: 18px; }}
        .section-head {{ align-items: start; flex-direction: column; gap: 5px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="eyebrow">Berlin S-Bahn / monthly KPI view</div>
        <h1>Service delivery improved.<br>Punctuality remains weaker.</h1>
        <p class="lede">The long-run VBB series shows train-km delivery rose from {summary.comparison_year - 1} to {summary.comparison_year}, while {summary.comparison_year} punctuality was the lowest complete-year result in the available series. The {latest_year} result is a partial year.</p>
        <div class="hero-meta">
          <span class="window-pill">Observed: Jan 2019 - {escape(summary.observed_until)}</span>
          <span>{latest_year} has {latest_month} observed months</span>
        </div>
      </section>

      <input class="tab-input" type="radio" name="dashboard-view" id="global-tab" checked>
      <input class="tab-input" type="radio" name="dashboard-view" id="route-tab">
      <div class="tabs" role="tablist" aria-label="Report view">
        <label class="tab-label" for="global-tab" role="tab">Network evidence</label>
        <label class="tab-label" for="route-tab" role="tab">My route: S25 + S26</label>
      </div>

      <div class="tab-content">
      <div class="tab-panel global-panel">
      <section class="metric-grid" aria-label="Current headline metrics">
        <article class="metric-card">
          <div class="metric-card-top"><span class="metric-name">Punctuality</span><span class="metric-tag">core KPI</span></div>
          <div class="metric-value">{punctuality_ytd.value_percent:.2f}%</div>
          <div class="metric-delta">{punctuality_ytd.value_percent - punctuality_comparison_ytd.value_percent:+.2f} pp vs Jan-{latest_month_name} {summary.comparison_year}</div>
          <div class="metric-history">
            <span><small>{summary.baseline_year} Jan-{latest_month_name}</small><strong>{punctuality_baseline_ytd.value_percent:.2f}%</strong></span>
            <span><small>{summary.comparison_year} Jan-{latest_month_name}</small><strong>{punctuality_comparison_ytd.value_percent:.2f}%</strong></span>
            <span><small>{latest_year} Jan-{latest_month_name}</small><strong>{punctuality_ytd.value_percent:.2f}%</strong></span>
          </div>
          <div class="metric-definition">Arrivals within 3:59 minutes</div>
        </article>
        <article class="metric-card">
          <div class="metric-card-top"><span class="metric-name">Reliability</span><span class="metric-tag">core KPI</span></div>
          <div class="metric-value">{reliability_ytd.value_percent:.2f}%</div>
          <div class="metric-delta">{reliability_ytd.value_percent - reliability_comparison_ytd.value_percent:+.2f} pp vs Jan-{latest_month_name} {summary.comparison_year}</div>
          <div class="metric-history">
            <span><small>{summary.baseline_year} Jan-{latest_month_name}</small><strong>{reliability_baseline_ytd.value_percent:.2f}%</strong></span>
            <span><small>{summary.comparison_year} Jan-{latest_month_name}</small><strong>{reliability_comparison_ytd.value_percent:.2f}%</strong></span>
            <span><small>{latest_year} Jan-{latest_month_name}</small><strong>{reliability_ytd.value_percent:.2f}%</strong></span>
          </div>
          <div class="metric-definition">Train-km delivered vs scheduled</div>
        </article>
      </section>

      <section class="section">
        <div class="section-head">
          <div class="section-title"><span class="section-index">01</span><h2>The two primary KPIs diverged</h2></div>
          <span class="section-note">complete years plus {latest_year} YTD</span>
        </div>
        <p class="chart-note">Reliability increased from {summary.comparison_year - 1} to {summary.comparison_year}, while punctuality fell to the lowest complete-year result in the available VBB series. This is a descriptive comparison, not a combined score or causal claim.</p>
        <div class="chart-frame">{annual_svg}</div>
      </section>

      <section class="section">
        <div class="section-head">
          <div class="section-title"><span class="section-index">02</span><h2>Punctuality is the persistent weakness in this series</h2></div>
          <span class="section-note">2019 through {escape(summary.observed_until)}</span>
        </div>
        <p class="chart-note">Punctuality reached its weakest complete-year result in {summary.comparison_year} while reliability increased. The measures are intentionally shown separately because they capture different commuter failure modes.</p>
        <div class="chart-frame">{network_svg}</div>
        {event_legend}
        <div class="signal-strip" aria-label="Network evidence highlights">
          <div class="signal"><span class="signal-label">{summary.comparison_year} weak-month exposure</span><strong>{exposure_lookup[summary.comparison_year].months_below_reference}/12 below {summary.punctuality_reference_percent:.1f}%</strong></div>
          <div class="signal"><span class="signal-label">Punctuality</span><strong>{punctuality_comparison_ytd.value_percent:.2f}% Jan-{latest_month_name} {summary.comparison_year}</strong></div>
          <div class="signal"><span class="signal-label">Reliability</span><strong>{reliability_ytd.value_percent - reliability_comparison_ytd.value_percent:+.2f} pp vs {summary.comparison_year} YTD</strong></div>
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <div class="section-title"><span class="section-index">03</span><h2>Line shifts</h2></div>
          <span class="section-note">{summary.comparison_year} vs {summary.baseline_year}</span>
        </div>
        <p class="chart-note">Change in the mean of monthly published values. Negative bars mean the line average fell. {sum(delta.metric_id == 'punctuality_p3' and delta.delta_percent_points < 0 for delta in punctuality_deltas)}/{len(punctuality_deltas)} published line averages lost punctuality, while {sum(delta.metric_id == 'reliability_zg' and delta.delta_percent_points > 0 for delta in reliability_deltas)}/{len(reliability_deltas)} improved reliability. This count is unweighted and does not measure passenger or train-km exposure.</p>
        <div class="chart-frame">{line_svg}</div>
        <div class="signal-strip" aria-label="Key line shifts">
          <div class="signal"><span class="signal-label">Largest punctuality fall</span><strong>{worst_punctuality.entity_id} {worst_punctuality.delta_percent_points:+.2f} pp</strong></div>
          <div class="signal"><span class="signal-label">Largest reliability fall</span><strong>{worst_reliability.entity_id} {worst_reliability.delta_percent_points:+.2f} pp</strong></div>
          <div class="signal"><span class="signal-label">Largest reliability rise</span><strong>{best_reliability.entity_id} {best_reliability.delta_percent_points:+.2f} pp</strong></div>
        </div>
      </section>

      <details class="details-card">
        <summary>Method and source trail</summary>
        <div class="details-content">
          <div class="details-grid">
            <div>
              <h3>How to read</h3>
              <p>Complete-year and partial-year values are simple means of the published monthly percentages. They are useful descriptive comparisons, not weighted annual aggregates.</p>
            </div>
            <div>
              <h3>Evidence boundary</h3>
              <p>The headline claim uses the VBB primary KPI series. Event markers are interpretation context only; they are not used to assert a cause for a monthly movement.</p>
            </div>
          </div>
          <div class="table-block">{full_year_table}{comparable_table}{exposure_table}{network_value_table}{line_delta_table}{event_table}</div>
          <h3>Caveats</h3>
          <ul>{caveats_html}</ul>
          <p><a href="{escape(summary.source_urls['primary_quality_tool'])}">VBB Berlin S-Bahn quality tool</a> / <a href="{escape(summary.source_urls['quality_archive'])}">VBB quality archive</a></p>
          <p><code>data/vbb_sbahn_quality_2019_onward.csv</code> / <code>data/vbb_sbahn_event_annotations_2023_2026.csv</code></p>
        </div>
      </details>
      </div>

      <div class="tab-panel route-panel">
        <section class="section">
          <div class="section-head">
            <div class="section-title"><span class="section-index">Personal view</span><h2>Personal route deep dive</h2></div>
            <span class="section-note">S25 and S26 line-level KPIs</span>
          </div>
          <p class="chart-note">These lines make the network-level divergence tangible: S25 maintained train-km delivery while punctuality fell; S26 increased reliability from a much lower starting point. The secondary overall score adds context but does not replace the primary KPIs.</p>
          <div class="chart-frame">{route_svg}</div>
        </section>

        <section class="route-grid" aria-label="S25 and S26 findings">
          <article class="route-card">
            <h3>S25: delivered, but later</h3>
            <p>In {s25_punctuality.comparison_year}, <strong>punctuality fell {s25_punctuality.delta_percent_points:+.2f} pp</strong> versus {s25_punctuality.baseline_year} to {s25_punctuality.comparison_value:.2f}%; {s25_punctuality.network_gap_percent_points:+.2f} pp against the network. Yet reliability was {s25_reliability.comparison_value:.2f}% ({s25_reliability.delta_percent_points:+.2f} pp versus {s25_reliability.baseline_year}). The secondary overall score also fell {s25_overall.delta_percent_points:+.2f} pp. That is a commuter-relevant split: trains ran, but they arrived less reliably on time.</p>
          </article>
          <article class="route-card">
            <h3>S26: recovery, still a gap</h3>
            <p>S26 reliability rose <strong>{s26_reliability.delta_percent_points:+.2f} pp</strong> from {s26_reliability.baseline_year} to {s26_reliability.comparison_value:.2f}% in {s26_reliability.comparison_year}, but remained {s26_reliability.network_gap_percent_points:+.2f} pp below the network. Its secondary overall score rose {s26_overall.delta_percent_points:+.2f} pp. Punctuality was stronger at {s26_punctuality.comparison_value:.2f}% ({s26_punctuality.network_gap_percent_points:+.2f} pp versus network), so delivery rather than late running remains the larger relative weakness.</p>
          </article>
        </section>

        <section class="section">
          <div class="section-head">
            <div class="section-title"><span class="section-index">Route scorecard</span><h2>What changed, and what improved</h2></div>
            <span class="section-note">{summary.baseline_year} baseline / {summary.comparison_year} full year / {latest_year} Jan-{latest_month_name}</span>
          </div>
          <p class="chart-note">The current-year figures are matched Jan-{latest_month_name} comparisons. They may signal improvement, but they do not turn a {latest_month}-month window into an annual result.</p>
          {route_scorecard_table}
          {route_overall_score_table}
        </section>
      </div>
      </div>
    </main>
  </body>
</html>
"""


def write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


STANDALONE_SVG_STYLE = """
.svg-kicker { fill: #138a70; font: 800 11px Aptos, Segoe UI, sans-serif; letter-spacing: 1.5px; }
.svg-legend, .svg-caption { fill: #627487; font: 600 12px Aptos, Segoe UI, sans-serif; }
.svg-panel-title { fill: #102a43; font: 800 17px Aptos, Segoe UI, sans-serif; }
.svg-axis, .svg-year, .svg-axis-label { fill: #627487; font: 600 11px Aptos, Segoe UI, sans-serif; }
.svg-year { fill: #102a43; font-size: 12px; font-weight: 800; }
.svg-axis-label { fill: #102a43; font-size: 12px; }
.grid-line { stroke: #e8e3d8; stroke-width: 1; }
.annual-punctuality, .annual-reliability { fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 3; }
.annual-punctuality { stroke: #0f766e; }
.annual-reliability { stroke: #1d4ed8; }
.annual-ytd { stroke-dasharray: 7 6; }
.route-network, .route-s25, .route-s26 { fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 3; }
.route-network { stroke: #627487; stroke-dasharray: 7 6; }
.route-s25 { stroke: #d6654b; }
.route-s26 { stroke: #138a70; }
.route-point { stroke: #fbfaf6; stroke-width: 2; }
.route-point.route-network { fill: #fbfaf6; }
.route-point.route-s25 { fill: #d6654b; }
.route-point.route-s26 { fill: #138a70; }
"""


def standalone_svg(svg: str) -> str:
    """Embed the small stylesheet needed when a report chart is viewed alone."""
    return svg.replace("</svg>", f"<style>{STANDALONE_SVG_STYLE}</style></svg>")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the final offline HTML report for Berlin S-Bahn reliability trends."
    )
    parser.add_argument("--network-csv", type=Path, default=DEFAULT_NETWORK_CSV)
    parser.add_argument("--line-csv", type=Path, default=DEFAULT_LINE_CSV)
    parser.add_argument("--baseline-year", type=int, default=LINE_BASELINE_YEAR)
    parser.add_argument("--comparison-year", type=int, default=LINE_COMPARISON_YEAR)
    parser.add_argument(
        "--punctuality-reference-percent",
        type=float,
        default=PUNCTUALITY_REFERENCE_PERCENT,
    )
    parser.add_argument("--annotations-csv", type=Path, default=DEFAULT_ANNOTATIONS_CSV)
    parser.add_argument("--notes-json", type=Path, default=DEFAULT_NOTES_JSON)
    parser.add_argument("--sources-json", type=Path, default=DEFAULT_SOURCES_JSON)
    parser.add_argument("--output-html", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--asset-dir", type=Path, default=DEFAULT_ASSET_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    network_source_rows = load_metric_rows(args.network_csv)
    line_source_rows = load_metric_rows(args.line_csv)
    network_rows = [
        row for row in network_source_rows if row.entity_scope == "network"
    ]
    line_rows = [row for row in line_source_rows if row.entity_scope == "line"]
    all_quality_rows = (
        network_source_rows
        if args.network_csv == args.line_csv
        else network_source_rows + line_source_rows
    )
    annotations = load_annotation_rows(args.annotations_csv)
    notes_metadata = load_json(args.notes_json)
    sources_metadata = load_json(args.sources_json)

    source_urls = {
        "primary_quality_tool": sources_metadata["source_urls"]["primary_quality_tool"],
        "quality_archive": sources_metadata["source_urls"]["quality_archive"],
        "observed_until": notes_metadata["period_range"]["observed_until"],
    }

    summary = build_report_summary(
        network_rows,
        line_rows,
        source_urls=source_urls,
        baseline_year=args.baseline_year,
        comparison_year=args.comparison_year,
        punctuality_reference_percent=args.punctuality_reference_percent,
    )
    network_svg = build_network_svg(
        network_rows,
        annotations,
        comparison_year=summary.comparison_year,
    )
    annual_svg = build_annual_network_svg(summary)
    line_svg = build_line_comparison_svg(summary.line_deltas)
    route_svg = build_route_comparison_svg(all_quality_rows, summary.route_scorecards)

    html_output = render_html(
        summary,
        network_svg=network_svg,
        annual_svg=annual_svg,
        line_svg=line_svg,
        route_svg=route_svg,
        network_rows=network_rows,
        annotations=annotations,
    )
    markdown_output = render_markdown(summary)

    write_text(args.output_html, html_output)
    write_text(args.output_markdown, markdown_output)
    write_text(
        args.asset_dir / "annual_network_divergence.svg",
        standalone_svg(annual_svg),
    )
    write_text(
        args.asset_dir / "s25_s26_route_comparison.svg",
        standalone_svg(route_svg),
    )
    print(f"Wrote offline HTML report to {args.output_html}")
    print(f"Wrote written conclusion to {args.output_markdown}")
    print(f"Wrote README chart assets to {args.asset_dir}")


if __name__ == "__main__":
    main()
