import argparse
import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
INPUT_FILE = DATA_DIR / "tweakdb.txt"
NAME_EXCLUDE_PATTERNS: list[str] = [
	"_inline*", 
]


def _sanitize_pattern_for_filename(pattern: str) -> str:
	"""Strip characters that are unsafe in a filename."""
	return re.sub(r'[\\/:*?"<>|.]+', "_", pattern)


def _name_matches_pattern(name: str, pattern: str) -> bool:
	"""Match plain contains tags and '*' wildcard patterns."""
	name_l = name.lower()
	pattern_l = pattern.lower()

	if "*" not in pattern_l:
		return pattern_l in name_l

	wildcard_regex = re.escape(pattern_l).replace(r"\*", ".*")
	return re.search(wildcard_regex, name_l) is not None


def filter_record_names(df: pd.DataFrame, patterns: list[str]) -> pd.DataFrame:
	"""Remove record names that match any pattern in the list."""
	if df.empty or not patterns:
		return df

	mask_to_remove = df["record_name"].apply(
		lambda record_name: any(_name_matches_pattern(record_name, pattern) for pattern in patterns)
	)
	return df[~mask_to_remove].reset_index(drop=True)


def build_base_pattern_regex(base_pattern: str) -> re.Pattern[str]:
	"""Match strict base entries: <base_pattern>.<name>,<number>."""
	return re.compile(rf"^{re.escape(base_pattern)}\.([^.,]+),(\d+(?:\.\d+)?)$")


def extract_matching_lines(input_file: Path, base_pattern: str) -> pd.DataFrame:
	"""Return record names from strict base entry lines matching the base pattern."""
	pattern_regex = build_base_pattern_regex(base_pattern)
	records = []

	total_lines = sum(1 for _ in input_file.open("r", encoding="utf-8"))

	with input_file.open("r", encoding="utf-8") as infile:
		for raw_line in tqdm(infile, total=total_lines, desc="Parsing tweakdb", unit="line"):
			line = raw_line.strip()
			match = pattern_regex.match(line)
			if not match:
				continue

			records.append(
				{
					"record_name": f"{base_pattern}.{match.group(1)}",
				}
			)

	return pd.DataFrame(records, columns=["record_name"])


def save_matching_lines(df: pd.DataFrame, output_file: Path) -> None:
	"""Write only record names to the output file."""
	output_file.parent.mkdir(parents=True, exist_ok=True)
	with output_file.open("w", encoding="utf-8") as outfile:
		if not df.empty:
			outfile.write("\n".join(df["record_name"].tolist()))
			outfile.write("\n")


def main() -> None:
	parser = argparse.ArgumentParser(description="Extract TweakDB records matching a base pattern.")
	parser.add_argument(
		"base_pattern",
		nargs="?",
		default="BaseStatusEffect",
		help="Base pattern to match, e.g. 'BaseStatusEffect' (default: %(default)s)",
	)
	args = parser.parse_args()

	if not INPUT_FILE.exists():
		raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

	output_file = DATA_DIR / f"tweakdb-{_sanitize_pattern_for_filename(args.base_pattern)}.txt"

	matches_df = extract_matching_lines(INPUT_FILE, args.base_pattern)
	matches_df = filter_record_names(matches_df, NAME_EXCLUDE_PATTERNS)
	save_matching_lines(matches_df, output_file)

	print(f"Extracted {len(matches_df)} matching entries for pattern '{args.base_pattern}'.")
	print(f"Saved to: {output_file}")


if __name__ == "__main__":
	main()
