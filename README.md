# berlin-sbahn-disruption
Analysing train disruption trends in Berlin S-Bahn

## Findings at a glance

The VBB series shows a clear split: reliability recovered after 2024, but punctuality remains the persistent weakness, with 2025 the weakest complete year. On my route, S25 is mainly an on-time problem while S26 is mainly a delivery problem; the charts below show the evidence.

   ![Annual network KPI divergence](reports/assets/annual_network_divergence.svg)

   ![S25 and S26 route comparison](reports/assets/s25_s26_route_comparison.svg)

[Read or download the full offline HTML report](reports/berlin_sbahn_reliability_trend.html) for the monthly network trend, event legend, line comparisons, and route scorecard.

## Primary VBB KPI dataset

Build the normalized 2019 onward VBB Berlin S-Bahn KPI dataset:

```powershell
py scripts/build_vbb_sbahn_dataset.py
```

Build the curated event-annotation layer for chart markers and source-backed caveats:

```powershell
py scripts/build_vbb_sbahn_event_annotations.py
```

Build the final shareable HTML report and written conclusion:

```powershell
py scripts/build_final_report.py
```

Each script prints the directory and filename of every output when it finishes.

Run the parser tests:

```powershell
py -m pytest
```
