from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://unternehmen.vbb.de"
DEFAULT_SOURCE_URL = (
    "https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaet-berliner-s-bahn/"
)
ARCHIVE_URL = "https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaetsbilanzen/"
FORM_PREFIX = "tx_sbahnqualitaet_sbahnoverview"
USER_AGENT = "berlin-sbahn-disruption dataset builder"

CSV_FIELDS = [
    "period",
    "year",
    "month",
    "entity_scope",
    "entity_id",
    "metric_id",
    "value_percent",
    "comparability_class",
    "source_artifact",
    "source_url",
    "extracted_at",
    "notes",
]

LINE_TITLE_RE = re.compile(
    r"Linie\s+(?P<line>.+?)\s+Jahr:\s+(?P<year>\d{4}),\s+Monat\s+(?P<month>\d{1,2})",
    re.DOTALL,
)


@dataclass(frozen=True)
class FilterConfig:
    action_url: str
    hidden_fields: dict[str, str]
    years: list[int]
    months: list[int]


@dataclass(frozen=True)
class KpiRow:
    period: str
    year: int
    month: int
    entity_scope: str
    entity_id: str
    metric_id: str
    value_percent: str
    comparability_class: str
    source_artifact: str
    source_url: str
    extracted_at: str
    notes: str


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def post_filter(
    session: requests.Session,
    config: FilterConfig,
    *,
    year: int,
    month: int | None = None,
) -> str:
    payload = dict(config.hidden_fields)
    payload[f"{FORM_PREFIX}[search]"] = ""
    payload[f"{FORM_PREFIX}[jsSelect]"] = "overallranking"
    payload[f"{FORM_PREFIX}[year]"] = str(year)
    if month is not None:
        payload[f"{FORM_PREFIX}[month]"] = str(month)
    payload[f"{FORM_PREFIX}[operator]"] = ""
    payload[f"{FORM_PREFIX}[contract]"] = ""

    response = session.post(config.action_url, data=payload, timeout=30)
    response.raise_for_status()
    return response.text


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def parse_filter_config(html: str, source_url: str = DEFAULT_SOURCE_URL) -> FilterConfig:
    soup = soup_from_html(html)
    form = soup.find("form", id="rqfilterform")
    if form is None:
        raise ValueError("Could not find VBB S-Bahn filter form")

    action = form.get("action")
    if not action:
        raise ValueError("VBB S-Bahn filter form has no action URL")

    hidden_fields = {
        field["name"]: field.get("value", "")
        for field in form.find_all("input", attrs={"type": "hidden"})
        if field.get("name")
    }

    years = parse_integer_options(form.find("select", id="year"))
    months = parse_integer_options(form.find("select", id="month"))
    if not years:
        raise ValueError("Could not find available years in VBB filter form")

    return FilterConfig(
        action_url=urljoin(source_url, action),
        hidden_fields=hidden_fields,
        years=years,
        months=months,
    )


def parse_integer_options(select_tag) -> list[int]:
    if select_tag is None:
        return []

    values: list[int] = []
    for option in select_tag.find_all("option"):
        raw_value = option.get("value", "").strip()
        if raw_value.isdigit():
            values.append(int(raw_value))
    return values


def parse_network_rows(
    soup: BeautifulSoup,
    *,
    year: int,
    months: Iterable[int],
    extracted_at: str,
    source_url: str = DEFAULT_SOURCE_URL,
) -> list[KpiRow]:
    rows: list[KpiRow] = []
    containers = [
        (
            "data-container-P0",
            "punctuality",
            "punctuality_p0",
            "sensitivity",
            "Network punctuality, arrivals no more than 0:59 minutes late.",
        ),
        (
            "data-container-P3",
            "punctuality",
            "punctuality_p3",
            "primary_headline",
            "Network punctuality, arrivals no more than 3:59 minutes late.",
        ),
        (
            "data-container-ZG",
            "reliability",
            "reliability_zg",
            "primary_headline",
            "Network reliability, delivered train-km over scheduled train-km.",
        ),
    ]

    for element_id, series_key, metric_id, comparability_class, notes in containers:
        container = soup.find(id=element_id)
        if container is None:
            raise ValueError(f"Could not find network data container {element_id}")

        dataset = json.loads(container.get("data-dataset", "{}"))
        series = dataset.get(series_key)
        if not isinstance(series, list):
            raise ValueError(f"Network container {element_id} has no {series_key} series")

        for month in sorted(months):
            if month == 13:
                continue
            index = month - 1
            if index < 0 or index >= len(series):
                continue
            value = normalize_percent(series[index])
            if value is None:
                continue
            rows.append(
                make_row(
                    year=year,
                    month=month,
                    entity_scope="network",
                    entity_id="Gesamtnetz",
                    metric_id=metric_id,
                    value_percent=value,
                    comparability_class=comparability_class,
                    extracted_at=extracted_at,
                    source_url=source_url,
                    notes=notes,
                )
            )

    return rows


def parse_line_rows(
    soup: BeautifulSoup,
    *,
    extracted_at: str,
    source_url: str = DEFAULT_SOURCE_URL,
) -> list[KpiRow]:
    rows: list[KpiRow] = []
    metrics = [
        (
            "data-overallranking",
            "overall_ranking",
            "Line overall score published by VBB for comparison.",
        ),
        (
            "data-punctuality",
            "punctuality_p3",
            "Line punctuality, arrivals no more than 3:59 minutes late.",
        ),
        (
            "data-reliability",
            "reliability_zg",
            "Line reliability, delivered train-km over scheduled train-km.",
        ),
    ]

    for form in soup.select("form.tablerow"):
        title = form.get("title", "")
        match = LINE_TITLE_RE.search(title)
        if match is None:
            continue

        line = match.group("line").strip()
        year = int(match.group("year"))
        month = int(match.group("month"))
        if month == 13:
            continue

        for attr_name, metric_id, notes in metrics:
            value = normalize_percent(form.get(attr_name))
            if value is None:
                continue
            rows.append(
                make_row(
                    year=year,
                    month=month,
                    entity_scope="line",
                    entity_id=line,
                    metric_id=metric_id,
                    value_percent=value,
                    comparability_class="primary_drilldown",
                    extracted_at=extracted_at,
                    source_url=source_url,
                    notes=notes,
                )
            )

    return rows


def normalize_percent(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip().replace(",", ".")
    if not text or text == "-":
        return None

    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Could not parse percentage value {value!r}") from exc

    return f"{number.quantize(Decimal('0.01'))}"


def make_row(
    *,
    year: int,
    month: int,
    entity_scope: str,
    entity_id: str,
    metric_id: str,
    value_percent: str,
    comparability_class: str,
    extracted_at: str,
    source_url: str,
    notes: str,
) -> KpiRow:
    return KpiRow(
        period=f"{year}-{month:02d}",
        year=year,
        month=month,
        entity_scope=entity_scope,
        entity_id=entity_id,
        metric_id=metric_id,
        value_percent=value_percent,
        comparability_class=comparability_class,
        source_artifact="VBB Berlin S-Bahn quality tool",
        source_url=source_url,
        extracted_at=extracted_at,
        notes=notes,
    )


def sort_rows(rows: Iterable[KpiRow]) -> list[KpiRow]:
    scope_order = {"network": 0, "line": 1}
    metric_order = {
        "punctuality_p3": 0,
        "reliability_zg": 1,
        "punctuality_p0": 2,
        "overall_ranking": 3,
    }
    return sorted(
        rows,
        key=lambda row: (
            row.period,
            scope_order.get(row.entity_scope, 99),
            row.entity_id,
            metric_order.get(row.metric_id, 99),
        ),
    )


def build_dataset(source_url: str = DEFAULT_SOURCE_URL) -> tuple[list[KpiRow], dict[str, object]]:
    extracted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    initial_html = fetch_html(session, source_url)
    config = parse_filter_config(initial_html, source_url=source_url)
    rows: list[KpiRow] = []
    discovered_months: dict[int, list[int]] = {}

    for year in sorted(config.years):
        year_html = post_filter(session, config, year=year)
        year_soup = soup_from_html(year_html)
        year_config = parse_filter_config(year_html, source_url=source_url)
        months = sorted(month for month in year_config.months if 1 <= month <= 12)
        discovered_months[year] = months
        rows.extend(
            parse_network_rows(
                year_soup,
                year=year,
                months=months,
                extracted_at=extracted_at,
                source_url=source_url,
            )
        )

        for month in months:
            month_html = post_filter(session, config, year=year, month=month)
            month_soup = soup_from_html(month_html)
            rows.extend(
                parse_line_rows(
                    month_soup,
                    extracted_at=extracted_at,
                    source_url=source_url,
                )
            )

    sorted_rows = sort_rows(rows)
    metadata = build_metadata(
        rows=sorted_rows,
        extracted_at=extracted_at,
        years=sorted(config.years),
        months_by_year=discovered_months,
        source_url=source_url,
    )
    return sorted_rows, metadata


def build_metadata(
    *,
    rows: list[KpiRow],
    extracted_at: str,
    years: list[int],
    months_by_year: dict[int, list[int]],
    source_url: str,
) -> dict[str, object]:
    return {
        "generated_at": extracted_at,
        "source_urls": {
            "primary_quality_tool": source_url,
            "quality_archive": ARCHIVE_URL,
        },
        "row_count": len(rows),
        "columns": CSV_FIELDS,
        "years": years,
        "months_by_year": {str(year): months for year, months in months_by_year.items()},
        "source_artifacts": [
            {
                "name": "VBB Berlin S-Bahn quality tool",
                "role": "primary evidence layer for 2019 onward monthly KPI values",
                "access_method": "TYPO3 filter form plus embedded chart and table attributes",
            },
            {
                "name": "VBB quality archive",
                "role": "older backfill or sensitivity source only; not merged into this dataset",
                "access_method": "PDF and ZIP links on the VBB quality archive page",
            },
        ],
        "metric_definitions": {
            "punctuality_p3": "Share of arrivals no more than 3:59 minutes late.",
            "punctuality_p0": "Share of arrivals no more than 0:59 minutes late.",
            "reliability_zg": "Delivered train-km divided by scheduled train-km on the day-current timetable.",
            "overall_ranking": "VBB line comparison score combining punctuality and reliability.",
        },
        "notes": [
            "Month option 13, Gesamtjahr, is intentionally skipped to keep this file monthly.",
            "Future or unavailable months represented by '-' in the VBB chart data are omitted.",
            "Network punctuality_p3 and reliability_zg are the headline primary evidence series.",
            "Line values are drilldown evidence and should not replace the network headline series.",
        ],
    }


def write_csv(rows: Iterable[KpiRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(payload: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the VBB Berlin S-Bahn primary KPI dataset."
    )
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/vbb_sbahn_quality_2019_onward.csv"),
    )
    parser.add_argument(
        "--metadata-json",
        type=Path,
        default=Path("data/vbb_sbahn_quality_sources.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, metadata = build_dataset(source_url=args.source_url)
    write_csv(rows, args.output_csv)
    write_json(metadata, args.metadata_json)
    print(f"Wrote {len(rows)} rows to {args.output_csv}")
    print(f"Wrote source metadata to {args.metadata_json}")


if __name__ == "__main__":
    main()
