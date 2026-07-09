# Issue #4 event annotations: infrastructure and operational context

Date: 2026-07-09

## Outcome

The repo now includes a curated annotation dataset for infrastructure and operational events that can help interpret the Berlin S-Bahn KPI trend charts without turning those events into a second primary metric.

Outputs:

- `data/vbb_sbahn_event_annotations_2023_2026.csv`
- `data/vbb_sbahn_event_annotation_sources_2023_2026.json`
- `scripts/build_vbb_sbahn_event_annotations.py`

The annotation layer stays inside the exploratory layer defined by the repo context and ADR. It is intended for chart markers, hover notes, and narrative caveats.

## Event families covered

- Wollankstrasse bridge-work closures
- signal or Stellwerk failures
- cable-theft incidents

## Selection logic

The selected events are not meant to be exhaustive. They are the strongest clearly dated examples I could verify quickly from public sources in the 2024-2026 analysis window, with emphasis on:

- exact dates or date ranges
- operator, public-traffic, or high-trust local news sourcing
- direct evidence of service disruption
- usefulness as timeline context for monthly KPI charts

## Evidence posture

These annotations should be presented as interpretive context only.

- A planned closure or incident can explain why a chart segment deserves attention.
- It does not prove that a network-wide KPI change was caused by that event.
- Short incidents are especially weak as monthly explanations unless the KPI movement is also visible in the primary VBB series.

## Notable caveats

- The April 2025 Gesundbrunnen Stellwerk fault overlaps with the Humboldthain cable-theft corridor disruption, so it should be read as compounded context rather than a clean standalone cause.
- The July and August 2025 Schoeneweide Stellwerk events are operationally important, but the reporting points to staffing fragility at manually staffed signal boxes rather than proving a broader infrastructure trend by themselves.
- The Wollankstrasse entries are strong planned-disruption markers for the northern north-south corridor, but they remain local explanatory context unless the primary KPI series shows a matching monthly inflection.

## Source mix

The dataset uses a mix of:

- VIZ Berlin disruption notices for dated public traffic notices
- S-Bahn Berlin press material for planned works
- rbb24 reporting for operational incidents and follow-up confirmation
- one Tagesspiegel / dpa item to pin the start of the Baumschulenweg cable-theft disruption

This mix gives reasonably auditable chart annotations while preserving the repo's distinction between the primary evidence layer and contextual evidence.
