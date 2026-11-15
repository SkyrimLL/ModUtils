"""
Vortex tracks enabled/disabled state inside its internal application state database (state.v2 / LevelDB), not by renaming or altering folders in the staging directory.

You can extract the exact enabled state without external tools by reading Vortex's automated JSON state backup, which Vortex writes whenever it updates deployment or profile rules.

Instructions to create a Vortex backup.

- Open Vortex.
- Go to Settings > Workarounds.
- Click Create Backup.
- Close Vortex (to ensure all buffers flush to disk).
 """
import json
import os
from pathlib import Path

# --- Configuration ---
GAME_ID = "skyrimse"  # e.g., 'skyrimse', 'fallout4', 'cyberpunk2077'
MO2_PROFILE_DIR = Path(r"F:\_VORTEX_MODS\_backups")

# Vortex application data path
VORTEX_APPDATA = Path(os.environ["APPDATA"]) / "Vortex"

# Find the most recent state backup
backup_dirs = [
    VORTEX_APPDATA / "temp" / "state_backups_full",
    VORTEX_APPDATA / "backups",
]

backup_files = []
for b_dir in backup_dirs:
    if b_dir.exists():
        backup_files.extend(b_dir.glob("*.json"))

if not backup_files:
    raise FileNotFoundError(
        "No Vortex state backups found. Go to Vortex -> Settings -> Workarounds -> Create Backup."
    )

latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)
print(f"Reading state from: {latest_backup.name}")

with open(latest_backup, "r", encoding="utf-8") as f:
    state = json.load(f)

# 1. Resolve Profile & Active Mods
profiles = state.get("persistent", {}).get("profiles", {})
game_profiles = [p for p in profiles.values() if p.get("gameId") == GAME_ID]

if not game_profiles:
    raise ValueError(f"No profile found in Vortex for game ID '{GAME_ID}'")

# Use last activated profile or the first matching profile
target_profile = next((p for p in game_profiles if p.get("lastActivated")), game_profiles[0])
profile_mod_states = target_profile.get("modState", {})

# 2. Resolve Mod Metadata (folder names / IDs)
mods_table = state.get("persistent", {}).get("mods", {}).get(GAME_ID, {})

modlist_entries = []

for mod_id, mod_info in mods_table.items():
    # Folder name in staging directory
    installation_path = mod_info.get("installationPath")
    if not installation_path:
        continue

    # Check activation state in profile
    mod_state = profile_mod_states.get(mod_id, {})
    is_enabled = mod_state.get("enabled", False)

    prefix = "+" if is_enabled else "-"
    modlist_entries.append((prefix, installation_path))

# 3. MO2 Priority Inversion:
# MO2 reads modlist.txt from top (highest priority) to bottom (lowest priority).
# If you don't have explicit load order rules, reversing staging order provides a base list:
modlist_entries.reverse()

output_lines = [f"{prefix}{name}\n" for prefix, name in modlist_entries]

output_file = MO2_PROFILE_DIR / "modlist.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.writelines(output_lines)

enabled_count = sum(1 for p, _ in modlist_entries if p == "+")
disabled_count = len(modlist_entries) - enabled_count
print(f"Wrote {output_file}: {enabled_count} enabled, {disabled_count} disabled.")