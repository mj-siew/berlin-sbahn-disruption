# Berlin S-Bahn Reliability Trend conclusion

Observed VBB monthly trend window: `2019-01` to `2026-05`.

## Answer

The VBB series shows a divergence that a single service-quality score would hide: train-km delivery increased after its preceding annual low, while punctual running remained weaker. 2025 was the weakest complete-year punctuality result in the observed series at 92.94%, while reliability rose from 92.14% in 2024 to 93.95% in 2025. The 2026 Jan-May result is higher than the same months of 2025, but punctuality (94.14%) remains below the same months of 2023 (94.32%).

## Evidence highlights
- Punctuality fell from 93.78% in 2024 to 92.94% in 2025, even as reliability increased by +1.80 pp.
- 6 of 12 months in 2025 were below the explicit 93.0% punctuality reference, versus 3 in 2023 and 4 in 2024.
- The movement is not confined to one published line average: 9/16 lines lost punctuality from 2023 to 2025, while 10/16 improved reliability.
- The observed 2026 Jan-May window is stronger than the same months of 2025 by +0.90 pp on punctuality and +0.92 pp on reliability; it is not a full-year result.

## Personal route: S25 and S26

The route view is a line-level comparison, not a claim about a particular journey.
- S25 Punctuality <= 3:59 late: 90.99% in 2025 (-1.59 pp vs 2023; -1.95 pp vs the network).
- S25 Reliability train-km delivered: 97.78% in 2025 (+0.11 pp vs 2023; +3.83 pp vs the network).
- S26 Punctuality <= 3:59 late: 94.01% in 2025 (-1.24 pp vs 2023; +1.06 pp vs the network).
- S26 Reliability train-km delivered: 90.45% in 2025 (+5.45 pp vs 2023; -3.49 pp vs the network).
- S25 secondary VBB overall score: 94.38% in 2025 (-0.74 pp vs 2023).
- S26 secondary VBB overall score: 92.23% in 2025 (+2.11 pp vs 2023).

## Caveats

- The current VBB monthly trend window stops at 2026-05, so 2026 is not yet a full-year comparison.
- The core claim is anchored on VBB monthly punctuality and reliability KPIs, not disruption-count proxies.
- The 93.0% punctuality reference is a descriptive threshold for counting weak months, not a VBB target or pass/fail standard.
- The VBB overall score in the route view is a secondary comparison only; it does not replace the two primary KPIs.
- The S25/S26 view measures line-level service. It cannot describe the experience of a particular station-to-station trip or identify a causal mechanism.
- Pre-2019 archive backfill remains outside the headline charts because compatibility with the current VBB tool is not proven.

## Primary sources

- VBB Berlin S-Bahn quality tool: https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaet-berliner-s-bahn/
- VBB quality archive for older backfill context only: https://unternehmen.vbb.de/qualitaet-im-oepnv/qualitaetsbilanzen/
- Repo inputs: `data/vbb_sbahn_quality_2019_onward.csv` and `data/vbb_sbahn_event_annotations_2023_2026.csv`.
