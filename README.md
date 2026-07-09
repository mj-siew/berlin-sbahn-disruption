# berlin-sbahn-disruption
Analysing train disruption trends in Berlin S-Bahn

## Primary VBB KPI dataset

Build the normalized 2019 onward VBB Berlin S-Bahn KPI dataset:

```powershell
py scripts/build_vbb_sbahn_dataset.py
```

This also writes chart-ready monthly trend views for 2023-2026:

- `data/vbb_sbahn_monthly_network_trends_2023_2026.csv`
- `data/vbb_sbahn_monthly_line_trends_2023_2026.csv`
- `data/vbb_sbahn_monthly_trend_notes_2023_2026.json`

Build the curated event-annotation layer for chart markers and source-backed caveats:

```powershell
py scripts/build_vbb_sbahn_event_annotations.py
```

This writes:

- `data/vbb_sbahn_event_annotations_2023_2026.csv`
- `data/vbb_sbahn_event_annotation_sources_2023_2026.json`

Build the Tagesspiegel 2025 comparison note that cross-checks external reporting against
the repo's KPI definitions:

```powershell
py scripts/build_vbb_sbahn_tagesspiegel_crosscheck.py
```

This writes:

- `data/vbb_sbahn_tagesspiegel_crosscheck_2025.json`

Run the parser tests:

```powershell
py -m pytest
```
