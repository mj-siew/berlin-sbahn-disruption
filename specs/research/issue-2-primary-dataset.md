# Issue #2 primary dataset: VBB S-Bahn quality KPIs

Date: 2026-07-09

## Outcome

The primary dataset for the minimum viable analysis is built from the VBB Berlin S-Bahn quality tool for 2019 onward. The dataset keeps network headline metrics, network sensitivity metrics, and line-level drilldown metrics in one normalized monthly table while preserving comparability labels.

## Extraction method

- Source: https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaet-berliner-s-bahn/
- Builder: `scripts/build_vbb_sbahn_dataset.py`
- Outputs:
  - `data/vbb_sbahn_quality_2019_onward.csv`
  - `data/vbb_sbahn_quality_sources.json`
- Method:
  - fetch the quality tool page
  - read the TYPO3 filter form for available years and months
  - post the same form for each year/month
  - extract network chart values from `data-container-P0`, `data-container-P3`, and `data-container-ZG`
  - extract line-level values from table row `data-*` attributes

The script skips the VBB `Gesamtjahr` month option because the analysis dataset is monthly. Future months or missing chart values represented as `-` are omitted.

## Metric classes

- `primary_headline`: whole-network `punctuality_p3` and `reliability_zg`
- `sensitivity`: whole-network `punctuality_p0`
- `primary_drilldown`: line-level punctuality, reliability, and VBB overall ranking

The headline descriptive trend should use the whole-network `punctuality_p3` and `reliability_zg` series. Line-level values are useful for drilldowns, but they should not replace the network headline series.

## Older archive compatibility

Older VBB archive PDFs and ZIPs are documented at:

https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaetsbilanzen/

Those values are not merged into this primary dataset. Per the issue #1 feasibility audit, pre-2019 material should remain backfill, sensitivity, or context until metric definitions and denominators are proven compatible with the current quality tool.
