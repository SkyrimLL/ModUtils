# DeployModFiles

`deployModFiles.py` is a local deployment utility for mod development workflows.

It reads one YAML config file that points to one or more JSON manifests, then:

- Copies matching files from each mod `source_folder`.
- Deploys files to up to two destinations per mod:
  - `release_folder`
  - `github_folder`
- Optionally creates dated `.7z` archives from an `archive_folder`.

This is useful for keeping release-ready folders and source-control folders in sync from your active mod workspace.

## Script Location

- `DeployModFiles/deployModFiles.py`

## Requirements

- Python 3.9+
- Python packages:
  - `PyYAML`
  - `colorama`
  - `py7zr`

Install dependencies:

```powershell
pip install pyyaml colorama py7zr
```

## How It Works

At runtime, the script loads:

- `DeployModFiles/data/config.yaml`

For each enabled group and enabled manifest in that YAML file, it loads the manifest JSON and deploys all enabled mods.

Each mod entry can:

- Copy selected files/patterns from source to release and/or github targets.
- Skip deployment by setting `mode` to `skip`.
- Optionally archive files from `archive_folder` into a dated `.7z` file.

## Configuration Files

### 1) Global config (YAML)

File used by default:

- `data/config.yaml`

Example shape:

```yaml
manifest_groups:
  - name: "Cyberpunk 2077"
    status: true
    manifests:
      - file: "mods_manifest_cyberpunk_2077.json"
        status: true
```

Notes:

- Group `status: false` means the whole group is skipped.
- Manifest `status: false` means that manifest is skipped.
- `file` is resolved from the `data` folder. Use filenames like `mods_manifest_xxx.json`.

### 2) Manifest files (JSON)

Example files:

- `data/mods_manifest_cyberpunk_2077.json`
- `data/mods_manifest_sample.json`

Required root key:

- `mod_groups`

Minimal structure:

```json
{
  "mod_groups": [
    {
      "name": "Example Group",
      "mods": [
        {
          "name": "Example Mod",
          "source_folder": "F:\\Source\\MyMod",
          "release_folder": "G:\\Release\\MyMod",
          "github_folder": "G:\\Github\\MyMod",
          "mode": "update",
          "assets": [
            {
              "path": "",
              "file_patterns": ["*.reds", "Config.reds"]
            }
          ]
        }
      ]
    }
  ]
}
```

Field notes:

- `mode`: currently expected values are `update` or `skip`.
- `assets[].path`: subfolder under `source_folder` and destination folders.
- `assets[].file_patterns`: wildcard patterns (`*.reds`, `*.yaml`, etc.).
- `release_folder` or `github_folder` can be empty strings to skip that target.

## Copy Behavior

For matched files, copy happens when:

- Target file does not exist, or
- Source file is newer than target, or
- Source and target differ by content.

Excluded files include:

- `Thumbs.db`
- Files containing `.vortex_backup`

The script preserves timestamps/metadata via `shutil.copy2`.

## Archive Behavior

If a mod defines `archive_folder` and at least one file was copied:

- A dated archive name is generated from mod name, for example `MyMod20260726.7z`.
- Archive is written to:
  - `archive_target` if provided
  - otherwise `archive_folder`
- Existing matching archives in `archive_target` are moved to `_old`.
- Some files/folders are excluded from the archive (for example `.vscode`, `.ppj`, `.code-workspace`, hidden/system noise files).

## Usage

From the `DeployModFiles` directory:

```powershell
python deployModFiles.py
```

The script has no CLI arguments right now. It always reads:

- `data/config.yaml`

## Typical Workflow

1. Edit `data/config.yaml` to enable only the groups/manifests you want.
2. Update manifest JSON entries with valid source/release/github/archive paths.
3. Run `python deployModFiles.py`.
4. Check console output for copied files, skipped groups/mods, and archive actions.

## Troubleshooting

- `Configuration file not found...`
  - Verify `data/config.yaml` exists next to the script.

- `Invalid Source folder...`
  - Check `source_folder + assets.path` exists exactly.

- `No mod group deployed` or `No mods deployed`
  - Confirm statuses are `true` and `mode` is not `skip`.

- Missing destination output
  - Ensure destination folder is not empty (`""`) for that target.

## Known Limitations

- No command-line options yet (always config-driven).
- A known case-sensitivity issue is documented in code comments for some existing target files.
