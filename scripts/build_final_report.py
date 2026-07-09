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
DEFAULT_NETWORK_CSV = Path("data/vbb_sbahn_monthly_network_trends_2023_2026.csv")
DEFAULT_LINE_CSV = Path("data/vbb_sbahn_monthly_line_trends_2023_2026.csv")
DEFAULT_ANNOTATIONS_CSV = Path("data/vbb_sbahn_event_annotations_2023_2026.csv")
DEFAULT_NOTES_JSON = Path("data/vbb_sbahn_monthly_trend_notes_2023_2026.json")
DEFAULT_SOURCES_JSON = Path("data/vbb_sbahn_quality_sources.json")
DEFAULT_HTML_OUTPUT = Path("reports/berlin_sbahn_reliability_trend.html")
DEFAULT_MARKDOWN_OUTPUT = Path("reports/berlin_sbahn_reliability_conclusion.md")

HEADLINE_METRICS = ("punctuality_p3", "reliability_zg")
LINE_BASELINE_YEAR = 2023
LINE_COMPARISON_YEAR = 2025

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

TAGESSPIEGEL_CROSS_CHECKS = (
    {
        "slug": "tagesspiegel_2024_q1_q3",
        "published_date": "2024-12-12",
        "title": "Tagesspiegel: Berliner S-Bahn kommt aus der Krise nicht heraus",
        "url": (
            "https://www.tagesspiegel.de/berlin/"
            "zugverspatungen-um-vier-prozent-gestiegen-berliner-s-bahn-kommt-aus-der-"
            "krise-nicht-heraus-12853352.html"
        ),
        "metric_id": "punctuality_p3",
        "comparison_year": 2024,
        "end_month": 9,
        "published_value": 93.9,
        "published_note": (
            "Tagesspiegel reports 93.9% punctuality for the first nine months of 2024."
        ),
    },
    {
        "slug": "tagesspiegel_2025_q1_q3",
        "published_date": "2025-12-30",
        "title": "Tagesspiegel: operating situation worsened in 2025",
        "url": (
            "https://www.tagesspiegel.de/berlin/"
            "lage-hat-sich-2025-verscharft-135298-zuge-kamen-zu-spat--die-berliner-"
            "s-bahn-wird-immer-unzuverlassiger-15087045.html"
        ),
        "metric_id": "punctuality_p3",
        "comparison_year": 2025,
        "end_month": 9,
        "published_value": 92.9,
        "published_note": (
            "Tagesspiegel reports 92.9% punctuality for the first nine months of 2025."
        ),
    },
)


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
class CrossCheckResult:
    slug: str
    title: str
    url: str
    published_date: str
    window_label: str
    metric_id: str
    published_value: float
    observed_value: float
    difference_percent_points: float
    published_note: str


@dataclass(frozen=True)
class ReportSummary:
    observed_until: str
    conclusion_label: str
    conclusion_text: str
    key_findings: tuple[str, ...]
    caveats: tuple[str, ...]
    full_year_summaries: tuple[MetricWindowSummary, ...]
    comparable_ytd_summaries: tuple[MetricWindowSummary, ...]
    cross_checks: tuple[CrossCheckResult, ...]
    line_deltas: tuple[LineDelta, ...]
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


def build_line_deltas(line_rows: list[MetricRow]) -> tuple[LineDelta, ...]:
    deltas: list[LineDelta] = []
    line_ids = sorted({row.entity_id for row in line_rows})
    for metric_id in HEADLINE_METRICS:
        for line_id in line_ids:
            baseline_rows = metric_rows_for(
                [row for row in line_rows if row.entity_id == line_id],
                metric_id=metric_id,
                year=LINE_BASELINE_YEAR,
            )
            comparison_rows = metric_rows_for(
                [row for row in line_rows if row.entity_id == line_id],
                metric_id=metric_id,
                year=LINE_COMPARISON_YEAR,
            )
            if not baseline_rows or not comparison_rows:
                continue
            baseline_value = mean(row.value_percent for row in baseline_rows)
            comparison_value = mean(row.value_percent for row in comparison_rows)
            deltas.append(
                LineDelta(
                    metric_id=metric_id,
                    entity_id=line_id,
                    baseline_year=LINE_BASELINE_YEAR,
                    comparison_year=LINE_COMPARISON_YEAR,
                    baseline_value=baseline_value,
                    comparison_value=comparison_value,
                    delta_percent_points=comparison_value - baseline_value,
                )
            )
    return tuple(
        sorted(deltas, key=lambda delta: (delta.metric_id, delta.delta_percent_points, delta.entity_id))
    )


def build_cross_checks(network_rows: list[MetricRow]) -> tuple[CrossCheckResult, ...]:
    results: list[CrossCheckResult] = []
    for definition in TAGESSPIEGEL_CROSS_CHECKS:
        observed = summarize_window(
            network_rows,
            metric_id=definition["metric_id"],
            label=f"Tagesspiegel {definition['comparison_year']}",
            year=definition["comparison_year"],
            end_month=definition["end_month"],
        )
        results.append(
            CrossCheckResult(
                slug=definition["slug"],
                title=definition["title"],
                url=definition["url"],
                published_date=definition["published_date"],
                window_label=f"Jan-{month_label(definition['end_month'])} {definition['comparison_year']}",
                metric_id=definition["metric_id"],
                published_value=float(definition["published_value"]),
                observed_value=observed.value_percent,
                difference_percent_points=observed.value_percent - float(definition["published_value"]),
                published_note=definition["published_note"],
            )
        )
    return tuple(results)


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
) -> ReportSummary:
    observed_until = max(row.period for row in network_rows)
    latest_year, latest_month = (int(part) for part in observed_until.split("-"))
    full_year_summaries = build_full_year_summaries(network_rows)
    comparable_ytd_summaries = build_comparable_ytd_summaries(
        network_rows,
        latest_year=latest_year,
        latest_month=latest_month,
    )
    line_deltas = build_line_deltas(line_rows)
    cross_checks = build_cross_checks(network_rows)

    summary_lookup = {(item.metric_id, item.label): item for item in full_year_summaries}
    ytd_lookup = {(item.metric_id, item.label): item for item in comparable_ytd_summaries}
    punctuality_2023 = summary_lookup[("punctuality_p3", "2023")].value_percent
    punctuality_2024 = summary_lookup[("punctuality_p3", "2024")].value_percent
    punctuality_2025 = summary_lookup[("punctuality_p3", "2025")].value_percent
    reliability_2023 = summary_lookup[("reliability_zg", "2023")].value_percent
    reliability_2024 = summary_lookup[("reliability_zg", "2024")].value_percent
    reliability_2025 = summary_lookup[("reliability_zg", "2025")].value_percent
    latest_ytd_label = f"{latest_year} YTD (Jan-{month_label(latest_month)})"
    punctuality_latest_ytd = ytd_lookup[("punctuality_p3", latest_ytd_label)].value_percent
    reliability_latest_ytd = ytd_lookup[("reliability_zg", latest_ytd_label)].value_percent

    worst_reliability_month = min(
        metric_rows_for(network_rows, metric_id="reliability_zg"),
        key=lambda row: row.value_percent,
    )

    punctuality_losses = [
        delta
        for delta in line_deltas
        if delta.metric_id == "punctuality_p3" and delta.delta_percent_points < 0
    ][:4]
    reliability_losses = [
        delta
        for delta in line_deltas
        if delta.metric_id == "reliability_zg" and delta.delta_percent_points < 0
    ][:4]

    conclusion_text = (
        "The primary VBB KPI evidence points to a mixed trend rather than a clean, "
        "one-direction decline. Network punctuality was materially worse in 2025 than "
        f"in 2023 or 2024 ({punctuality_2025:.2f}% versus {punctuality_2023:.2f}% and "
        f"{punctuality_2024:.2f}%), which supports a real deterioration in day-to-day "
        "service quality during 2025. But network reliability did not keep falling "
        f"across the whole window: 2024 was dragged down by a severe January low at "
        f"{worst_reliability_month.value_percent:.2f}%, 2025 recovered close to the "
        f"2023 full-year level ({reliability_2025:.2f}% versus {reliability_2023:.2f}%), "
        f"and the observed {latest_year} year-to-date window through {observed_until} is stronger "
        f"on both headline metrics ({punctuality_latest_ytd:.2f}% punctuality, "
        f"{reliability_latest_ytd:.2f}% reliability)."
    )

    key_findings = (
        f"Whole-network punctuality worsened from {punctuality_2024:.2f}% in 2024 to "
        f"{punctuality_2025:.2f}% in 2025, after a flatter 2023 to 2024 change.",
        f"Whole-network reliability improved from the weak 2024 full-year average of "
        f"{reliability_2024:.2f}% to {reliability_2025:.2f}% in 2025, landing almost "
        f"back on the 2023 level of {reliability_2023:.2f}%.",
        (
            "The largest 2025 punctuality drops versus 2023 were on "
            + ", ".join(
                f"{delta.entity_id} ({delta.delta_percent_points:.2f} pp)"
                for delta in punctuality_losses
            )
            + "."
        ),
        (
            "The sharpest 2025 reliability declines versus 2023 were on "
            + ", ".join(
                f"{delta.entity_id} ({delta.delta_percent_points:.2f} pp)"
                for delta in reliability_losses
            )
            + "."
        ),
        (
            f"The Tagesspiegel 2025 cross-check is directionally consistent: its "
            f"Jan-Sep 2025 punctuality figure of 92.9% is only "
            f"{abs(cross_checks[-1].difference_percent_points):.2f} percentage points "
            "away from the VBB-series average computed from this repo."
        ),
    )

    caveats = (
        f"The current VBB monthly trend window stops at {observed_until}, so 2026 is "
        "not yet a full-year comparison.",
        "The core claim should stay anchored on VBB monthly punctuality and reliability KPIs, not on disruption-count proxies.",
        "The Tagesspiegel articles are a useful external cross-check for punctuality, but their cancellation shares are not numerically identical to the VBB train-km reliability KPI.",
        "Pre-2019 archive backfill remains outside the headline charts because compatibility with the current VBB tool is not proven.",
    )

    return ReportSummary(
        observed_until=observed_until,
        conclusion_label="mixed",
        conclusion_text=conclusion_text,
        key_findings=key_findings,
        caveats=caveats,
        full_year_summaries=full_year_summaries,
        comparable_ytd_summaries=comparable_ytd_summaries,
        cross_checks=cross_checks,
        line_deltas=line_deltas,
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


def build_network_svg(network_rows: list[MetricRow], annotations: list[AnnotationRow]) -> str:
    periods = sorted({row.period for row in network_rows})
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
        '<desc id="network-chart-desc">Monthly punctuality and reliability from January 2023 through the latest observed month. The 2025 and 2026 year-to-date periods are shaded for comparison.</desc>',
        '<rect width="100%" height="100%" rx="18" fill="#fbfaf6"/>',
        '<text x="78" y="30" class="svg-kicker">WHOLE-NETWORK PULSE</text>',
        '<line x1="285" y1="25" x2="315" y2="25" class="legend-line"/>',
        '<text x="323" y="30" class="svg-legend">monthly KPI</text>',
        '<rect x="410" y="18" width="18" height="14" rx="3" fill="#fff0df"/>',
        '<text x="436" y="30" class="svg-legend">2025</text>',
        '<rect x="495" y="18" width="18" height="14" rx="3" fill="#e7f5ee"/>',
        '<text x="521" y="30" class="svg-legend">2026 Jan-May</text>',
        '<circle cx="680" cy="25" r="4" fill="#d97706"/>',
        '<text x="692" y="30" class="svg-legend">context event</text>',
    ]

    year_groups: dict[int, list[int]] = {}
    for index, period in enumerate(periods):
        year_groups.setdefault(int(period[:4]), []).append(index)
    for year, indices in year_groups.items():
        band_left = max(left, _svg_x(indices[0], len(periods), left, plot_width) - step / 2)
        band_right = min(width - right, _svg_x(indices[-1], len(periods), left, plot_width) + step / 2)
        fill = "#fff0df" if year == 2025 else "#e7f5ee" if year == max(year_groups) else "#f3f1eb"
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
    for annotation in annotations:
        annotation_period = annotation.start_date[:7]
        if annotation_period not in period_index:
            continue
        x = _svg_x(period_index[annotation_period], len(periods), left, plot_width)
        color = ANNOTATION_COLORS.get(annotation.event_family, "#64748b")
        title = f"{annotation.chart_label}: {annotation.summary}"
        parts.append(
            f'<circle cx="{x:.1f}" cy="{height - 33}" r="4.5" fill="{color}" class="event-point">'
            f'<title>{escape(title)}</title></circle>'
        )
    parts.append("</svg>")
    return "".join(parts)


def build_line_comparison_svg(line_deltas: tuple[LineDelta, ...]) -> str:
    width = 1080
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
        '<desc id="line-chart-desc">Change in each S-Bahn line average from 2023 to 2025, shown in percentage points. Bars left of zero indicate deterioration.</desc>',
        '<rect width="100%" height="100%" rx="18" fill="#fbfaf6"/>',
        '<text x="78" y="30" class="svg-kicker">LINE SHIFTS</text>',
        f'<text x="78" y="54" class="svg-caption">{LINE_COMPARISON_YEAR} average minus {LINE_BASELINE_YEAR} average · percentage points</text>',
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
                f"{delta.entity_id}: {LINE_BASELINE_YEAR} {delta.baseline_value:.2f}%, "
                f"{LINE_COMPARISON_YEAR} {delta.comparison_value:.2f}%, {label}"
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


def build_summary_table(
    title: str,
    summaries: Iterable[MetricWindowSummary],
) -> str:
    rows = list(summaries)
    header = (
        "<thead><tr><th>Window</th><th>Metric</th><th>Average</th>"
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


def build_cross_check_table(cross_checks: Iterable[CrossCheckResult]) -> str:
    rows = []
    for cross_check in cross_checks:
        rows.append(
            "<tr>"
            f"<td><a href='{escape(cross_check.url)}'>{escape(cross_check.title)}</a></td>"
            f"<td>{cross_check.window_label}</td>"
            f"<td>{cross_check.published_value:.1f}%</td>"
            f"<td>{cross_check.observed_value:.2f}%</td>"
            f"<td>{cross_check.difference_percent_points:+.2f} pp</td>"
            "</tr>"
        )
    return (
        "<section class='table-block'><h3>Tagesspiegel punctuality cross-check</h3>"
        "<table><thead><tr><th>Article</th><th>Window</th><th>Published</th>"
        "<th>Repo series</th><th>Difference</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def render_markdown(summary: ReportSummary) -> str:
    lines = [
        f"# {REPORT_TITLE.title()} conclusion",
        "",
        f"Observed VBB monthly trend window: `2023-01` to `{summary.observed_until}`.",
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
            "## Tagesspiegel cross-check",
            "",
            (
                "The external Tagesspiegel punctuality figures line up closely with the "
                "VBB monthly series used here."
            ),
            "",
        ]
    )
    for cross_check in summary.cross_checks:
        lines.append(
            "- "
            f"[{cross_check.title}]({cross_check.url}) on `{cross_check.published_date}` "
            f"reported `{cross_check.published_value:.1f}%` punctuality for "
            f"`{cross_check.window_label}`; the VBB-series average in this repo is "
            f"`{cross_check.observed_value:.2f}%` "
            f"(`{cross_check.difference_percent_points:+.2f}` percentage points)."
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
                "- Repo inputs: `data/vbb_sbahn_monthly_network_trends_2023_2026.csv`, "
                "`data/vbb_sbahn_monthly_line_trends_2023_2026.csv`, and "
                "`data/vbb_sbahn_event_annotations_2023_2026.csv`."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def render_html(
    summary: ReportSummary,
    *,
    network_figure,
    line_figure,
) -> str:
    network_html = network_figure.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"displayModeBar": False, "responsive": True},
    )
    line_html = line_figure.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
    )

    findings_html = "".join(f"<li>{escape(finding)}</li>" for finding in summary.key_findings)
    caveats_html = "".join(f"<li>{escape(caveat)}</li>" for caveat in summary.caveats)

    full_year_table = build_summary_table("Full-year headline averages", summary.full_year_summaries)
    comparable_table = build_summary_table(
        "Comparable Jan-May averages aligned to the 2026 observed window",
        summary.comparable_ytd_summaries,
    )
    cross_check_table = build_cross_check_table(summary.cross_checks)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(REPORT_TITLE.title())}</title>
    <style>
      :root {{
        --bg: #f7f5ef;
        --panel: #fffdf8;
        --ink: #172554;
        --muted: #475569;
        --border: #d6d3d1;
        --accent: #0f766e;
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        font-family: "Segoe UI", "Trebuchet MS", sans-serif;
        background:
          radial-gradient(circle at top left, rgba(15, 118, 110, 0.08), transparent 28rem),
          linear-gradient(180deg, #fefce8 0%, var(--bg) 38%, #f5f3ff 100%);
        color: #111827;
      }}
      main {{
        max-width: 1160px;
        margin: 0 auto;
        padding: 2.5rem 1.25rem 3rem;
      }}
      h1, h2, h3 {{
        color: var(--ink);
        margin: 0 0 0.75rem;
      }}
      p {{
        line-height: 1.55;
        color: #1f2937;
      }}
      .hero {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 1.5rem;
        padding: 1.5rem;
        box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
      }}
      .eyebrow {{
        display: inline-block;
        font-size: 0.85rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--accent);
        margin-bottom: 0.75rem;
      }}
      .cards {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 1rem;
        margin-top: 1.25rem;
      }}
      .card {{
        background: rgba(255, 255, 255, 0.78);
        border: 1px solid var(--border);
        border-radius: 1rem;
        padding: 1rem;
      }}
      .card .label {{
        color: var(--muted);
        font-size: 0.9rem;
        margin-bottom: 0.35rem;
      }}
      .card .value {{
        color: var(--ink);
        font-size: 1.9rem;
        font-weight: 700;
      }}
      .section {{
        margin-top: 1.5rem;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 1.5rem;
        padding: 1.4rem;
        box-shadow: 0 14px 30px rgba(15, 23, 42, 0.06);
      }}
      ul {{
        margin: 0;
        padding-left: 1.2rem;
      }}
      li {{
        margin: 0.45rem 0;
        color: #1f2937;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.85rem;
      }}
      th, td {{
        text-align: left;
        padding: 0.7rem 0.55rem;
        border-bottom: 1px solid #e7e5e4;
      }}
      th {{
        color: var(--muted);
        font-weight: 600;
      }}
      a {{
        color: #1d4ed8;
      }}
      .source-list {{
        margin-top: 0.9rem;
      }}
      .plot {{
        margin-top: 1rem;
      }}
      @media (max-width: 720px) {{
        main {{
          padding: 1rem 0.85rem 2rem;
        }}
        .hero, .section {{
          border-radius: 1.1rem;
          padding: 1rem;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="eyebrow">Plotly shareable artifact</div>
        <h1>{escape(REPORT_TITLE.title())}</h1>
        <p>{escape(summary.conclusion_text)}</p>
        <p><strong>Observed window:</strong> 2023-01 to {escape(summary.observed_until)}.</p>
        <div class="cards">
          <div class="card">
            <div class="label">2025 punctuality</div>
            <div class="value">{next(item for item in summary.full_year_summaries if item.metric_id == 'punctuality_p3' and item.label == '2025').value_percent:.2f}%</div>
          </div>
          <div class="card">
            <div class="label">2025 reliability</div>
            <div class="value">{next(item for item in summary.full_year_summaries if item.metric_id == 'reliability_zg' and item.label == '2025').value_percent:.2f}%</div>
          </div>
          <div class="card">
            <div class="label">2026 YTD punctuality</div>
            <div class="value">{next(item for item in summary.comparable_ytd_summaries if item.metric_id == 'punctuality_p3' and item.label.startswith('2026 YTD')).value_percent:.2f}%</div>
          </div>
          <div class="card">
            <div class="label">2026 YTD reliability</div>
            <div class="value">{next(item for item in summary.comparable_ytd_summaries if item.metric_id == 'reliability_zg' and item.label.startswith('2026 YTD')).value_percent:.2f}%</div>
          </div>
        </div>
      </section>

      <section class="section">
        <h2>Key findings</h2>
        <ul>{findings_html}</ul>
      </section>

      <section class="section">
        <h2>Whole-network trend</h2>
        <p>
          The network view keeps VBB monthly KPIs as the primary evidence layer and uses
          curated infrastructure and operating events as explanatory context only.
        </p>
        <div class="plot">{network_html}</div>
      </section>

      <section class="section">
        <h2>Line-level comparison</h2>
        <p>
          This comparison shows how 2025 average line performance shifted versus the 2023
          baseline. It helps show where the deterioration was concentrated instead of
          implying a perfectly uniform network-wide decline.
        </p>
        <div class="plot">{line_html}</div>
      </section>

      <section class="section">
        <h2>Supporting tables</h2>
        {full_year_table}
        {comparable_table}
        {cross_check_table}
      </section>

      <section class="section">
        <h2>Caveats</h2>
        <ul>{caveats_html}</ul>
      </section>

      <section class="section">
        <h2>Source trail</h2>
        <ul class="source-list">
          <li><a href="{escape(summary.source_urls['primary_quality_tool'])}">VBB Berlin S-Bahn quality tool</a></li>
          <li><a href="{escape(summary.source_urls['quality_archive'])}">VBB quality archive</a></li>
          <li>Repo inputs: <code>data/vbb_sbahn_monthly_network_trends_2023_2026.csv</code>, <code>data/vbb_sbahn_monthly_line_trends_2023_2026.csv</code>, <code>data/vbb_sbahn_event_annotations_2023_2026.csv</code></li>
          <li><a href="{escape(summary.cross_checks[-1].url)}">Tagesspiegel 2025 cross-check</a></li>
        </ul>
      </section>
    </main>
  </body>
</html>
"""


def write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the final Plotly report for Berlin S-Bahn reliability trends."
    )
    parser.add_argument("--network-csv", type=Path, default=DEFAULT_NETWORK_CSV)
    parser.add_argument("--line-csv", type=Path, default=DEFAULT_LINE_CSV)
    parser.add_argument("--annotations-csv", type=Path, default=DEFAULT_ANNOTATIONS_CSV)
    parser.add_argument("--notes-json", type=Path, default=DEFAULT_NOTES_JSON)
    parser.add_argument("--sources-json", type=Path, default=DEFAULT_SOURCES_JSON)
    parser.add_argument("--output-html", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    network_rows = load_metric_rows(args.network_csv)
    line_rows = load_metric_rows(args.line_csv)
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
    )
    network_figure = build_network_figure(network_rows, annotations)
    line_figure = build_line_delta_figure(summary.line_deltas)

    html_output = render_html(
        summary,
        network_figure=network_figure,
        line_figure=line_figure,
    )
    markdown_output = render_markdown(summary)

    write_text(args.output_html, html_output)
    write_text(args.output_markdown, markdown_output)
    print(f"Wrote Plotly report to {args.output_html}")
    print(f"Wrote written conclusion to {args.output_markdown}")


if __name__ == "__main__":
    main()
