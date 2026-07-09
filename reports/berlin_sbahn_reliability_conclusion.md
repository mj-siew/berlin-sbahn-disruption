# Berlin S-Bahn Reliability Trend conclusion

Observed VBB monthly trend window: `2023-01` to `2026-05`.

## Answer

The primary VBB KPI evidence points to a mixed trend rather than a clean, one-direction decline. Network punctuality was materially worse in 2025 than in 2023 or 2024 (92.94% versus 93.56% and 93.78%), which supports a real deterioration in day-to-day service quality during 2025. But network reliability did not keep falling across the whole window: 2024 was dragged down by a severe January low at 75.18%, 2025 recovered close to the 2023 full-year level (93.95% versus 94.04%), and the observed 2026 year-to-date window through 2026-05 is stronger on both headline metrics (94.14% punctuality, 94.99% reliability).

## Evidence highlights
- Whole-network punctuality worsened from 93.78% in 2024 to 92.94% in 2025, after a flatter 2023 to 2024 change.
- Whole-network reliability improved from the weak 2024 full-year average of 92.14% to 93.95% in 2025, landing almost back on the 2023 level of 94.04%.
- The largest 2025 punctuality drops versus 2023 were on S7 (-2.69 pp), S1 (-2.05 pp), S3 (-1.88 pp), S25 (-1.59 pp).
- The sharpest 2025 reliability declines versus 2023 were on S5 (-3.12 pp), S47 (-2.05 pp), S3 (-1.76 pp), S1 (-1.45 pp).
- The Tagesspiegel 2025 cross-check is directionally consistent: its Jan-Sep 2025 punctuality figure of 92.9% is only 0.08 percentage points away from the VBB-series average computed from this repo.

## Tagesspiegel cross-check

The external Tagesspiegel punctuality figures line up closely with the VBB monthly series used here.

- [Tagesspiegel: Berliner S-Bahn kommt aus der Krise nicht heraus](https://www.tagesspiegel.de/berlin/zugverspatungen-um-vier-prozent-gestiegen-berliner-s-bahn-kommt-aus-der-krise-nicht-heraus-12853352.html) on `2024-12-12` reported `93.9%` punctuality for `Jan-Sep 2024`; the VBB-series average in this repo is `93.92%` (`+0.02` percentage points).
- [Tagesspiegel: operating situation worsened in 2025](https://www.tagesspiegel.de/berlin/lage-hat-sich-2025-verscharft-135298-zuge-kamen-zu-spat--die-berliner-s-bahn-wird-immer-unzuverlassiger-15087045.html) on `2025-12-30` reported `92.9%` punctuality for `Jan-Sep 2025`; the VBB-series average in this repo is `92.82%` (`-0.08` percentage points).

## Caveats

- The current VBB monthly trend window stops at 2026-05, so 2026 is not yet a full-year comparison.
- The core claim should stay anchored on VBB monthly punctuality and reliability KPIs, not on disruption-count proxies.
- The Tagesspiegel articles are a useful external cross-check for punctuality, but their cancellation shares are not numerically identical to the VBB train-km reliability KPI.
- Pre-2019 archive backfill remains outside the headline charts because compatibility with the current VBB tool is not proven.

## Primary sources

- VBB Berlin S-Bahn quality tool: https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaet-berliner-s-bahn/
- VBB quality archive for older backfill context only: https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaetsbilanzen/
- Repo inputs: `data/vbb_sbahn_monthly_network_trends_2023_2026.csv`, `data/vbb_sbahn_monthly_line_trends_2023_2026.csv`, and `data/vbb_sbahn_event_annotations_2023_2026.csv`.
