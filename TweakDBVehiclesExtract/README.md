# TweakDBVehiclesExtract

Extracts vehicle IDs from a `tweakdb.txt` dump, filters out non-claimable/non-relevant vehicle entries, and reports which vehicles are missing from ClaimVehicles TweakXL YAML files.

## What this script does

The script (`TweakDBVehiclesExtract.py`) performs four steps:

1. Reads `data/tweakdb.txt`.
2. Extracts lines that match strict base vehicle entries in this format:
   - `Vehicle.<name>,<number>`
3. Filters out vehicle names that match a curated exclusion pattern list (`NAME_INCLUDE_PATTERNS`).
4. Compares the filtered list against all YAML files in your ClaimVehicles tweaks directory and outputs the vehicles not yet present there.

## Inputs

- `data/tweakdb.txt`
  - Plain text file containing TweakDB lines.

## Outputs

- `data/tweakdb-vehicles.txt`
  - Filtered list of `Vehicle.*` IDs, one per line.
- `data/missingcars_tweakxl.txt`
  - Vehicle IDs found in `tweakdb-vehicles.txt` but not found in ClaimVehicles YAML files.

## Requirements

- Python 3.10+
- Python packages:
  - `pandas`
  - `tqdm`

Install dependencies:

```powershell
pip install pandas tqdm
```

## Configuration

The script currently uses these path constants:

- `INPUT_FILE = data/tweakdb.txt`
- `OUTPUT_FILE = data/tweakdb-vehicles.txt`
- `MISSING_CARS_OUTPUT_FILE = data/missingcars_tweakxl.txt`
- `CLAIM_VEHICLES_TWEAKS_DIR = F:\_VORTEX_MODS\cyberpunk2077\ClaimVehicles\r6\tweaks\ClaimVehicles`

If your ClaimVehicles folder is somewhere else, update `CLAIM_VEHICLES_TWEAKS_DIR` in `TweakDBVehiclesExtract.py`.

You can also tune filtering behavior by editing `NAME_INCLUDE_PATTERNS`.

## Usage

Run from this folder:

```powershell
python .\TweakDBVehiclesExtract.py
```

The script prints a summary:

- Number of extracted vehicle entries
- Output file location for extracted vehicles
- Number of missing ClaimVehicles entries
- Output file location for missing entries

## Notes

- YAML scanning includes files matching `*.yml` and `*.yaml` in `CLAIM_VEHICLES_TWEAKS_DIR`.
- Vehicle references are detected with the pattern `Vehicle.<alphanumeric_or_underscore>`.
- If required files or directories are missing, the script raises `FileNotFoundError`.
