import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
INPUT_FILE = DATA_DIR / "tweakdb.txt"
OUTPUT_FILE = DATA_DIR / "tweakdb-Vehicles.txt"
MISSING_CARS_OUTPUT_FILE = DATA_DIR / "missingcars_tweakxl.txt"
VEHICLES_TO_DELETE_OUTPUT_FILE = DATA_DIR / "missingcars_tweakxl_to_delete.txt"
CLAIM_VEHICLES_TWEAKS_DIR = Path(r"F:\_VORTEX_MODS\cyberpunk2077\ClaimVehicles\r6\tweaks\ClaimVehicles")
NAME_EXCLUDE_PATTERNS: list[str] = [
	"_offer", 
	"_inline*", 
	"_crashed",
	"_broken",
	"_destroyed",
	"_exploded",
	"_crash",
	"*UIData",
	"_settings",
	"Settings",
	"DataPackage",
	"FirstAvailable",
	"CameraParams",
	"VehicleWheel",
	"DriveWheel",
	"Vehicle_Power_Weapon_",
	"Base_Vehicle_Weapon",
	"VehicleShowroomUI*",
	"VehicleTPP*",
	"FlatTire*",
	"VehicleDroneCarrier",
	"VehicleDriver",
	"VehicleDriveModelData",
	"VehicleAirControl",
	"VehicleBurnOut",
	"ControlAxis",
	"WaterDefault",
	"VehicleDataPackage",
	"VehicleCameraManager",
	"Vehicle_Missile_Launcher",
	"UphillDriveHelper_",
	"TrafficSuspension_",
	"FrictionModifier",
	"GravityModifier",
	"RotationLimiter",
	"DestructionParams",
	"DynamicDownforceHelper",
	"FxWheels",
	"FxCollision",
	"SeatSetDefault",
    "VehicleSeat",
	"EngineData",
	"AppearancesToColor",
	"Vehicle.Always",
	"Vehicle.Bike",
	"Vehicle.Car",
	"Vehicle.CourierMissions",
	"Vehicle.Dynamic",
	"Vehicle.PanamTurret",
	"Vehicle.Preview",
	"Vehicle.Quest",
	"Vehicle.SeatBackLeft",
	"Vehicle.SeatBackRight",
	"Vehicle.SeatFrontLeft",
	"Vehicle.SeatFrontRight",
	"Vehicle.Veh4WDefaultState",
	"Vehicle.Vehicle_2w_Default",
	"Vehicle.Vehicle_4w_Default", 
	"_disabled_interactions",
	"Vehicle.sq027_fake_flatbed_truck_a",
	"Vehicle.sq027_fake_flatbed_truck_b",
	"Vehicle.sq030_lake_crane",
	"Vehicle.summon_setup",
	"Vehicle.vehicle_destruction_percentage_weights",
	"Vehicle.vehicle_racing",
	"Vehicle.vehicle_template",
	"Vehicle.PlayerBike",
	"Vehicle.PlayerCar",
	"Vehicle.drive_alerted_setup",
	"Vehicle.q307_militech_manticore",
	"Vehicle.q305_kaukaz_containter",
	"Vehicle.q114_tunnel_driller",
	"Vehicle.q003_manticore",
	"Vehicle.sa_ep1_airdrop_crate",
	"Vehicle.sq025_delamain_cab_*",
	"_no_interactions",
	"_test",
	"vcc_paintjob_",
	"_spaceport",
	"_cart",
	"_wagon",
	"_wheelchair",
	"_satellite",
	"_bus",
	"_panzer",
	"Panzer",
	"_av",
	"Vehicle.av_", 
	"_drone",
	"_heli",
	"_chopper",
	"_train",
	"_holo",
	"_rocket",
	"_capsule",
	"_pod",
	"_yacht",
	"_barge"
	]

# Matches: vehicle.<string without '.'>,<number>
VEHICLE_LINE_PATTERN = re.compile(r"^Vehicle\.([^.,]+),(\d+(?:\.\d+)?)$")
YAML_VEHICLE_PATTERN = re.compile(r"\bVehicle\.[A-Za-z0-9_]+\b")
MISSING_VEHICLE_YAML_PREFIX = "  - !append "


def _name_matches_pattern(name: str, pattern: str) -> bool:
	"""Match plain contains tags and '*' wildcard patterns."""
	name_l = name.lower()
	pattern_l = pattern.lower()

	if "*" not in pattern_l:
		return pattern_l in name_l

	wildcard_regex = re.escape(pattern_l).replace(r"\*", ".*")
	return re.search(wildcard_regex, name_l) is not None


def filter_vehicle_names(df: pd.DataFrame, patterns: list[str]) -> pd.DataFrame:
	"""Remove vehicle names that match any pattern in the list."""
	if df.empty or not patterns:
		return df

	mask_to_remove = df["vehicle_name"].apply(
		lambda vehicle_name: any(_name_matches_pattern(vehicle_name, pattern) for pattern in patterns)
	)
	return df[~mask_to_remove].reset_index(drop=True)


def extract_vehicle_lines(input_file: Path) -> pd.DataFrame:
	"""Return vehicle names from strict base vehicle lines only."""
	records = []

	total_lines = sum(1 for _ in input_file.open("r", encoding="utf-8"))

	with input_file.open("r", encoding="utf-8") as infile:
		for raw_line in tqdm(infile, total=total_lines, desc="Parsing tweakdb", unit="line"):
			line = raw_line.strip()
			match = VEHICLE_LINE_PATTERN.match(line)
			if not match:
				continue

			records.append(
				{
					"vehicle_name": "Vehicle." + match.group(1),
				}
			)

	return pd.DataFrame(records, columns=["vehicle_name"])


def save_vehicle_lines(df: pd.DataFrame, output_file: Path) -> None:
	"""Write only vehicle names to the output file."""
	output_file.parent.mkdir(parents=True, exist_ok=True)
	with output_file.open("w", encoding="utf-8") as outfile:
		if not df.empty:
			outfile.write("\n".join(df["vehicle_name"].tolist()))
			outfile.write("\n")


def export_missing_vehicles_from_claimvehicles_yaml(
	all_vehicles_file: Path,
	claim_vehicles_tweaks_dir: Path,
	missing_output_file: Path,
	) -> tuple[int, int]:
	"""Write vehicles present in tweakdb list but absent from ClaimVehicles YAML files."""
	if not all_vehicles_file.exists():
		raise FileNotFoundError(f"Vehicle list file not found: {all_vehicles_file}")
	if not claim_vehicles_tweaks_dir.exists():
		raise FileNotFoundError(f"ClaimVehicles tweaks dir not found: {claim_vehicles_tweaks_dir}")

	with all_vehicles_file.open("r", encoding="utf-8") as infile:
		all_vehicles = [line.strip() for line in infile if line.strip()]

	vehicles_in_yaml: set[str] = set()
	for yaml_file in sorted(claim_vehicles_tweaks_dir.glob("*.y*ml")):
		content = yaml_file.read_text(encoding="utf-8")
		vehicles_in_yaml.update(YAML_VEHICLE_PATTERN.findall(content))

	missing_vehicles = [vehicle for vehicle in all_vehicles if vehicle not in vehicles_in_yaml]

	missing_output_file.parent.mkdir(parents=True, exist_ok=True)
	with missing_output_file.open("w", encoding="utf-8") as outfile:
		if missing_vehicles:
			formatted_missing_vehicles = [f"{MISSING_VEHICLE_YAML_PREFIX}{vehicle}" for vehicle in missing_vehicles]
			outfile.write("\n".join(formatted_missing_vehicles))
			outfile.write("\n")

	return len(missing_vehicles), len(vehicles_in_yaml)


def export_yaml_only_vehicles_with_source_file(
	all_vehicles_file: Path,
	claim_vehicles_tweaks_dir: Path,
	output_file: Path,
	) -> tuple[int, int]:
	"""Write YAML-only vehicles grouped by source YAML file."""
	if not all_vehicles_file.exists():
		raise FileNotFoundError(f"Vehicle list file not found: {all_vehicles_file}")
	if not claim_vehicles_tweaks_dir.exists():
		raise FileNotFoundError(f"ClaimVehicles tweaks dir not found: {claim_vehicles_tweaks_dir}")

	with all_vehicles_file.open("r", encoding="utf-8") as infile:
		all_vehicles_set = {line.strip() for line in infile if line.strip()}

	vehicle_to_yaml_files: dict[str, set[str]] = {}
	for yaml_file in sorted(claim_vehicles_tweaks_dir.glob("*.y*ml")):
		content = yaml_file.read_text(encoding="utf-8")
		yaml_file_name = yaml_file.name
		for vehicle in YAML_VEHICLE_PATTERN.findall(content):
			vehicle_to_yaml_files.setdefault(vehicle, set()).add(yaml_file_name)

	vehicles_to_delete: list[tuple[str, str]] = []
	vehicles_by_yaml_file: dict[str, list[str]] = {}
	for vehicle, yaml_files in sorted(vehicle_to_yaml_files.items()):
		if vehicle in all_vehicles_set:
			continue
		for yaml_file_name in sorted(yaml_files):
			vehicles_to_delete.append((vehicle, yaml_file_name))
			vehicles_by_yaml_file.setdefault(yaml_file_name, []).append(vehicle)

	output_file.parent.mkdir(parents=True, exist_ok=True)
	with output_file.open("w", encoding="utf-8") as outfile:
		if vehicles_by_yaml_file:
			for yaml_file_name in sorted(vehicles_by_yaml_file):
				outfile.write(f"[{yaml_file_name}]\n")
				for vehicle in sorted(set(vehicles_by_yaml_file[yaml_file_name])):
					outfile.write(f"{vehicle}\n")
				outfile.write("\n")

	return len(vehicles_to_delete), len({vehicle for vehicle, _ in vehicles_to_delete})


def main() -> None:
	if not INPUT_FILE.exists():
		raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

	vehicles_df = extract_vehicle_lines(INPUT_FILE)
	vehicles_df = filter_vehicle_names(vehicles_df, NAME_EXCLUDE_PATTERNS)
	save_vehicle_lines(vehicles_df, OUTPUT_FILE)

	missing_count, yaml_unique_count = export_missing_vehicles_from_claimvehicles_yaml(
		OUTPUT_FILE,
		CLAIM_VEHICLES_TWEAKS_DIR,
		MISSING_CARS_OUTPUT_FILE,
	)

	to_delete_rows_count, to_delete_vehicle_count = export_yaml_only_vehicles_with_source_file(
		OUTPUT_FILE,
		CLAIM_VEHICLES_TWEAKS_DIR,
		VEHICLES_TO_DELETE_OUTPUT_FILE,
	)

	print(f"Extracted {len(vehicles_df)} vehicle entries.")
	print(f"Saved to: {OUTPUT_FILE}")
	print(f"Unique vehicles found in YAML files: {yaml_unique_count}")
	print(f"Missing ClaimVehicles entries: {missing_count}")
	print(f"Saved to: {MISSING_CARS_OUTPUT_FILE}")
	print(f"YAML-only vehicle entries (with source file): {to_delete_rows_count}")
	print(f"Unique YAML-only vehicles: {to_delete_vehicle_count}")
	print(f"Saved to: {VEHICLES_TO_DELETE_OUTPUT_FILE}")


if __name__ == "__main__":
	main()
