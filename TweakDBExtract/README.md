# TweakDB Extractors

Utilities for extracting record names from a Cyberpunk 2077 `tweakdb.txt` dump. Both scripts expect the dump at `data/tweakdb.txt` relative to this folder.

## Requirements

- Python 3.10+
- Python packages: `pandas`, `tqdm`

Install dependencies with:

```powershell
pip install pandas tqdm
```

## TweakDBExtract.py

Extracts records matching a base pattern. It accepts an optional pattern argument, removes names matching the configured exclusion patterns, and writes one record name per line.

Run from this folder:

```powershell
python .\TweakDBExtract.py
python .\TweakDBExtract.py BaseStatusEffect
```

The default base pattern is `BaseStatusEffect`. The output is written to a sanitized filename under `data`, for example:

- `data/tweakdb-BaseStatusEffect.txt`

The matching format is `<base_pattern>.<name>,<number>`. Edit `NAME_EXCLUDE_PATTERNS` in `TweakDBExtract.py` to change filtering.

## TweakDBVehiclesExtract.py

Extracts strict `Vehicle.<name>,<number>` entries, removes non-claimable or irrelevant vehicle names using its configured exclusion list, and compares the result with ClaimVehicles TweakXL YAML files.

Run from this folder:

```powershell
python .\TweakDBVehiclesExtract.py
```

Outputs:

- `data/tweakdb-Vehicles.txt` - filtered vehicle IDs.
- `data/missingcars_tweakxl.txt` - vehicles in the dump that are absent from ClaimVehicles YAML files, formatted as TweakXL `!append` entries.
- `data/missingcars_tweakxl_to_delete.txt` - vehicles present in ClaimVehicles YAML files but absent from the dump, grouped by source YAML file.

The ClaimVehicles directory is currently configured as:

```text
F:\_VORTEX_MODS\cyberpunk2077\ClaimVehicles\r6\tweaks\ClaimVehicles
```

Update `CLAIM_VEHICLES_TWEAKS_DIR` in `TweakDBVehiclesExtract.py` if the directory is elsewhere. YAML scanning includes both `*.yml` and `*.yaml` files.

## Common Notes

- Both scripts raise `FileNotFoundError` when required input files or directories are missing.
- Outputs are regenerated each time the corresponding script runs.
- The scripts use Windows paths for the local mod workspace.
