# berlin-sbahn-disruption
Analysing train disruption trends in Berlin S-Bahn

## Primary VBB KPI dataset

Build the normalized 2019 onward VBB Berlin S-Bahn KPI dataset:

```powershell
py scripts/build_vbb_sbahn_dataset.py
```

Run the parser tests:

```powershell
py -m pytest
```
