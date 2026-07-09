from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ANALYSIS_WINDOW_START = "2023-01"
ANALYSIS_WINDOW_END = "2026-12"

DEFAULT_OUTPUT_CSV = Path("data/vbb_sbahn_event_annotations_2023_2026.csv")
DEFAULT_OUTPUT_JSON = Path("data/vbb_sbahn_event_annotation_sources_2023_2026.json")

ANNOTATION_FIELDS = [
    "event_id",
    "event_family",
    "context_type",
    "event_title",
    "annotation_kind",
    "start_date",
    "end_date",
    "start_period",
    "end_period",
    "chart_date",
    "impact_scope",
    "affected_lines",
    "confidence_level",
    "chart_label",
    "summary",
    "context_note",
    "causal_caveat",
    "source_count",
]

FAMILY_NOTES = {
    "wollankstrasse_closure": (
        "Planned disruption context from bridge works around S Wollankstrasse."
    ),
    "signal_or_stellwerk_failure": (
        "Operational disruption context from signal, signal-box, or staffing failures."
    ),
    "cable_theft": "Operational disruption context from vandalism or cable theft.",
}


@dataclass(frozen=True)
class SourceReference:
    title: str
    url: str
    publisher: str
    published_date: str
    note: str


@dataclass(frozen=True)
class EventAnnotation:
    event_id: str
    event_family: str
    context_type: str
    event_title: str
    annotation_kind: str
    start_date: str
    end_date: str
    impact_scope: str
    affected_lines: tuple[str, ...]
    confidence_level: str
    chart_label: str
    summary: str
    context_note: str
    causal_caveat: str
    sources: tuple[SourceReference, ...]


CURATED_ANNOTATIONS: tuple[EventAnnotation, ...] = (
    EventAnnotation(
        event_id="cable_theft_landsberger_allee_2024_12",
        event_family="cable_theft",
        context_type="operational_incident_context",
        event_title="Cable theft disrupts Ring and radial services near Landsberger Allee",
        annotation_kind="point",
        start_date="2024-12-13",
        end_date="2024-12-13",
        impact_scope="ring_east",
        affected_lines=("S41", "S42", "S8", "S85"),
        confidence_level="high",
        chart_label="Cable theft: Landsberger Allee",
        summary=(
            "Cable theft forced a shuttle segment between Landsberger Allee and "
            "Frankfurter Allee and suspended the S85."
        ),
        context_note=(
            "Useful context for a sharp single-day service shock on the eastern Ring "
            "corridor in December 2024."
        ),
        causal_caveat=(
            "The event is well evidenced but short-lived, so it is only local context "
            "unless a December monthly KPI change is also visible in the primary series."
        ),
        sources=(
            SourceReference(
                title=(
                    "Beendet: S-Bahn-Pendelverkehr zwischen Landsberger Allee und "
                    "Frankfurter Allee"
                ),
                url=(
                    "https://viz.berlin.de/aktuelle-meldungen/aktuell-zugverkehr-s41-"
                    "s42-s8-und-s85-zwischen-landsberger-allee-und-frankfurter-allee-"
                    "unterbrochen/"
                ),
                publisher="VIZ Berlin",
                published_date="2024-12-13",
                note=(
                    "Archived disruption notice naming cable theft and affected lines."
                ),
            ),
        ),
    ),
    EventAnnotation(
        event_id="wollankstrasse_full_closure_2025_03",
        event_family="wollankstrasse_closure",
        context_type="planned_disruption_context",
        event_title="Full Wollankstrasse bridge-work closure in March 2025",
        annotation_kind="range",
        start_date="2025-03-03",
        end_date="2025-03-28",
        impact_scope="north_south_north",
        affected_lines=("S1", "S8", "S25", "S26", "S85"),
        confidence_level="high",
        chart_label="Wollankstrasse full closure",
        summary=(
            "Bridge-replacement work around S Wollankstrasse rerouted multiple north-south "
            "services through most of March 2025."
        ),
        context_note=(
            "This is strong planned disruption context for the northern north-south "
            "corridor during March 2025."
        ),
        causal_caveat=(
            "The closure clearly changed operations locally, but it should annotate the "
            "chart rather than be treated as proof of a network-wide KPI change."
        ),
        sources=(
            SourceReference(
                title="Vollsperrung der Wollankstrasse in Hoehe S-Bahnhof",
                url=(
                    "https://viz.berlin.de/aktuelle-meldungen/neubau-der-bruecke-"
                    "uber-die-wollankstrasse/"
                ),
                publisher="VIZ Berlin",
                published_date="2025-03-03",
                note=(
                    "Official Berlin traffic notice with exact road-closure window and "
                    "S-Bahn rerouting summary."
                ),
            ),
        ),
    ),
    EventAnnotation(
        event_id="cable_theft_humboldthain_2025_04",
        event_family="cable_theft",
        context_type="operational_incident_context",
        event_title="Cable theft near Humboldthain interrupts the north-south corridor",
        annotation_kind="range",
        start_date="2025-04-25",
        end_date="2025-04-27",
        impact_scope="north_south_centre_north",
        affected_lines=("S1", "S2", "S25", "S26", "S85"),
        confidence_level="high",
        chart_label="Cable theft: Humboldthain",
        summary=(
            "Unknown offenders cut and partly stole cables near Humboldthain, interrupting "
            "traffic between Nordbahnhof and Gesundbrunnen."
        ),
        context_note=(
            "This is a directly evidenced cable-theft event on the north-south trunk late "
            "in April 2025."
        ),
        causal_caveat=(
            "This event is appropriate as chart context, but any monthly interpretation "
            "should note that a separate Stellwerk defect was also reported in the same "
            "corridor on April 26."
        ),
        sources=(
            SourceReference(
                title=(
                    "Beeintraechtigung durch Vandalismus (Kabeldiebstahl) im Bereich "
                    "Humboldthain bis 27.04.25"
                ),
                url=(
                    "https://viz.berlin.de/aktuelle-meldungen/"
                    "beeintrachtigung-durch-vandalismus-kabeldiebstahl-im-bereich-"
                    "humboldthain/"
                ),
                publisher="VIZ Berlin",
                published_date="2025-04-25",
                note=(
                    "Official disruption notice with affected lines and repair horizon."
                ),
            ),
            SourceReference(
                title=(
                    "Stellwerkstoerung fuehrt weiter zu Einschraenkungen bei der S-Bahn"
                ),
                url=(
                    "https://www.rbb24.de/panorama/beitrag/2025/04/berlin-s-bahn-"
                    "kabeldiebstahl-behoben-stellwerkstoerung-verkehr-einschraenkungen.html"
                ),
                publisher="rbb24",
                published_date="2025-04-26",
                note=(
                    "Follow-up report confirming the cable damage and its overlap with a "
                    "separate Stellwerk problem."
                ),
            ),
        ),
    ),
    EventAnnotation(
        event_id="stellwerk_gesundbrunnen_2025_04",
        event_family="signal_or_stellwerk_failure",
        context_type="operational_incident_context",
        event_title="Stellwerk defect at Gesundbrunnen after the Humboldthain disruption",
        annotation_kind="point",
        start_date="2025-04-26",
        end_date="2025-04-26",
        impact_scope="north_south_centre_north",
        affected_lines=("S1", "S2", "S25", "S26"),
        confidence_level="medium",
        chart_label="Stellwerk defect: Gesundbrunnen",
        summary=(
            "A reported Stellwerk defect around Gesundbrunnen continued to disrupt the "
            "north-south corridor on April 26, 2025."
        ),
        context_note=(
            "This event shows that short operational failures can compound corridor stress "
            "even after a cable-theft repair."
        ),
        causal_caveat=(
            "Treat this as weaker monthly context because it was short-lived and overlapped "
            "with the nearby Humboldthain cable-damage event."
        ),
        sources=(
            SourceReference(
                title=(
                    "Stellwerkstoerung fuehrt weiter zu Einschraenkungen bei der S-Bahn"
                ),
                url=(
                    "https://www.rbb24.de/panorama/beitrag/2025/04/berlin-s-bahn-"
                    "kabeldiebstahl-behoben-stellwerkstoerung-verkehr-einschraenkungen.html"
                ),
                publisher="rbb24",
                published_date="2025-04-26",
                note=(
                    "Report citing a Stellwerk defect in the Gesundbrunnen area."
                ),
            ),
        ),
    ),
    EventAnnotation(
        event_id="wollankstrasse_pfingsten_2025_06",
        event_family="wollankstrasse_closure",
        context_type="planned_disruption_context",
        event_title="Pfingsten Wollankstrasse works interrupt the S1 corridor",
        annotation_kind="range",
        start_date="2025-06-06",
        end_date="2025-06-11",
        impact_scope="north_south_north",
        affected_lines=("S1", "S8", "S25", "S26", "S85"),
        confidence_level="high",
        chart_label="Wollankstrasse Pfingsten works",
        summary=(
            "Bridge and track work over the Pfingsten weekend interrupted the S1 and "
            "reduced corridor frequency around Wollankstrasse."
        ),
        context_note=(
            "This is a second strong planned-disruption marker for the same corridor in "
            "June 2025."
        ),
        causal_caveat=(
            "Useful timeline context for June 2025, but still explanatory rather than "
            "causal evidence for any KPI inflection."
        ),
        sources=(
            SourceReference(
                title=(
                    "Brueckenbaustelle Wollankstrasse beeinflusst S-Bahnverkehr ueber "
                    "Pfingsten"
                ),
                url=(
                    "https://sbahn.berlin/das-unternehmen/presse/"
                    "pressemitteilungen-pressearchiv/pressemitteilungen/"
                    "brueckenbaustelle-wollankstrasse-beeinflusst-s-bahnverkehr-"
                    "ueber-pfingsten/"
                ),
                publisher="S-Bahn Berlin",
                published_date="2025-05-27",
                note=(
                    "Official press release with exact service window and affected lines."
                ),
            ),
        ),
    ),
    EventAnnotation(
        event_id="stellwerk_schoeneweide_personalausfall_2025_07",
        event_family="signal_or_stellwerk_failure",
        context_type="operational_incident_context",
        event_title="Staffing failure at the Schoeneweide signal box disrupts the southeast",
        annotation_kind="range",
        start_date="2025-07-19",
        end_date="2025-07-20",
        impact_scope="southeast",
        affected_lines=("S45", "S46", "S47", "S8", "S85", "S9"),
        confidence_level="high",
        chart_label="Schoeneweide Stellwerk outage",
        summary=(
            "A sickness-related staffing failure left the Schoeneweide Stellwerk "
            "unoccupied for much of the weekend, forcing bus replacement and a shuttle."
        ),
        context_note=(
            "This is a well-documented southeast corridor disruption tied to a manually "
            "staffed Stellwerk."
        ),
        causal_caveat=(
            "The event is meaningful operational context, but its root cause was a local "
            "staffing shortage rather than a proven infrastructure defect trend."
        ),
        sources=(
            SourceReference(
                title=(
                    "S-Bahn-Linien im Berliner Suedosten fahren nach Personalmangel im "
                    "Stellwerk wieder"
                ),
                url=(
                    "https://www.rbb24.de/panorama/beitrag/2025/07/s-bahn-berlin-"
                    "plaenterwald-baumschulenweg-schoeneweide-unterbrochen.html"
                ),
                publisher="rbb24",
                published_date="2025-07-20",
                note=(
                    "Contemporary report with dates, affected lines, and operator quote."
                ),
            ),
            SourceReference(
                title=(
                    "Warum Stellwerke so sensibel fuer den Berliner S-Bahn-Betrieb sind"
                ),
                url=(
                    "https://www.rbb24.de/panorama/beitrag/2025/07/stellwerk-berlin-"
                    "sbahn-personal-ausfall-verkehr-bahn.html"
                ),
                publisher="rbb24",
                published_date="2025-07-21",
                note=(
                    "Explainer confirming the southeast corridor still depended on "
                    "manually staffed Stellwerke in 2025."
                ),
            ),
        ),
    ),
    EventAnnotation(
        event_id="stellwerk_schoeneweide_personalausfall_2025_08",
        event_family="signal_or_stellwerk_failure",
        context_type="operational_incident_context",
        event_title="Repeat Schoeneweide signal-box staffing outage in August 2025",
        annotation_kind="point",
        start_date="2025-08-03",
        end_date="2025-08-03",
        impact_scope="southeast",
        affected_lines=("S41", "S42", "S45", "S46", "S47", "S8"),
        confidence_level="medium",
        chart_label="Repeat Schoeneweide outage",
        summary=(
            "A second short-notice staffing failure at the Schoeneweide Stellwerk caused "
            "renewed southeast and Ring-related disruption."
        ),
        context_note=(
            "This repeated outage strengthens the case that Schoeneweide was an important "
            "fragility point during summer 2025."
        ),
        causal_caveat=(
            "This is plausible context for August 2025, but it remains a short single-day "
            "event and should not be over-read without corroborating KPI movement."
        ),
        sources=(
            SourceReference(
                title=(
                    "Berliner S-Bahn gestoert: Stellwerk in Schoeneweide faellt erneut "
                    "wegen Personalmangel aus"
                ),
                url=(
                    "https://www.rbb24.de/panorama/beitrag/2025/08/berlin-stoerung-"
                    "sbahn-stellwerk-schoeneweide-personalausfall.html"
                ),
                publisher="rbb24",
                published_date="2025-08-03",
                note=(
                    "Report documenting the repeat outage and affected lines."
                ),
            ),
        ),
    ),
    EventAnnotation(
        event_id="cable_theft_baumschulenweg_2026_05",
        event_family="cable_theft",
        context_type="operational_incident_context",
        event_title="Cable theft at Baumschulenweg disrupts southeast services",
        annotation_kind="range",
        start_date="2026-05-19",
        end_date="2026-05-20",
        impact_scope="southeast",
        affected_lines=("S46", "S47", "S8", "S85", "S9"),
        confidence_level="high",
        chart_label="Cable theft: Baumschulenweg",
        summary=(
            "Cable theft at Baumschulenweg caused a multi-line southeast disruption that "
            "lasted from Tuesday morning until repairs finished on Wednesday."
        ),
        context_note=(
            "This is one of the clearer cable-theft markers in the 2026 trend window."
        ),
        causal_caveat=(
            "The event is well evidenced and lasted into a second day, but it still "
            "belongs in the exploratory annotation layer rather than as standalone proof "
            "of a monthly KPI shift."
        ),
        sources=(
            SourceReference(
                title=(
                    "Kriminalitaet: Kabeldiebstahl in Treptow - Stoerungen bei der S-Bahn"
                ),
                url=(
                    "https://www.tagesspiegel.de/berlin/kriminalitat-kabeldiebstahl-in-"
                    "treptow-storungen-bei-der-s-bahn-15610269.html"
                ),
                publisher="Tagesspiegel / dpa",
                published_date="2026-05-19",
                note=(
                    "Early report placing the disruption in the Tuesday-morning commute."
                ),
            ),
            SourceReference(
                title=(
                    "Nach einem Kabeldiebstahl fahren S-Bahnen wieder planmaessig"
                ),
                url=(
                    "https://www.rbb24.de/panorama/beitrag/2026/05/"
                    "kabeldiebstahl-berlin-sbahn-baumschulenweg-einschraenkungen.html"
                ),
                publisher="rbb24",
                published_date="2026-05-20",
                note=(
                    "Follow-up report confirming restoration by Wednesday midday."
                ),
            ),
        ),
    ),
)


def period_from_date(value: str) -> str:
    return value[:7]


def sort_annotations(
    annotations: tuple[EventAnnotation, ...] | list[EventAnnotation],
) -> list[EventAnnotation]:
    return sorted(
        annotations,
        key=lambda annotation: (annotation.start_date, annotation.end_date, annotation.event_id),
    )


def build_annotation_rows(
    annotations: tuple[EventAnnotation, ...] | list[EventAnnotation],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for annotation in sort_annotations(annotations):
        rows.append(
            {
                "event_id": annotation.event_id,
                "event_family": annotation.event_family,
                "context_type": annotation.context_type,
                "event_title": annotation.event_title,
                "annotation_kind": annotation.annotation_kind,
                "start_date": annotation.start_date,
                "end_date": annotation.end_date,
                "start_period": period_from_date(annotation.start_date),
                "end_period": period_from_date(annotation.end_date),
                "chart_date": annotation.start_date,
                "impact_scope": annotation.impact_scope,
                "affected_lines": ",".join(annotation.affected_lines),
                "confidence_level": annotation.confidence_level,
                "chart_label": annotation.chart_label,
                "summary": annotation.summary,
                "context_note": annotation.context_note,
                "causal_caveat": annotation.causal_caveat,
                "source_count": len(annotation.sources),
            }
        )
    return rows


def build_annotation_metadata(
    annotations: tuple[EventAnnotation, ...] | list[EventAnnotation],
    *,
    generated_at: str,
    analysis_window_start: str,
    analysis_window_end: str,
) -> dict[str, object]:
    rows_by_id = {row["event_id"]: row for row in build_annotation_rows(annotations)}
    events: list[dict[str, object]] = []
    for annotation in sort_annotations(annotations):
        event = dict(rows_by_id[annotation.event_id])
        event["sources"] = [asdict(source) for source in annotation.sources]
        events.append(event)

    return {
        "generated_at": generated_at,
        "analysis_window": {
            "start_period": analysis_window_start,
            "end_period": analysis_window_end,
        },
        "columns": ANNOTATION_FIELDS,
        "event_count": len(events),
        "family_notes": FAMILY_NOTES,
        "events": events,
        "notes": [
            "Annotations are interpretive context for KPI charts, not a replacement for the VBB primary evidence layer.",
            "Confidence levels reflect source quality and date precision, not proof of causal impact on monthly KPI values.",
            "Short incidents can be meaningful chart markers while still being too weak to explain a monthly network trend on their own.",
        ],
    }


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(payload: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the curated Berlin S-Bahn event annotation dataset."
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
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
    rows = build_annotation_rows(CURATED_ANNOTATIONS)
    metadata = build_annotation_metadata(
        CURATED_ANNOTATIONS,
        generated_at=generated_at,
        analysis_window_start=ANALYSIS_WINDOW_START,
        analysis_window_end=ANALYSIS_WINDOW_END,
    )
    write_csv(rows, args.output_csv)
    write_json(metadata, args.output_json)
    print(f"Wrote {len(rows)} annotation rows to {args.output_csv}")
    print(f"Wrote annotation source metadata to {args.output_json}")


if __name__ == "__main__":
    main()
