"""Generate PartySheet-compatible portrait thumbnails for every potential follower
in a Skyrim SE load order, using the NPC Plugin Chooser mugshot cache as image source.

Pipeline:
  1. Read the active load order (plugins.txt + implicit base masters).
  2. Parse every plugin's NPC_ records (TES4 binary format), keeping winning overrides.
  3. Detect followers via faction membership (PotentialFollower / PotentialHireling),
     honoring "Use Factions" template inheritance.
  4. Resolve display names, including localized string tables (loose .STRINGS or BSA).
  5. Locate each follower's mugshot in the NPC Plugin Chooser cache
     (<ModName>/<SourcePlugin>/<LocalFormID>.png|webp|jpg); when several mods provide
     one, the mod closest to the bottom of modlist.txt wins.
  6. Emit 256x256 JPEG thumbnails named after the NPC display name, plus
     Plugin-FormID fallback names for unnamed NPCs and duplicate display names.

Requires: Pillow, lz4  (pip install pillow lz4)
"""

from __future__ import annotations

import argparse
import io
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import lz4.frame
from PIL import Image

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_DATA_DIR = Path(r"F:\Steam\steamapps\common\Skyrim Special Edition\Data")
DEFAULT_PLUGINS_TXT = Path(
    r"F:\_VORTEX_MODS\_backups\plugins.txt"
)
DEFAULT_MODLIST_TXT = Path(r"F:\_VORTEX_MODS\_backups\modlist.txt")
DEFAULT_MUGSHOT_DIR = Path(r"F:\_VORTEX_MODS\_backups\NPCMugshots")
DEFAULT_OUTPUT_DIR = Path(
    r"F:\_VORTEX_MODS\skyrimse\_CustomPartySheetPortraits\Interface\PartySheet\Portraits"
)

# Plugins loaded by the engine before anything in plugins.txt.
IMPLICIT_MASTERS = [
    "Skyrim.esm",
    "Update.esm",
    "Dawnguard.esm",
    "HearthFires.esm",
    "Dragonborn.esm",
    "ccBGSSSE001-Fish.esm",
    "ccQDRSSE001-SurvivalMode.esl",
    "ccBGSSSE037-Curios.esl",
    "ccBGSSSE025-AdvDSGS.esm",
    "_ResourcePack.esl",
]

# FormKey = (source plugin lowercase, local form id)
FormKey = tuple[str, int]

# Factions whose membership marks an NPC as a recruitable follower.
FOLLOWER_FACTIONS: set[FormKey] = {
    ("skyrim.esm", 0x05C84D),  # PotentialFollowerFaction
    ("skyrim.esm", 0x0BD738),  # PotentialHireling
}

PLAYER_FORMKEY: FormKey = ("skyrim.esm", 0x000007)

THUMB_SIZE = 256
JPEG_QUALITY = 92

# NPC_ ACBS template data flags
TPL_USE_FACTIONS = 0x0004
TPL_USE_BASE_DATA = 0x0080

RECORD_FLAG_DELETED = 0x00000020
RECORD_FLAG_COMPRESSED = 0x00040000
TES4_FLAG_LOCALIZED = 0x00000080

MUGSHOT_EXTENSIONS = {".png", ".webp", ".jpg", ".jpeg"}
INVALID_FILENAME_CHARS = set('<>:"/\\|?*')


# ---------------------------------------------------------------------------
# Load order
# ---------------------------------------------------------------------------


class LoadOrderReader:
    """Builds the active plugin load order from plugins.txt and implicit masters."""

    def __init__(self, plugins_txt: Path, data_dir: Path):
        self._plugins_txt = plugins_txt
        self._data_dir = data_dir

    def read(self) -> list[str]:
        enabled: list[str] = []
        text = self._plugins_txt.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("*"):
                enabled.append(line[1:].strip())
        listed = {p.lower() for p in enabled}
        order = [
            m
            for m in IMPLICIT_MASTERS
            if m.lower() not in listed and (self._data_dir / m).is_file()
        ]
        order.extend(p for p in enabled if (self._data_dir / p).is_file())
        return order


# ---------------------------------------------------------------------------
# TES4 plugin parsing
# ---------------------------------------------------------------------------


@dataclass
class NpcRecord:
    form_key: FormKey
    editor_id: str | None
    deleted: bool
    # Raw FULL payload plus the plugin that provided it (needed for localization).
    full_bytes: bytes | None
    full_plugin: str | None
    full_localized: bool
    factions: list[FormKey]
    template: FormKey | None
    template_flags: int


@dataclass
class PluginInfo:
    name: str
    localized: bool
    masters: list[str]


class PluginParser:
    """Streams NPC_ records out of a single TES4 plugin file."""

    REC_HEADER = struct.Struct("<4sIIIHHHH")

    def __init__(self, path: Path):
        self._path = path
        self.info: PluginInfo | None = None

    def parse_npcs(self) -> list[NpcRecord]:
        npcs: list[NpcRecord] = []
        with open(self._path, "rb") as fh:
            header = fh.read(24)
            if len(header) < 24 or header[:4] != b"TES4":
                raise ValueError("not a TES4 plugin")
            _, data_size, flags, _, _, _, _, _ = self.REC_HEADER.unpack(header)
            tes4_data = fh.read(data_size)
            masters = self._parse_masters(tes4_data)
            self.info = PluginInfo(
                name=self._path.name,
                localized=bool(flags & TES4_FLAG_LOCALIZED),
                masters=masters,
            )
            file_size = self._path.stat().st_size
            while fh.tell() + 24 <= file_size:
                head = fh.read(24)
                if len(head) < 24:
                    break
                rtype = head[:4]
                size = struct.unpack_from("<I", head, 4)[0]
                if rtype == b"GRUP":
                    label = head[8:12]
                    if label == b"NPC_":
                        self._parse_group(fh.read(size - 24), npcs)
                    else:
                        fh.seek(size - 24, io.SEEK_CUR)
                else:
                    fh.seek(size, io.SEEK_CUR)
        return npcs

    @staticmethod
    def _parse_masters(tes4_data: bytes) -> list[str]:
        masters: list[str] = []
        for stype, payload in PluginParser._iter_subrecords(tes4_data):
            if stype == b"MAST":
                masters.append(payload.rstrip(b"\0").decode("cp1252", "replace"))
        return masters

    def _parse_group(self, blob: bytes, out: list[NpcRecord]) -> None:
        pos = 0
        end = len(blob)
        while pos + 24 <= end:
            rtype = blob[pos : pos + 4]
            size = struct.unpack_from("<I", blob, pos + 4)[0]
            if rtype == b"GRUP":
                self._parse_group(blob[pos + 24 : pos + size], out)
                pos += size
                continue
            if rtype == b"NPC_":
                flags, form_id = struct.unpack_from("<II", blob, pos + 8)
                data = blob[pos + 24 : pos + 24 + size]
                if flags & RECORD_FLAG_COMPRESSED and len(data) >= 4:
                    data = zlib.decompress(data[4:])
                record = self._parse_npc(form_id, flags, data)
                if record is not None:
                    out.append(record)
            pos += 24 + size

    def _parse_npc(self, form_id: int, flags: int, data: bytes) -> NpcRecord | None:
        assert self.info is not None
        editor_id: str | None = None
        full_bytes: bytes | None = None
        factions: list[FormKey] = []
        template: FormKey | None = None
        template_flags = 0
        for stype, payload in self._iter_subrecords(data):
            if stype == b"EDID":
                editor_id = payload.rstrip(b"\0").decode("cp1252", "replace")
            elif stype == b"FULL":
                full_bytes = payload
            elif stype == b"SNAM" and len(payload) >= 4:
                factions.append(self._resolve(struct.unpack_from("<I", payload)[0]))
            elif stype == b"TPLT" and len(payload) >= 4:
                template = self._resolve(struct.unpack_from("<I", payload)[0])
            elif stype == b"ACBS" and len(payload) >= 20:
                template_flags = struct.unpack_from("<H", payload, 18)[0]
        return NpcRecord(
            form_key=self._resolve(form_id),
            editor_id=editor_id,
            deleted=bool(flags & RECORD_FLAG_DELETED),
            full_bytes=full_bytes,
            full_plugin=self.info.name if full_bytes is not None else None,
            full_localized=self.info.localized,
            factions=factions,
            template=template,
            template_flags=template_flags,
        )

    def _resolve(self, form_id: int) -> FormKey:
        assert self.info is not None
        index = form_id >> 24
        masters = self.info.masters
        source = masters[index] if index < len(masters) else self.info.name
        return (source.lower(), form_id & 0x00FFFFFF)

    @staticmethod
    def _iter_subrecords(data: bytes):
        pos = 0
        end = len(data)
        override_size: int | None = None
        while pos + 6 <= end:
            stype = data[pos : pos + 4]
            size = struct.unpack_from("<H", data, pos + 4)[0]
            pos += 6
            if stype == b"XXXX":
                override_size = struct.unpack_from("<I", data, pos)[0]
                pos += size
                continue
            if override_size is not None:
                size = override_size
                override_size = None
            yield stype, data[pos : pos + size]
            pos += size


# ---------------------------------------------------------------------------
# Localized strings (.STRINGS loose files and BSA archives)
# ---------------------------------------------------------------------------


class BsaReader:
    """Minimal BSA v104/v105 reader able to extract a single file by path."""

    HEADER = struct.Struct("<4sII IIIIII")

    def __init__(self, path: Path):
        self._path = path

    def extract(self, wanted: str) -> bytes | None:
        wanted = wanted.lower().replace("/", "\\")
        wanted_dir, _, wanted_file = wanted.rpartition("\\")
        try:
            with open(self._path, "rb") as fh:
                head = fh.read(36)
                if len(head) < 36 or head[:4] != b"BSA\0":
                    return None
                (_, version, _, archive_flags, folder_count, file_count, _, _, _) = (
                    self.HEADER.unpack(head)
                )
                folder_rec = (
                    struct.Struct("<QIIQ") if version >= 105 else struct.Struct("<QII")
                )
                folders = [
                    folder_rec.unpack(fh.read(folder_rec.size))
                    for _ in range(folder_count)
                ]
                entries: list[tuple[int, int]] = []  # (size, offset) in name order
                match_dir_spans: list[tuple[int, int]] = []
                for rec in folders:
                    count = rec[1]
                    name = ""
                    if archive_flags & 0x1:
                        name_len = fh.read(1)[0]
                        name = (
                            fh.read(name_len)
                            .rstrip(b"\0")
                            .decode("cp1252", "replace")
                            .lower()
                        )
                    start = len(entries)
                    for _ in range(count):
                        _, size, offset = struct.unpack("<QII", fh.read(16))
                        entries.append((size, offset))
                    if name == wanted_dir:
                        match_dir_spans.append((start, start + count))
                if not (archive_flags & 0x2) or not match_dir_spans:
                    return None
                name_block = fh.read(self._total_name_length(head))
                names = name_block.split(b"\0")[:file_count]
                for start, stop in match_dir_spans:
                    for i in range(start, stop):
                        if names[i].decode("cp1252", "replace").lower() == wanted_file:
                            return self._read_file(
                                fh, entries[i], archive_flags, version
                            )
        except (OSError, struct.error, IndexError):
            return None
        return None

    def _total_name_length(self, head: bytes) -> int:
        # totalFileNameLength sits at byte 28 of the 36-byte header.
        return struct.unpack_from("<I", head, 28)[0]

    @staticmethod
    def _read_file(
        fh, entry: tuple[int, int], archive_flags: int, version: int
    ) -> bytes | None:
        size, offset = entry
        compressed = bool(archive_flags & 0x4) != bool(size & 0x40000000)
        size &= 0x3FFFFFFF
        fh.seek(offset)
        blob = fh.read(size)
        if archive_flags & 0x100:  # embedded file name prefix
            skip = blob[0] + 1
            blob = blob[skip:]
        if not compressed:
            return blob
        try:
            if version >= 105:
                return lz4.frame.decompress(blob[4:])
            return zlib.decompress(blob[4:])
        except Exception:
            return None


class StringsResolver:
    """Resolves localized FULL string ids to text via loose or BSA string tables."""

    def __init__(self, data_dir: Path, language: str = "english"):
        self._data_dir = data_dir
        self._language = language.lower()
        self._tables: dict[str, dict[int, str] | None] = {}

    def lookup(self, plugin: str, string_id: int) -> str | None:
        table = self._table_for(plugin)
        return table.get(string_id) if table else None

    def _table_for(self, plugin: str) -> dict[int, str] | None:
        key = plugin.lower()
        if key not in self._tables:
            self._tables[key] = self._load_table(plugin)
        return self._tables[key]

    def _load_table(self, plugin: str) -> dict[int, str] | None:
        stem = Path(plugin).stem
        target = f"{stem}_{self._language}.strings"
        loose_dir = self._data_dir / "Strings"
        if loose_dir.is_dir():
            for candidate in loose_dir.iterdir():
                if candidate.name.lower() == target:
                    return self._parse_strings(candidate.read_bytes())
        wanted = f"strings\\{target}"
        all_bsas = sorted(self._data_dir.glob("*.bsa"))
        prefixed = [b for b in all_bsas if b.name.lower().startswith(stem.lower())]
        # Official DLC strings live in "Skyrim - Interface.bsa", so after the
        # prefix-matched archives fall back to scanning every remaining BSA.
        for bsa in prefixed + [b for b in all_bsas if b not in prefixed]:
            blob = BsaReader(bsa).extract(wanted)
            if blob is not None:
                return self._parse_strings(blob)
        return None

    @staticmethod
    def _parse_strings(blob: bytes) -> dict[int, str] | None:
        try:
            count, _ = struct.unpack_from("<II", blob)
            data_start = 8 + count * 8
            table: dict[int, str] = {}
            for i in range(count):
                string_id, offset = struct.unpack_from("<II", blob, 8 + i * 8)
                start = data_start + offset
                stop = blob.index(b"\0", start)
                table[string_id] = blob[start:stop].decode("cp1252", "replace")
            return table
        except (struct.error, ValueError):
            return None


# ---------------------------------------------------------------------------
# Follower resolution
# ---------------------------------------------------------------------------


@dataclass
class Follower:
    form_key: FormKey
    name: str | None
    editor_id: str | None


class FollowerResolver:
    """Merges winning NPC overrides and extracts the follower set."""

    def __init__(self, strings: StringsResolver):
        self._strings = strings
        self._npcs: dict[FormKey, NpcRecord] = {}

    def add_plugin_records(self, records: list[NpcRecord]) -> None:
        for record in records:
            self._npcs[record.form_key] = record  # later plugin wins

    @property
    def npc_count(self) -> int:
        return len(self._npcs)

    def followers(self) -> list[Follower]:
        result: list[Follower] = []
        for form_key, record in self._npcs.items():
            if form_key == PLAYER_FORMKEY or record.deleted:
                continue
            if FOLLOWER_FACTIONS & set(self._effective_factions(record)):
                result.append(
                    Follower(
                        form_key=form_key,
                        name=self._effective_name(record),
                        editor_id=record.editor_id,
                    )
                )
        result.sort(key=lambda f: (f.name or "", f.form_key))
        return result

    def _effective_factions(self, record: NpcRecord, depth: int = 0) -> list[FormKey]:
        if record.template_flags & TPL_USE_FACTIONS and record.template and depth < 16:
            target = self._npcs.get(record.template)
            if target is not None:
                return self._effective_factions(target, depth + 1)
            return []  # template is a leveled list or unresolved
        return record.factions

    def _effective_name(self, record: NpcRecord, depth: int = 0) -> str | None:
        name = self._decode_full(record)
        if name:
            return name
        if record.template_flags & TPL_USE_BASE_DATA and record.template and depth < 16:
            target = self._npcs.get(record.template)
            if target is not None:
                return self._effective_name(target, depth + 1)
        return None

    def _decode_full(self, record: NpcRecord) -> str | None:
        if not record.full_bytes or not record.full_plugin:
            return None
        if record.full_localized:
            if len(record.full_bytes) < 4:
                return None
            string_id = struct.unpack_from("<I", record.full_bytes)[0]
            return self._strings.lookup(record.full_plugin, string_id)
        return record.full_bytes.rstrip(b"\0").decode("cp1252", "replace") or None


# ---------------------------------------------------------------------------
# Mugshot cache index
# ---------------------------------------------------------------------------


class MugshotIndex:
    """Indexes the NPC Plugin Chooser cache and ranks sources by modlist priority."""

    def __init__(self, mugshot_dir: Path, modlist_txt: Path):
        self._priorities = self._read_modlist(modlist_txt)
        self._index: dict[FormKey, list[tuple[str, Path]]] = {}
        self._build(mugshot_dir)

    @staticmethod
    def _read_modlist(modlist_txt: Path) -> dict[str, int]:
        priorities: dict[str, int] = {}
        if modlist_txt.is_file():
            text = modlist_txt.read_text(encoding="utf-8", errors="replace")
            for position, line in enumerate(text.splitlines()):
                line = line.strip()
                if line.startswith(("+", "-")):
                    priorities[line[1:].strip().lower()] = position
        return priorities

    def _build(self, mugshot_dir: Path) -> None:
        if not mugshot_dir.is_dir():
            return
        for mod_dir in mugshot_dir.iterdir():
            if not mod_dir.is_dir():
                continue
            for plugin_dir in mod_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue
                plugin = plugin_dir.name.lower()
                for file in plugin_dir.iterdir():
                    if file.suffix.lower() not in MUGSHOT_EXTENSIONS:
                        continue
                    try:
                        local_id = int(file.stem, 16) & 0x00FFFFFF
                    except ValueError:
                        continue
                    key = (plugin, local_id)
                    self._index.setdefault(key, []).append((mod_dir.name, file))

    def best_for(self, form_key: FormKey) -> tuple[str, Path] | None:
        """Pick the candidate whose mod sits lowest (latest) in modlist.txt."""
        candidates = self._index.get(form_key)
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda c: (self._priorities.get(c[0].lower(), -1), c[0].lower()),
        )

    def candidate_count(self, form_key: FormKey) -> int:
        return len(self._index.get(form_key, []))


# ---------------------------------------------------------------------------
# Thumbnail generation
# ---------------------------------------------------------------------------


class ThumbnailWriter:
    """Converts mugshots into square 256x256 JPEG portraits."""

    def __init__(self, output_dir: Path, dry_run: bool = False):
        self._output_dir = output_dir
        self._dry_run = dry_run

    def write(self, source: Path, file_stem: str) -> Path:
        destination = self._output_dir / f"{file_stem}.jpg"
        if self._dry_run:
            return destination
        self._output_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as img:
            thumb = self._square_crop(img.convert("RGB")).resize(
                (THUMB_SIZE, THUMB_SIZE), Image.LANCZOS
            )
            thumb.save(destination, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return destination

    @staticmethod
    def _square_crop(img: Image.Image) -> Image.Image:
        width, height = img.size
        if width == height:
            return img
        side = min(width, height)
        if width > height:
            left = (width - side) // 2
            return img.crop((left, 0, left + side, side))
        # Tall mugshots: anchor at the top, where the face is.
        return img.crop((0, 0, side, side))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def sanitize_filename(name: str) -> str | None:
    cleaned = "".join(c for c in name if c not in INVALID_FILENAME_CHARS and ord(c) >= 32)
    cleaned = cleaned.strip().rstrip(".")
    return cleaned or None


def formid_stem(form_key: FormKey, source_plugin_display: str) -> str:
    return f"{source_plugin_display}-0x{form_key[1]:X}"


@dataclass
class RunReport:
    plugins_parsed: int = 0
    plugins_failed: list[str] = field(default_factory=list)
    followers_total: int = 0
    written: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)


def run(args: argparse.Namespace) -> RunReport:
    report = RunReport()
    load_order = LoadOrderReader(args.plugins_txt, args.data_dir).read()
    print(f"Load order: {len(load_order)} plugins")

    strings = StringsResolver(args.data_dir, args.language)
    resolver = FollowerResolver(strings)
    plugin_display: dict[str, str] = {}

    for plugin in load_order:
        plugin_display[plugin.lower()] = plugin
        try:
            parser = PluginParser(args.data_dir / plugin)
            resolver.add_plugin_records(parser.parse_npcs())
            report.plugins_parsed += 1
        except Exception as exc:  # malformed plugin should not abort the run
            report.plugins_failed.append(f"{plugin}: {exc}")
            if args.verbose:
                print(f"  [warn] failed to parse {plugin}: {exc}")

    followers = resolver.followers()
    report.followers_total = len(followers)
    print(f"Scanned {resolver.npc_count} NPC records, found {len(followers)} followers")

    mugshots = MugshotIndex(args.mugshot_dir, args.modlist_txt)
    writer = ThumbnailWriter(args.output_dir, dry_run=args.dry_run)
    used_stems: dict[str, Follower] = {}

    for follower in followers:
        source_plugin = plugin_display.get(follower.form_key[0], follower.form_key[0])
        label = f"{follower.name or follower.editor_id or '?'} " \
                f"[{source_plugin}:{follower.form_key[1]:06X}]"
        best = mugshots.best_for(follower.form_key)
        if best is None:
            report.missing.append(label)
            continue
        mod_name, source_path = best

        name_stem = sanitize_filename(follower.name) if follower.name else None
        stems: list[str] = []
        if name_stem is None:
            stems.append(formid_stem(follower.form_key, source_plugin))
        elif name_stem.lower() in used_stems:
            report.duplicates.append(label)
            stems.append(formid_stem(follower.form_key, source_plugin))
        else:
            stems.append(name_stem)

        for stem in stems:
            key = stem.lower()
            if key in used_stems:
                continue
            used_stems[key] = follower
            destination = writer.write(source_path, stem)
            report.written.append(f"{destination.name}  <-  {mod_name}  ({label})")
            if args.verbose:
                extra = mugshots.candidate_count(follower.form_key)
                print(f"  {destination.name} <- {mod_name} "
                      f"({extra} candidate(s)) {label}")
    return report


def print_report(report: RunReport, dry_run: bool) -> None:
    action = "Would write" if dry_run else "Wrote"
    print()
    print("=" * 70)
    print(f"{action} {len(report.written)} thumbnail(s):")
    for line in report.written:
        print(f"  {line}")
    if report.duplicates:
        print(f"\nDuplicate display names (written as Plugin-FormID instead):")
        for line in report.duplicates:
            print(f"  {line}")
    if report.missing:
        print(f"\nFollowers without a mugshot in the cache ({len(report.missing)}):")
        for line in report.missing:
            print(f"  {line}")
    if report.plugins_failed:
        print(f"\nPlugins that failed to parse ({len(report.plugins_failed)}):")
        for line in report.plugins_failed:
            print(f"  {line}")
    print("=" * 70)
    print(
        f"Summary: {report.followers_total} followers | "
        f"{len(report.written)} thumbnails | {len(report.missing)} missing mugshots"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate PartySheet portrait thumbnails for follower NPCs "
        "from the NPC Plugin Chooser mugshot cache."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="Skyrim SE Data folder")
    parser.add_argument("--plugins-txt", type=Path, default=DEFAULT_PLUGINS_TXT,
                        help="Active load order file (plugins.txt)")
    parser.add_argument("--modlist-txt", type=Path, default=DEFAULT_MODLIST_TXT,
                        help="Mod list used to prioritize mugshot sources")
    parser.add_argument("--mugshot-dir", type=Path, default=DEFAULT_MUGSHOT_DIR,
                        help="NPC Plugin Chooser mugshot cache folder")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="PartySheet Portraits output folder")
    parser.add_argument("--language", default="english",
                        help="Localized strings language (default: english)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be generated without writing files")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    for path, label in [
        (args.data_dir, "Data folder"),
        (args.plugins_txt, "plugins.txt"),
        (args.mugshot_dir, "mugshot folder"),
    ]:
        if not path.exists():
            print(f"Error: {label} not found: {path}", file=sys.stderr)
            return 1
    report = run(args)
    print_report(report, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
