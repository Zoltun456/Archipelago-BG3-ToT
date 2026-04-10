from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import textwrap
import zipfile
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "build_config.json"
UNLOCK_CATALOG_PATH = ROOT / "config" / "trials_unlock_catalog.json"
APWORLD_SOURCE_DIR = ROOT / "src" / "apworld" / "bg3tot"
ARCHIPELAGO_METADATA_PATH = APWORLD_SOURCE_DIR / "archipelago.json"
PACKAGED_UNLOCK_CATALOG_PATH = APWORLD_SOURCE_DIR / "trials_unlock_catalog.json"
APWORLD_PACKAGE_NAME = "bg3tot"
APWORLD_FILENAME = "bg3tot.apworld"
APWORLD_CONTAINER_VERSION = 7
APWORLD_COMPATIBLE_VERSION = 7

REPO_TRIALS_MOD_SOURCE_DIR = ROOT / "src" / "archipelago_tot_mod" / "source"
BRANDING_ASSET_DIR = ROOT / "assets" / "archipelago_branding"
TEXCONV_PATH = ROOT / "tools" / "texconv.exe"

ARCHIPELAGO_ATLAS_TEXTURE_SIZE = 512
ARCHIPELAGO_ATLAS_ICON_SIZE = 64
ARCHIPELAGO_ATLAS_UUID = "aa417c69-e69a-f1ef-5a8d-65b7b5d4e195"
ARCHIPELAGO_ATLAS_DDS_NAME = "Icons_ArchipelagoTrials.dds"
ARCHIPELAGO_ATLAS_LSX_NAME = "Icons_ArchipelagoTrials.lsx"
ARCHIPELAGO_ATLAS_SPECS = (
    {
        "icon_key": "original-logo",
        "source": BRANDING_ASSET_DIR / "original-logo.png",
        "slot_x": 0,
        "slot_y": 0,
    },
    {
        "icon_key": "ap_trials_icon_blue_001",
        "source": BRANDING_ASSET_DIR / "blue-icon.png",
        "slot_x": 1,
        "slot_y": 0,
    },
    {
        "icon_key": "ap_trials_icon_color_001",
        "source": BRANDING_ASSET_DIR / "color-icon.png",
        "slot_x": 2,
        "slot_y": 0,
    },
)

DEFAULT_FINAL_MOD = {
    "module_folder": "CombatMod",
    "display_name": "Archipelago - Trials of Tav",
    "pak_name": "ArchipelagoToT.pak",
    "author": "Zoltun",
    "description": "Trials of Tav - Reloaded bundled with the Archipelago Trials integration.",
    "publish_handle": "",
}

ADVANCED_TT_SPELLS_UUID = "fa49db03-caa7-49c8-7c76-e6c38b60267a"
ADVANCED_TT_SPELLS_MODULE_FOLDER = f"AdvancedTTSpells_{ADVANCED_TT_SPELLS_UUID}"
ADVANCED_TT_SPELLS_DEPENDENCY = {
    "folder": ADVANCED_TT_SPELLS_MODULE_FOLDER,
    "md5": "fa19e41de1e324ab801d286efdc89b3c",
    "name": "AdvancedTTSpells",
    "publish_handle": "0",
    "uuid": ADVANCED_TT_SPELLS_UUID,
    "version64": "36169553834672129",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents.rstrip() + "\n", encoding="utf-8")


def snake_case_identifier(value: str) -> str:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value))
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized.lower()


def unlock_copies_option_name(unlock_id: str) -> str:
    return f"{snake_case_identifier(unlock_id)}_copies"


def iter_sample_unlock_option_lines(sample_player: dict[str, Any]) -> list[str]:
    unlock_lines: list[str] = []
    unlock_catalog = load_json(UNLOCK_CATALOG_PATH)

    for unlock in unlock_catalog:
        unlock_id = str(unlock["id"])
        copies = max(1, int(unlock.get("copies", 1)))
        if copies <= 1:
            continue
        option_name = unlock_copies_option_name(unlock_id)
        value = int(sample_player.get(option_name, copies))
        unlock_lines.append(f"  {option_name}: {value}")

    unlock_lines.append(
        f"  include_equipment_fillers: {str(bool(sample_player.get('include_equipment_fillers', True))).lower()}"
    )
    return unlock_lines


def patch_once(contents: str, needle: str, replacement: str, file_label: str) -> str:
    if needle not in contents:
        raise ValueError(f"Could not find expected patch anchor in {file_label}")
    return contents.replace(needle, replacement, 1)


def slugify_filename(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    slug = slug.strip(".-")
    return slug or "release"


def release_version_to_version64(version_text: str) -> str:
    parts = str(version_text or "").strip().split(".")
    if len(parts) not in {3, 4}:
        raise ValueError(
            f"Release version '{version_text}' must use 'major.minor.patch' or 'major.minor.patch.build'."
        )

    try:
        major, minor, revision, build = [int(part) for part in (*parts[:3], *(parts[3:] or ["0"]))]
    except ValueError as exc:
        raise ValueError(f"Release version '{version_text}' must contain only numeric components.") from exc

    limits = {
        "major": (major, 0xFF),
        "minor": (minor, 0xFF),
        "revision": (revision, 0xFFFF),
        "build": (build, 0x7FFFFFFF),
    }
    for label, (value, maximum) in limits.items():
        if value < 0 or value > maximum:
            raise ValueError(f"Release version component '{label}'={value} is out of range (0-{maximum}).")

    version64 = ((major << 55) | (minor << 47) | (revision << 31) | build)
    return str(version64)


def normalize_config(config: dict[str, Any]) -> bool:
    changed = False

    final_mod = dict(DEFAULT_FINAL_MOD)
    final_mod.update(config.get("final_mod", {}))
    if config.get("final_mod") != final_mod:
        config["final_mod"] = final_mod
        changed = True

    release_version = config["final_mod"].get("release_version")
    if release_version:
        publish_release_version = config["final_mod"].get("publish_release_version") or release_version
        version64 = release_version_to_version64(str(release_version))
        publish_version64 = release_version_to_version64(str(publish_release_version))
        if config["final_mod"].get("version64") != version64:
            config["final_mod"]["version64"] = version64
            changed = True
        if config["final_mod"].get("publish_version64") != publish_version64:
            config["final_mod"]["publish_version64"] = publish_version64
            changed = True

    upstream = config.setdefault("upstream", {})
    if "bg3_mod_repo" in upstream:
        del upstream["bg3_mod_repo"]
        changed = True
    if "bg3_mod_ref" in upstream:
        del upstream["bg3_mod_ref"]
        changed = True

    sample_player = config.setdefault("sample_player", {})
    if "sync_method" in sample_player:
        del sample_player["sync_method"]
        changed = True

    test_bundle = config.setdefault("test_bundle", {})
    for key in ("divine_path", "trials_mod_source"):
        if key not in test_bundle:
            test_bundle[key] = ""
            changed = True
    if "attspells_mod_source" in test_bundle:
        del test_bundle["attspells_mod_source"]
        changed = True

    return changed


def sync_archipelago_world_version(config: dict[str, Any]) -> bool:
    release_version = str(config.get("final_mod", {}).get("release_version", "") or "").strip()
    if not release_version:
        return False

    metadata = load_json(ARCHIPELAGO_METADATA_PATH)
    if metadata.get("world_version") == release_version:
        return False

    metadata["world_version"] = release_version
    dump_json(ARCHIPELAGO_METADATA_PATH, metadata)
    return True


def sync_unlock_catalog() -> bool:
    source_contents = UNLOCK_CATALOG_PATH.read_text(encoding="utf-8")
    if PACKAGED_UNLOCK_CATALOG_PATH.exists():
        packaged_contents = PACKAGED_UNLOCK_CATALOG_PATH.read_text(encoding="utf-8")
        if packaged_contents == source_contents:
            return False

    PACKAGED_UNLOCK_CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PACKAGED_UNLOCK_CATALOG_PATH.write_text(source_contents, encoding="utf-8")
    return True


def write_packaged_apworld_manifest(staged_world_dir: Path) -> None:
    metadata = load_json(staged_world_dir / "archipelago.json")
    metadata["version"] = APWORLD_CONTAINER_VERSION
    metadata["compatible_version"] = APWORLD_COMPATIBLE_VERSION
    dump_json(staged_world_dir / "archipelago.json", metadata)


def render_sample_yaml(config: dict[str, Any]) -> str:
    sample = config["sample_player"]
    trap_lines = "\n".join(f"    - {trap}" for trap in sample["enabled_traps"])
    unlock_option_lines = "\n".join(iter_sample_unlock_option_lines(sample))
    return f"""name: {sample['name']}
description: {sample['description']}
game: {sample['game']}

{sample['game']}:
  death_link: {str(bool(sample.get('death_link', False))).lower()}
  death_link_trigger: {sample.get('death_link_trigger', 'full_party_wipe')}
  death_link_punishment: {sample.get('death_link_punishment', 'kill_all_party_members')}
  goal: {sample['goal']}
  goal_clear_target: {sample['goal_clear_target']}
  goal_rogue_score_target: {sample['goal_rogue_score_target']}
  goal_ng_plus_fragment_gate_percent: {sample.get('goal_ng_plus_fragment_gate_percent', 0)}
  goal_ng_plus_price: {sample.get('goal_ng_plus_price', 3000)}
  clear_check_count: {sample['clear_check_count']}
  clear_check_interval: {sample['clear_check_interval']}
  kill_check_count: {sample['kill_check_count']}
  kill_check_interval: {sample['kill_check_interval']}
  perfect_check_count: {sample['perfect_check_count']}
  perfect_check_interval: {sample['perfect_check_interval']}
  roguescore_check_count: {sample['roguescore_check_count']}
  roguescore_check_interval: {sample['roguescore_check_interval']}
  progressive_shop: {str(bool(sample.get('progressive_shop', True))).lower()}
  progressive_shop_unlock_rate: {sample.get('progressive_shop_unlock_rate', 10)}
  shop_check_count: {sample['shop_check_count']}
  shop_price_minimum: {sample['shop_price_minimum']}
  shop_price_maximum: {sample['shop_price_maximum']}
  vanilla_pixie_blessing_in_shop: {str(bool(sample.get('vanilla_pixie_blessing_in_shop', False))).lower()}
  permanent_buff_target: {sample.get('permanent_buff_target', 'random_party_member')}
{unlock_option_lines}
  traps_percentage: {sample['traps_percentage']}
  enabled_traps:
{trap_lines}
"""


def ensure_git_clone(target: Path, repo_url: str, ref: str, refresh: bool) -> None:
    if refresh and target.exists():
        shutil.rmtree(target)

    if target.exists():
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", ref, repo_url, str(target)],
        check=True,
        cwd=ROOT,
    )


def stage_trials_apworld(staged_world_dir: Path) -> None:
    if staged_world_dir.exists():
        shutil.rmtree(staged_world_dir)
    shutil.copytree(APWORLD_SOURCE_DIR, staged_world_dir)
    write_packaged_apworld_manifest(staged_world_dir)


def zip_directory(source_dir: Path, archive_path: Path, root_name: str) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_handle:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                arcname = Path(root_name) / file_path.relative_to(source_dir)
                zip_handle.write(file_path, arcname.as_posix())


def build_release_archive(
    config: dict[str, Any],
    archive_path: Path,
    release_files: list[tuple[Path, str]],
) -> str:
    root_name = slugify_filename(config["project_name"])
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_handle:
        for source_path, relative_name in release_files:
            if not source_path.exists():
                raise FileNotFoundError(f"Release archive source file missing: {source_path}")
            arcname = Path(root_name) / relative_name
            zip_handle.write(source_path, arcname.as_posix())
    return str(archive_path.resolve())


def copy_release_asset(source_path: Path, destination_path: Path) -> str:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)
    return str(destination_path.resolve())


def iter_divine_candidates(config: dict[str, Any]) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add(label: str, raw_path: str | Path | None) -> None:
        if not raw_path:
            return
        candidate = Path(raw_path).expanduser()
        normalized = str(candidate).lower()
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append((label, candidate))

    configured_path = config.get("test_bundle", {}).get("divine_path", "")
    if configured_path:
        add("config:test_bundle.divine_path", configured_path)

    for env_var in ("BG3_TRIALS_DIVINE_PATH", "DIVINE_PATH"):
        if os.environ.get(env_var):
            add(f"env:{env_var}", os.environ[env_var])

    path_hit = shutil.which("Divine.exe")
    if path_hit:
        add("PATH:Divine.exe", path_hit)

    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    appdata = Path(os.environ.get("APPDATA", ""))
    user_profile = Path(os.environ.get("USERPROFILE", ""))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))

    common_candidates = [
        ROOT / "tools" / "Divine.exe",
        ROOT / "third_party" / "Divine.exe",
        ROOT / ".tools" / "Divine.exe",
        program_files / "LSLib" / "Divine.exe",
        program_files_x86 / "LSLib" / "Divine.exe",
        local_appdata / "BG3ModManager" / "Divine.exe",
        local_appdata / "Larian Studios" / "BG3ModManager" / "Divine.exe",
        local_appdata / "Larian Studios" / "Baldur's Gate 3" / "ModManager" / "Divine.exe",
        local_appdata / "Programs" / "BG3 Mod Manager" / "Divine.exe",
        appdata / "BG3ModManager" / "Divine.exe",
        user_profile / "Downloads" / "Divine.exe",
        user_profile / "Downloads" / "Tools" / "Divine.exe",
    ]
    for candidate in common_candidates:
        add("common", candidate)

    return candidates


def resolve_divine_path(config: dict[str, Any]) -> dict[str, str | bool]:
    for source, candidate in iter_divine_candidates(config):
        if candidate.exists():
            return {
                "found": True,
                "path": str(candidate.resolve()),
                "source": source,
            }

    return {
        "found": False,
        "path": "",
        "source": "",
    }


def iter_trials_mod_candidates(config: dict[str, Any]) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add(label: str, raw_path: str | Path | None) -> None:
        if not raw_path:
            return
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        normalized = str(candidate).lower()
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append((label, candidate))

    configured_source = config.get("test_bundle", {}).get("trials_mod_source", "")
    if configured_source:
        add("config:test_bundle.trials_mod_source", configured_source)

    for env_var in ("BG3_TRIALS_MOD_SOURCE", "COMBATMOD_SOURCE"):
        if os.environ.get(env_var):
            add(f"env:{env_var}", os.environ[env_var])

    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    user_profile = Path(os.environ.get("USERPROFILE", ""))
    common_candidates = [
        REPO_TRIALS_MOD_SOURCE_DIR,
        ROOT / ".cache" / "combatmod_extract",
        local_appdata / "Larian Studios" / "Baldur's Gate 3" / "Mods" / "CombatMod.pak",
        ROOT / "CombatMod.pak",
        user_profile / "Downloads" / "CombatMod.pak",
    ]
    for candidate in common_candidates:
        add("common", candidate)

    vortex_root = user_profile / "AppData" / "Roaming" / "Vortex" / "baldursgate3" / "mods"
    if vortex_root.exists():
        for candidate in sorted(vortex_root.glob("**/CombatMod.pak")):
            add("vortex_staging", candidate)

    return candidates


def is_valid_trials_mod_source(candidate: Path, module_folder: str) -> bool:
    if not candidate.exists():
        return False
    if candidate.is_file():
        return candidate.suffix.lower() == ".pak"
    if not candidate.is_dir():
        return False

    mods_root = candidate / "Mods" / module_folder
    public_root = candidate / "Public" / module_folder
    return mods_root.exists() and public_root.exists()


def resolve_trials_mod_source(config: dict[str, Any]) -> dict[str, str | bool]:
    module_folder = str(config.get("final_mod", {}).get("module_folder", "CombatMod"))
    for source, candidate in iter_trials_mod_candidates(config):
        if is_valid_trials_mod_source(candidate, module_folder):
            return {
                "found": True,
                "path": str(candidate.resolve()),
                "source": source,
            }

    return {
        "found": False,
        "path": "",
        "source": "",
    }


def extract_pak(divine_path: str, source_pak: Path, destination_dir: Path) -> None:
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            divine_path,
            "-g",
            "bg3",
            "-a",
            "extract-package",
            "-s",
            str(source_pak),
            "-d",
            str(destination_dir),
        ],
        check=True,
        cwd=ROOT,
    )


def convert_resource(divine_path: str, source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            divine_path,
            "-g",
            "bg3",
            "-a",
            "convert-resource",
            "-s",
            str(source_path),
            "-d",
            str(destination_path),
        ],
        check=True,
        cwd=ROOT,
    )


def remove_path_if_exists(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def atlas_uv_bounds(slot_x: int, slot_y: int) -> tuple[float, float, float, float]:
    texture_size = float(ARCHIPELAGO_ATLAS_TEXTURE_SIZE)
    icon_size = float(ARCHIPELAGO_ATLAS_ICON_SIZE)
    u1 = ((slot_x * icon_size) + 0.5) / texture_size
    u2 = (((slot_x + 1) * icon_size) - 0.5) / texture_size
    v1 = ((slot_y * icon_size) + 0.5) / texture_size
    v2 = (((slot_y + 1) * icon_size) - 0.5) / texture_size
    return u1, u2, v1, v2


def render_archipelago_atlas(texture_path: str, uuid: str = ARCHIPELAGO_ATLAS_UUID) -> str:
    icon_nodes = []
    for spec in ARCHIPELAGO_ATLAS_SPECS:
        u1, u2, v1, v2 = atlas_uv_bounds(spec["slot_x"], spec["slot_y"])
        icon_nodes.append(
            f"""                <node id="IconUV">
                    <attribute id="MapKey" type="FixedString" value="{escape(spec['icon_key'])}"/>
                    <attribute id="U1" type="float" value="{u1:.10f}"/>
                    <attribute id="U2" type="float" value="{u2:.8f}"/>
                    <attribute id="V1" type="float" value="{v1:.10f}"/>
                    <attribute id="V2" type="float" value="{v2:.8f}"/>
                </node>"""
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<save>
    <version major="4" minor="8" revision="0" build="400"/>
    <region id="IconUVList">
        <node id="root">
            <children>
{chr(10).join(icon_nodes)}
            </children>
        </node>
    </region>
    <region id="TextureAtlasInfo">
        <node id="root">
            <children>
                <node id="TextureAtlasIconSize">
                    <attribute id="Height" type="int32" value="{ARCHIPELAGO_ATLAS_ICON_SIZE}"/>
                    <attribute id="Width" type="int32" value="{ARCHIPELAGO_ATLAS_ICON_SIZE}"/>
                </node>
                <node id="TextureAtlasPath">
                    <attribute id="Path" type="string" value="{escape(texture_path)}"/>
                    <attribute id="UUID" type="FixedString" value="{escape(uuid)}"/>
                </node>
                <node id="TextureAtlasTextureSize">
                    <attribute id="Height" type="int32" value="{ARCHIPELAGO_ATLAS_TEXTURE_SIZE}"/>
                    <attribute id="Width" type="int32" value="{ARCHIPELAGO_ATLAS_TEXTURE_SIZE}"/>
                </node>
            </children>
        </node>
    </region>
</save>"""


def render_texture_bank_resource(name: str, source_file: str, uuid: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<save>
    <version major="4" minor="0" revision="4" build="602" />
    <region id="TextureBank">
        <node id="TextureBank">
            <children>
                <node id="Resource">
                    <attribute id="ID" type="FixedString" value="{escape(uuid)}" />
                    <attribute id="Localized" type="bool" value="False" />
                    <attribute id="Name" type="LSString" value="{escape(name)}" />
                    <attribute id="SRGB" type="bool" value="True" />
                    <attribute id="SourceFile" type="LSString" value="{escape(source_file)}" />
                    <attribute id="Streaming" type="bool" value="True" />
                    <attribute id="Template" type="FixedString" value="Icons_Items" />
                    <attribute id="Type" type="int32" value="0" />
                    <attribute id="_OriginalFileVersion_" type="int64" value="144115188075855873" />
                </node>
            </children>
        </node>
    </region>
</save>"""


def compose_archipelago_atlas_png(atlas_png_path: Path) -> None:
    atlas_png_path.parent.mkdir(parents=True, exist_ok=True)
    script = [
        "Add-Type -AssemblyName System.Drawing",
        f"$bitmap = New-Object System.Drawing.Bitmap {ARCHIPELAGO_ATLAS_TEXTURE_SIZE}, {ARCHIPELAGO_ATLAS_TEXTURE_SIZE}",
        "$graphics = [System.Drawing.Graphics]::FromImage($bitmap)",
        "$graphics.Clear([System.Drawing.Color]::FromArgb(0, 0, 0, 0))",
        "$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic",
        "$graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality",
        "$graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality",
    ]

    for spec in ARCHIPELAGO_ATLAS_SPECS:
        slot_x = int(spec["slot_x"]) * ARCHIPELAGO_ATLAS_ICON_SIZE
        slot_y = int(spec["slot_y"]) * ARCHIPELAGO_ATLAS_ICON_SIZE
        source_png = Path(spec["source"])
        if not source_png.exists():
            raise FileNotFoundError(f"Missing icon source: {source_png}")
        script.extend(
            [
                f'$img = [System.Drawing.Image]::FromFile("{str(source_png.resolve()).replace("\\", "\\\\")}")',
                (
                    "$graphics.DrawImage($img, "
                    f"(New-Object System.Drawing.Rectangle {slot_x}, {slot_y}, {ARCHIPELAGO_ATLAS_ICON_SIZE}, {ARCHIPELAGO_ATLAS_ICON_SIZE}))"
                ),
                "$img.Dispose()",
            ]
        )

    script.extend(
        [
            (
                '$bitmap.Save("'
                + str(atlas_png_path.resolve()).replace("\\", "\\\\")
                + '", [System.Drawing.Imaging.ImageFormat]::Png)'
            ),
            "$graphics.Dispose()",
            "$bitmap.Dispose()",
        ]
    )

    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "\n".join(script)],
        check=True,
        cwd=ROOT,
    )


def patch_combatmod_custom_atlas_assets(staged_mod_dir: Path, divine_path: str, module_folder: str) -> None:
    if not TEXCONV_PATH.exists():
        raise FileNotFoundError(f"Missing required tool: {TEXCONV_PATH}")

    public_root = staged_mod_dir / "Public" / module_folder
    icons_dir = public_root / "Assets" / "Textures" / "Icons"
    gui_dir = public_root / "GUI"
    ui_dir = public_root / "Content" / "UI" / "[PAK]_UI"
    icons_dir.mkdir(parents=True, exist_ok=True)
    gui_dir.mkdir(parents=True, exist_ok=True)
    ui_dir.mkdir(parents=True, exist_ok=True)

    atlas_png_path = icons_dir / "Icons_ArchipelagoTrials.png"
    compose_archipelago_atlas_png(atlas_png_path)
    subprocess.run(
        [
            str(TEXCONV_PATH),
            "-f",
            "DXT5",
            "-dx9",
            "-w",
            str(ARCHIPELAGO_ATLAS_TEXTURE_SIZE),
            "-h",
            str(ARCHIPELAGO_ATLAS_TEXTURE_SIZE),
            "-m",
            "0",
            "-y",
            "-o",
            str(icons_dir),
            str(atlas_png_path),
        ],
        check=True,
        cwd=ROOT,
    )

    generated_dds = icons_dir / "Icons_ArchipelagoTrials.dds"
    generated_dds_upper = icons_dir / "Icons_ArchipelagoTrials.DDS"
    if generated_dds_upper.exists() and not generated_dds.exists():
        generated_dds_upper.rename(generated_dds)

    write_text(
        gui_dir / ARCHIPELAGO_ATLAS_LSX_NAME,
        render_archipelago_atlas(texture_path=f"Assets/Textures/Icons/{ARCHIPELAGO_ATLAS_DDS_NAME}"),
    )
    merged_lsx_path = ui_dir / "_merged.lsx"
    write_text(
        merged_lsx_path,
        render_texture_bank_resource(
            name="Icons_ArchipelagoTrials",
            source_file=f"Public/{module_folder}/Assets/Textures/Icons/{ARCHIPELAGO_ATLAS_DDS_NAME}",
            uuid=ARCHIPELAGO_ATLAS_UUID,
        ),
    )
    convert_resource(divine_path, merged_lsx_path, ui_dir / "_merged.lsf")


def set_xml_attribute(node: ET.Element | None, attribute_id: str, value: str) -> None:
    if node is None:
        return
    for attribute in node.findall("attribute"):
        if attribute.attrib.get("id") == attribute_id:
            attribute.set("value", value)
            return


def upsert_xml_attribute(node: ET.Element | None, attribute_id: str, attr_type: str, value: str) -> None:
    if node is None:
        return
    for attribute in node.findall("attribute"):
        if attribute.attrib.get("id") == attribute_id:
            attribute.set("type", attr_type)
            attribute.set("value", value)
            return
    new_attribute = ET.Element("attribute", {"id": attribute_id, "type": attr_type, "value": value})
    children = node.find("children")
    if children is None:
        node.append(new_attribute)
        return

    insert_at = list(node).index(children)
    node.insert(insert_at, new_attribute)


def get_xml_attribute(node: ET.Element | None, attribute_id: str, default: str = "") -> str:
    if node is None:
        return default
    for attribute in node.findall("attribute"):
        if attribute.attrib.get("id") == attribute_id:
            return attribute.attrib.get("value", default)
    return default


def get_or_create_children(node: ET.Element) -> ET.Element:
    children = node.find("children")
    if children is None:
        children = ET.SubElement(node, "children")
    return children


def ensure_child_node(parent_node: ET.Element, child_id: str) -> ET.Element:
    children = get_or_create_children(parent_node)
    for child in children.findall("node"):
        if child.attrib.get("id") == child_id:
            return child
    return ET.SubElement(children, "node", {"id": child_id})


def dedupe_dependencies(dependencies: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for dependency in dependencies:
        key = (dependency.get("uuid") or dependency.get("folder") or dependency.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(dependency)
    return deduped


def write_dependency_nodes(config_root: ET.Element, dependencies: list[dict[str, str]]) -> None:
    dependency_entries = dedupe_dependencies(dependencies)
    dependencies_node = ensure_child_node(config_root, "Dependencies")
    dependency_children = get_or_create_children(dependencies_node)
    for child in list(dependency_children):
        dependency_children.remove(child)

    for dependency in dependency_entries:
        dependency_node = ET.SubElement(dependency_children, "node", {"id": "ModuleShortDesc"})
        upsert_xml_attribute(dependency_node, "Folder", "LSString", dependency.get("folder", ""))
        upsert_xml_attribute(dependency_node, "MD5", "LSString", dependency.get("md5", ""))
        upsert_xml_attribute(dependency_node, "Name", "LSString", dependency.get("name", ""))
        upsert_xml_attribute(
            dependency_node,
            "PublishHandle",
            "uint64",
            dependency.get("publish_handle", "0"),
        )
        upsert_xml_attribute(dependency_node, "UUID", "guid", dependency.get("uuid", ""))
        upsert_xml_attribute(dependency_node, "Version64", "int64", dependency.get("version64", "0"))


def remove_xml_attribute(node: ET.Element | None, attribute_id: str) -> None:
    if node is None:
        return
    for attribute in list(node.findall("attribute")):
        if attribute.attrib.get("id") == attribute_id:
            node.remove(attribute)


def patch_mod_meta(
    meta_path: Path,
    final_mod: dict[str, Any],
    dependencies: list[dict[str, str]] | None = None,
    patch_module_info: bool = True,
    patch_publish_handle: bool = True,
) -> None:
    tree = ET.parse(meta_path)
    root = tree.getroot()
    module_info = root.find(".//node[@id='ModuleInfo']")
    publish_version = root.find(".//node[@id='PublishVersion']")
    config_root = root.find(".//region[@id='Config']/node[@id='root']")

    if patch_module_info:
        set_xml_attribute(module_info, "Author", str(final_mod.get("author", "")))
        set_xml_attribute(module_info, "Description", str(final_mod.get("description", "")))
        set_xml_attribute(module_info, "Name", str(final_mod.get("display_name", "")))

        version64 = str(final_mod.get("version64", ""))
        publish_version64 = str(final_mod.get("publish_version64", version64))
        publish_handle = str(final_mod.get("publish_handle", "") or "").strip()
        if version64:
            set_xml_attribute(module_info, "Version64", version64)
        if publish_version64:
            set_xml_attribute(publish_version, "Version64", publish_version64)
        if patch_publish_handle and publish_handle:
            upsert_xml_attribute(module_info, "PublishHandle", "uint64", publish_handle)
        elif not patch_publish_handle:
            remove_xml_attribute(module_info, "PublishHandle")
    if dependencies is not None and config_root is not None:
        write_dependency_nodes(config_root, dependencies)

    meta_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(meta_path, encoding="utf-8", xml_declaration=True)


def read_mod_meta(meta_path: Path) -> dict[str, str]:
    tree = ET.parse(meta_path)
    root = tree.getroot()
    module_info = root.find(".//node[@id='ModuleInfo']")
    return {
        "author": get_xml_attribute(module_info, "Author"),
        "description": get_xml_attribute(module_info, "Description"),
        "folder": get_xml_attribute(module_info, "Folder"),
        "md5": get_xml_attribute(module_info, "MD5"),
        "name": get_xml_attribute(module_info, "Name"),
        "publish_handle": get_xml_attribute(module_info, "PublishHandle", "0"),
        "uuid": get_xml_attribute(module_info, "UUID"),
        "version64": get_xml_attribute(module_info, "Version64"),
    }


def read_additional_mod_metas(mods_root: Path, primary_module_folder: str) -> list[dict[str, str]]:
    metas: list[dict[str, str]] = []
    if not mods_root.exists():
        return metas

    for meta_path in sorted(mods_root.glob("*/meta.lsx")):
        mod_meta = read_mod_meta(meta_path)
        if mod_meta.get("folder") == primary_module_folder:
            continue
        metas.append(mod_meta)
    return metas


def read_dependency_nodes_from_meta(meta_path: Path) -> list[dict[str, str]]:
    tree = ET.parse(meta_path)
    root = tree.getroot()
    dependencies_root = root.find(".//region[@id='Config']/node[@id='root']/children/node[@id='Dependencies']/children")
    if dependencies_root is None:
        return []

    dependencies: list[dict[str, str]] = []
    for dependency_node in dependencies_root.findall("node[@id='ModuleShortDesc']"):
        dependencies.append(
            {
                "folder": get_xml_attribute(dependency_node, "Folder"),
                "md5": get_xml_attribute(dependency_node, "MD5"),
                "name": get_xml_attribute(dependency_node, "Name"),
                "publish_handle": get_xml_attribute(dependency_node, "PublishHandle", "0"),
                "uuid": get_xml_attribute(dependency_node, "UUID"),
                "version64": get_xml_attribute(dependency_node, "Version64"),
            }
        )
    return dependencies


def list_child_directories(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(entry.name for entry in root.iterdir() if entry.is_dir())


def validate_staged_final_mod(staged_mod_dir: Path, final_mod: dict[str, Any]) -> dict[str, Any]:
    module_folder = str(final_mod["module_folder"])
    mods_directories = list_child_directories(staged_mod_dir / "Mods")
    public_directories = list_child_directories(staged_mod_dir / "Public")

    for root_label, directories in (("Mods", mods_directories), ("Public", public_directories)):
        unexpected = [entry for entry in directories if entry != module_folder]
        if unexpected:
            raise ValueError(
                f"Staged final mod contains unexpected {root_label} modules: {', '.join(unexpected)}. "
                f"Expected only '{module_folder}'."
            )
        if root_label == "Mods" and module_folder not in directories:
            raise ValueError(
                f"Staged final mod is missing its primary Mods/{module_folder} directory."
            )

    mod_meta = read_mod_meta(staged_mod_dir / "Mods" / module_folder / "meta.lsx")
    if str(mod_meta.get("folder", "")) != module_folder:
        raise ValueError(
            f"Staged final mod metadata is missing the expected module folder '{module_folder}'."
        )
    expected_meta = {
        "author": str(final_mod.get("author", "")),
        "description": str(final_mod.get("description", "")),
        "name": str(final_mod.get("display_name", "")),
        "version64": str(final_mod.get("version64", "")),
    }
    for field_name, expected_value in expected_meta.items():
        if expected_value and str(mod_meta.get(field_name, "")) != expected_value:
            raise ValueError(
                f"Staged final mod metadata field '{field_name}' was '{mod_meta.get(field_name, '')}', "
                f"expected '{expected_value}'."
            )

    dependency_nodes = read_dependency_nodes_from_meta(staged_mod_dir / "Mods" / module_folder / "meta.lsx")
    if dependency_nodes:
        raise ValueError(
            "Staged final mod should not ship runtime dependency nodes; external dependencies must be installed separately."
        )

    return {
        "mods_directories": mods_directories,
        "public_directories": public_directories,
        "meta": mod_meta,
        "dependencies": dependency_nodes,
    }


DEPENDENCY_VERSION_HELPER = """-- The upstream Trials scripts sometimes compare dependency versions as one exact tuple.
-- We patch those to a minimum-version check so newer compatible releases do not throw false warnings.
local function dependency_version_at_least(version_parts, major, minor, revision, build)
    local normalized = {
        tonumber(version_parts and version_parts[1] or 0) or 0,
        tonumber(version_parts and version_parts[2] or 0) or 0,
        tonumber(version_parts and version_parts[3] or 0) or 0,
        tonumber(version_parts and version_parts[4] or 0) or 0,
    }
    local required = {
        tonumber(major or 0) or 0,
        tonumber(minor or 0) or 0,
        tonumber(revision or 0) or 0,
        tonumber(build or 0) or 0,
    }

    for index = 1, 4 do
        if normalized[index] > required[index] then
            return true
        end
        if normalized[index] < required[index] then
            return false
        end
    end

    return true
end
"""


def patch_dependency_version_checks(lua_root: Path) -> None:
    exact_version_pattern = re.compile(
        r"\(\s*([A-Za-z_][A-Za-z0-9_]*)\.ModVersion\[1\]\s*==\s*(\d+)\s*"
        r"and\s*\1\.ModVersion\[2\]\s*==\s*(\d+)\s*"
        r"and\s*\1\.ModVersion\[3\]\s*==\s*(\d+)\s*"
        r"and\s*\1\.ModVersion\[4\]\s*==\s*(\d+)\s*\)"
    )

    for lua_path in lua_root.rglob("*.lua"):
        contents = lua_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        replacement_count = 0

        def replace_exact_version(match: re.Match[str]) -> str:
            nonlocal replacement_count
            replacement_count += 1
            version_owner = match.group(1)
            return (
                f"dependency_version_at_least({version_owner}.ModVersion, "
                f"{match.group(2)}, {match.group(3)}, {match.group(4)}, {match.group(5)})"
            )

        contents = exact_version_pattern.sub(replace_exact_version, contents)
        if replacement_count == 0:
            continue

        if "local function dependency_version_at_least" not in contents:
            contents = DEPENDENCY_VERSION_HELPER + "\n" + contents.lstrip("\n")

        write_text(lua_path, contents)


def stage_final_mod(
    source: Path,
    staged_mod_dir: Path,
    divine_path: str,
    final_mod: dict[str, Any],
) -> None:
    module_folder = str(final_mod["module_folder"])
    remove_path_if_exists(staged_mod_dir)
    if source.is_dir():
        shutil.copytree(source, staged_mod_dir, dirs_exist_ok=True)
    else:
        extract_pak(divine_path, source, staged_mod_dir)

    public_root = staged_mod_dir / "Public" / module_folder
    mods_root = staged_mod_dir / "Mods" / module_folder

    remove_path_if_exists(mods_root / "ScriptExtender" / "VirtualTextures.json")
    remove_path_if_exists(public_root / "Assets" / "VirtualTextures")
    remove_path_if_exists(public_root / "Assets" / "Textures" / "VTexConfig.xml")
    remove_path_if_exists(public_root / "GUI" / ARCHIPELAGO_ATLAS_LSX_NAME)
    remove_path_if_exists(public_root / "Content" / "UI" / "[PAK]_UI" / "_merged.lsx")
    remove_path_if_exists(public_root / "Content" / "UI" / "[PAK]_UI" / "_merged.lsf")
    remove_path_if_exists(public_root / "Assets" / "Textures" / "Icons" / "Icons_ArchipelagoTrials.png")
    remove_path_if_exists(public_root / "Assets" / "Textures" / "Icons" / ARCHIPELAGO_ATLAS_DDS_NAME)

    patch_dependency_version_checks(mods_root / "ScriptExtender" / "Lua")
    patch_mod_meta(
        mods_root / "meta.lsx",
        final_mod,
        dependencies=None,
        patch_module_info=True,
        patch_publish_handle=False,
    )

    publish_logo_path = mods_root / "mod_publish_logo.png"
    if (BRANDING_ASSET_DIR / "color-icon.png").exists():
        shutil.copy2(BRANDING_ASSET_DIR / "color-icon.png", publish_logo_path)

    patch_combatmod_custom_atlas_assets(staged_mod_dir, divine_path, module_folder)


def build_pak(
    config: dict[str, Any],
    staged_unpacked_mod_dir: Path,
    pak_destination: Path,
) -> tuple[str | None, dict[str, str | bool]]:
    divine_info = resolve_divine_path(config)
    if not divine_info["found"]:
        return None, divine_info

    pak_destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(divine_info["path"]),
            "-g",
            "bg3",
            "-a",
            "create-package",
            "-s",
            str(staged_unpacked_mod_dir),
            "-d",
            str(pak_destination),
        ],
        check=True,
        cwd=ROOT,
    )
    return str(pak_destination.resolve()), divine_info


def build_test_bundle(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    output_dir = ROOT / config["output_dir"]
    cache_dir = ROOT / config["cache_dir"]
    staged_mod_dir: Path | None = None
    final_mod_validation: dict[str, Any] | None = None

    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    final_mod = config["final_mod"]
    final_pak_path = output_dir / "bg3_mods" / str(final_mod["pak_name"])
    legacy_dependency_pak_path = output_dir / "bg3_mods" / f"{ADVANCED_TT_SPELLS_MODULE_FOLDER}.pak"
    remove_path_if_exists(output_dir / "bg3_mods" / "ArchipelagoToT_unpacked")
    remove_path_if_exists(output_dir / "bg3_mods" / "_bundled_mod_extract")
    remove_path_if_exists(final_pak_path)
    remove_path_if_exists(legacy_dependency_pak_path)
    remove_path_if_exists(output_dir / "staging" / "_dependency_meta_extract")

    divine_info = resolve_divine_path(config)
    trials_mod_info = resolve_trials_mod_source(config)

    staged_world_dir = output_dir / "staging" / APWORLD_PACKAGE_NAME
    stage_trials_apworld(staged_world_dir)
    apworld_path = output_dir / "apworlds" / APWORLD_FILENAME
    zip_directory(staged_world_dir, apworld_path, APWORLD_PACKAGE_NAME)

    artifacts: list[dict[str, str]] = [
        {"kind": "apworld", "path": str(apworld_path.resolve())},
    ]

    if divine_info["found"] and trials_mod_info["found"]:
        staged_mod_dir = output_dir / "bg3_mods" / "ArchipelagoToT_unpacked"
        stage_final_mod(
            Path(str(trials_mod_info["path"])),
            staged_mod_dir,
            str(divine_info["path"]),
            final_mod,
        )
        final_mod_validation = validate_staged_final_mod(staged_mod_dir, final_mod)
        artifacts.append({"kind": "final_mod_unpacked", "path": str(staged_mod_dir.resolve())})
        built_final_pak, _ = build_pak(config, staged_mod_dir, final_pak_path)
        if built_final_pak:
            artifacts.append({"kind": "final_mod_pak", "path": built_final_pak})

    sample_yaml_path = output_dir / "player_yaml" / "bg3_trials_test.yaml"
    write_text(sample_yaml_path, render_sample_yaml(config))
    artifacts.append({"kind": "sample_yaml", "path": str(sample_yaml_path.resolve())})

    install_path = output_dir / "INSTALL.txt"
    instructions = textwrap.dedent(
        f"""
        Archipelago BG3 Trials test bundle

        This release ships as two GitHub assets:
        - {APWORLD_FILENAME}
        - {slugify_filename(config["project_name"])}-test-bundle.zip

        This zip archive contains:
        - {final_mod['pak_name']}
        - bg3_trials_test.yaml

        Brief setup:
        1. Download {APWORLD_FILENAME} from the same release page and put it into your Archipelago custom_worlds folder.
        2. Install the required external BG3 dependencies from the project README, including `AdvancedTTSpells`.
        3. Extract this zip and put `{final_mod['pak_name']}` into your BG3 Mods folder.
        4. In BG3 Mod Manager, enable "AdvancedTTSpells" before "{final_mod['display_name']}", and export the load order.
        5. Launch BG3 and start Trials of Tav as normal.

        For full instructions, troubleshooting, and current notes, read the repository README on GitHub.
        """
    ).strip()
    write_text(install_path, instructions)
    artifacts.append({"kind": "install", "path": str(install_path.resolve())})

    release_dir = output_dir / "release"
    release_bundle_path = output_dir / "release" / f"{slugify_filename(config['project_name'])}-test-bundle.zip"
    release_apworld_path = release_dir / APWORLD_FILENAME
    release_bundle_archive = None
    release_apworld_asset = None
    release_bundle_missing = []
    release_bundle_candidates = [
        (final_pak_path, str(final_mod["pak_name"])),
        (sample_yaml_path, sample_yaml_path.name),
        (install_path, "INSTALL.txt"),
    ]
    required_release_assets = [
        (apworld_path, APWORLD_FILENAME),
        (final_pak_path, str(final_mod["pak_name"])),
    ]
    for source_path, relative_name in required_release_assets:
        if not source_path.exists():
            release_bundle_missing.append(relative_name)

    if not release_bundle_missing:
        release_apworld_asset = copy_release_asset(apworld_path, release_apworld_path)
        artifacts.append({"kind": "release_apworld", "path": release_apworld_asset})
        release_bundle_archive = build_release_archive(config, release_bundle_path, release_bundle_candidates)
        artifacts.append({"kind": "release_zip", "path": release_bundle_archive})

    manifest = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "project": config["project_name"],
        "divine": divine_info,
        "trials_mod_source": trials_mod_info,
        "final_mod_validation": final_mod_validation,
        "artifacts": artifacts,
        "release_bundle": {
            "created": release_bundle_archive is not None,
            "path": release_bundle_archive or str(release_bundle_path.resolve()),
            "apworld_path": release_apworld_asset or str(release_apworld_path.resolve()),
            "missing_required_files": release_bundle_missing,
        },
    }
    dump_json(output_dir / "build_manifest.json", manifest)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Archipelago BG3 Trials test bundle.")
    parser.add_argument(
        "command",
        nargs="?",
        default="build",
        choices=["sync", "build"],
        help="sync normalizes generated config values only; build also creates dist artifacts.",
    )
    parser.add_argument("--clean", action="store_true", help="Delete the dist directory before building.")
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Delete cached upstream repos before cloning fresh copies.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_json(CONFIG_PATH)
    if normalize_config(config):
        dump_json(CONFIG_PATH, config)
    sync_archipelago_world_version(config)
    sync_unlock_catalog()

    if args.command == "sync":
        print("Synced generated config values from config/build_config.json")
        return

    manifest = build_test_bundle(config, args)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
