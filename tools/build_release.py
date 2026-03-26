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
CONFIG_PATH = ROOT / "build_config.json"
UNLOCK_CATALOG_PATH = ROOT / "trials_unlock_catalog.json"
APWORLD_TEMPLATE_DIR = ROOT / "apworld_templates" / "bg3"
APWORLD_PACKAGE_NAME = "bg3tot"
APWORLD_FILENAME = "bg3tot.apworld"

COMPAT_MOD_ROOT = ROOT / "compat_mod"
COMPAT_MOD_META_PATH = COMPAT_MOD_ROOT / "Mods" / "ArchipelagoTrials" / "meta.lsx"
COMPAT_MOD_CONFIG_PATH = COMPAT_MOD_ROOT / "Mods" / "ArchipelagoTrials" / "ScriptExtender" / "Config.json"
COMBATMOD_PATCH_ROOT = ROOT / "combatmod_patch"
ARCHIPELAGO_ASSET_PACK_DIR = ROOT / "archipelago-asset-pack"
TEXCONV_PATH = ROOT / "tools" / "texconv.exe"
AP_ICON_TEXTURE_SPECS = (
    {
        "stem": "ap_trials_icon_blue",
        "icon_key": "ap_trials_icon_blue_001",
        "source": ARCHIPELAGO_ASSET_PACK_DIR / "blue-icon.png",
        "dds_name": "ap_trials_icon_blue_001.dds",
        "atlas_name": "Icons_ArchipelagoTrials_Blue.lsx",
        "atlas_uuid": "2d62f82d-e4f9-4f07-b9f5-aec4fd2b86b4",
    },
    {
        "stem": "ap_trials_icon_color",
        "icon_key": "ap_trials_icon_color_001",
        "source": ARCHIPELAGO_ASSET_PACK_DIR / "color-icon.png",
        "dds_name": "ap_trials_icon_color_001.dds",
        "atlas_name": "Icons_ArchipelagoTrials_Color.lsx",
        "atlas_uuid": "f30fe0f6-6ba8-43cf-8915-14eecc3bd5ab",
    },
)
ARCHIPELAGO_ATLAS_TEXTURE_SIZE = 512
ARCHIPELAGO_ATLAS_ICON_SIZE = 64
ARCHIPELAGO_ATLAS_UUID = "aa417c69-e69a-f1ef-5a8d-65b7b5d4e195"
COMBATMOD_AP_ATLAS_NAME = "Icons_ArchipelagoTrials"
COMBATMOD_AP_ATLAS_DDS_NAME = "Icons_ArchipelagoTrials.dds"
COMBATMOD_AP_ATLAS_LSX_NAME = "Icons_ArchipelagoTrials.lsx"
ARCHIPELAGO_ATLAS_SPECS = (
    {
        "icon_key": "original-logo",
        "source": ARCHIPELAGO_ASSET_PACK_DIR / "original-logo.png",
        "slot_x": 0,
        "slot_y": 0,
    },
    {
        "icon_key": "ap_trials_icon_blue_001",
        "source": ARCHIPELAGO_ASSET_PACK_DIR / "blue-icon.png",
        "slot_x": 1,
        "slot_y": 0,
    },
    {
        "icon_key": "ap_trials_icon_color_001",
        "source": ARCHIPELAGO_ASSET_PACK_DIR / "color-icon.png",
        "slot_x": 2,
        "slot_y": 0,
    },
)
SHAREDDEV_SKILL_ATLAS_TEXTURE_SIZE = 2048
SHAREDDEV_SKILL_ATLAS_ICON_SIZE = 64
SHAREDDEV_SKILL_ATLAS_RELATIVE_DDS = Path("Public") / "SharedDev" / "Assets" / "Textures" / "Icons" / "Icons_Skills.dds"
SHAREDDEV_SKILL_ATLAS_RELATIVE_LSX = Path("Public") / "SharedDev" / "GUI" / "Icons_Skills.lsx"
SHAREDDEV_SKILL_ICON_OVERRIDES = (
    {
        "icon_key": "statIcons_WretchedGrowth_Aura",
        "source": ARCHIPELAGO_ASSET_PACK_DIR / "blue-icon.png",
    },
    {
        "icon_key": "statIcons_WretchedGrowth_Buff",
        "source": ARCHIPELAGO_ASSET_PACK_DIR / "color-icon.png",
    },
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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

    component_limits = {
        "major": (major, 0xFF),
        "minor": (minor, 0xFF),
        "revision": (revision, 0xFFFF),
        "build": (build, 0x7FFFFFFF),
    }
    for label, (value, maximum) in component_limits.items():
        if value < 0 or value > maximum:
            raise ValueError(
                f"Release version component '{label}'={value} is out of range (0-{maximum})."
            )

    version64 = (
        (major << 55)
        | (minor << 47)
        | (revision << 31)
        | build
    )
    return str(version64)


def normalize_release_versions(config: dict[str, Any]) -> bool:
    compat = config.get("compat_mod", {})
    release_version = compat.get("release_version")
    if not release_version:
        return False

    publish_release_version = compat.get("publish_release_version") or release_version
    version64 = release_version_to_version64(str(release_version))
    publish_version64 = release_version_to_version64(str(publish_release_version))

    changed = False
    if compat.get("version64") != version64:
        compat["version64"] = version64
        changed = True
    if compat.get("publish_version64") != publish_version64:
        compat["publish_version64"] = publish_version64
        changed = True

    return changed


def unlock_catalog_total_slots(unlock_catalog: list[dict[str, Any]]) -> int:
    total = 0
    for entry in unlock_catalog:
        try:
            total += max(1, int(entry.get("copies", 1)))
        except (TypeError, ValueError):
            total += 1
    return total


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents.rstrip() + "\n", encoding="utf-8")


def slugify_filename(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    slug = slug.strip(".-")
    return slug or "release"


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


def render_meta_lsx(config: dict[str, Any]) -> str:
    compat = config["compat_mod"]
    dependencies = []
    for dependency in compat["dependencies"]:
        dependencies.append(
            f"""            <node id="ModuleShortDesc">
              <attribute id="Folder" type="LSWString" value="{escape(dependency['folder'])}" />
              <attribute id="MD5" type="LSString" value="" />
              <attribute id="Name" type="FixedString" value="{escape(dependency['name'])}" />
              <attribute id="UUID" type="FixedString" value="{escape(dependency['uuid'])}" />
              <attribute id="Version64" type="int64" value="{escape(str(dependency['version64']))}" />
            </node>"""
        )

    return f"""<?xml version="1.0" encoding="utf-8"?>
<save>
  <version major="4" minor="0" revision="9" build="328" />
  <region id="Config">
    <node id="root">
      <children>
        <node id="Dependencies">
          <children>
{chr(10).join(dependencies)}
          </children>
        </node>
        <node id="ModuleInfo">
          <attribute id="Author" type="LSString" value="{escape(compat['author'])}" />
          <attribute id="CharacterCreationLevelName" type="FixedString" value="" />
          <attribute id="Description" type="LSString" value="{escape(compat['description'])}" />
          <attribute id="Folder" type="LSString" value="{escape(compat['folder'])}" />
          <attribute id="LobbyLevelName" type="FixedString" value="" />
          <attribute id="MD5" type="LSString" value="" />
          <attribute id="MainMenuBackgroundVideo" type="FixedString" value="" />
          <attribute id="MenuLevelName" type="FixedString" value="" />
          <attribute id="Name" type="LSString" value="{escape(compat['display_name'])}" />
          <attribute id="NumPlayers" type="uint8" value="4" />
          <attribute id="PhotoBooth" type="FixedString" value="" />
          <attribute id="StartupLevelName" type="FixedString" value="" />
          <attribute id="Tags" type="LSString" value="" />
          <attribute id="Type" type="FixedString" value="Add-on" />
          <attribute id="UUID" type="FixedString" value="{escape(compat['uuid'])}" />
          <attribute id="Version64" type="int64" value="{escape(str(compat['version64']))}" />
          <children>
            <node id="PublishVersion">
              <attribute id="Version64" type="int64" value="{escape(str(compat['publish_version64']))}" />
            </node>
            <node id="Scripts" />
            <node id="TargetModes">
              <children>
                <node id="Target">
                  <attribute id="Object" type="FixedString" value="{escape(compat['target_mode'])}" />
                </node>
              </children>
            </node>
          </children>
        </node>
      </children>
    </node>
  </region>
</save>"""


def render_sample_yaml(config: dict[str, Any], unlock_catalog: list[dict[str, Any]]) -> str:
    sample = config["sample_player"]
    trap_lines = "\n".join(f"    - {trap}" for trap in sample["enabled_traps"])
    total_shop_slots = unlock_catalog_total_slots(unlock_catalog)
    return f"""name: {sample['name']}
description: {sample['description']}
game: {sample['game']}

{sample['game']}:
  death_link: {str(bool(sample.get('death_link', False))).lower()}
  death_link_trigger: {sample.get('death_link_trigger', 'full_party_wipe')}
  goal: {sample['goal']}
  goal_clear_target: {sample['goal_clear_target']}
  goal_rogue_score_target: {sample['goal_rogue_score_target']}
  clear_check_count: {sample['clear_check_count']}
  clear_check_interval: {sample['clear_check_interval']}
  kill_check_count: {sample['kill_check_count']}
  kill_check_interval: {sample['kill_check_interval']}
  perfect_check_count: {sample['perfect_check_count']}
  perfect_check_interval: {sample['perfect_check_interval']}
  roguescore_check_count: {sample['roguescore_check_count']}
  roguescore_check_interval: {sample['roguescore_check_interval']}
  shop_check_count: {min(sample['shop_check_count'], total_shop_slots)}
  shop_price_minimum: {sample['shop_price_minimum']}
  shop_price_maximum: {sample['shop_price_maximum']}
  traps_percentage: {sample['traps_percentage']}
  enabled_traps:
{trap_lines}
  sync_method: {sample['sync_method']}
"""


def sync_repo_files(config: dict[str, Any]) -> None:
    write_text(COMPAT_MOD_META_PATH, render_meta_lsx(config))
    dump_json(COMPAT_MOD_CONFIG_PATH, config["compat_mod"]["script_extender_config"])


def stage_trials_apworld(source_world_dir: Path, staged_world_dir: Path) -> None:
    shutil.copytree(source_world_dir, staged_world_dir, dirs_exist_ok=True)
    shutil.copy2(UNLOCK_CATALOG_PATH, staged_world_dir / "trials_unlock_catalog.json")

    for template_path in APWORLD_TEMPLATE_DIR.iterdir():
        destination = staged_world_dir / template_path.name
        if template_path.is_dir():
            shutil.copytree(template_path, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(template_path, destination)


def patch_once(contents: str, needle: str, replacement: str, file_label: str) -> str:
    if needle not in contents:
        raise ValueError(f"Could not find expected patch anchor in {file_label}")
    return contents.replace(needle, replacement, 1)


def patch_archipelago_server_lua(contents: str) -> str:
    contents = contents.replace("\r\n", "\n")
    if 'string.sub(v, 1, 10) == "ToTUnlock:"' in contents:
        return contents

    stun_anchor = 'elseif (string.sub(v, 6, 9) == "Stun") then\n                            ApplyStatus(targetChar, "STUNNED", 5)\n'
    stun_replacement = textwrap.dedent(
        """\
elseif (string.sub(v, 6, 9) == "Stun") then
                            ApplyStatus(targetChar, "STUNNED", 5)
                        elseif (string.sub(v, 6, 15) == "Confusion") then
                            ApplyStatus(targetChar, "CONFUSED", 5)
                        elseif (string.sub(v, 6, 11) == "Sussur") then
                            ApplyStatus(targetChar, "SUSSUR_BLOOM", 5)
                        elseif (string.sub(v, 6, 10) == "Clown") then
                            ApplyStatus(targetChar, "CLOWN", 10)
                        elseif (string.sub(v, 6, 17) == "Overburdened") then
                            ApplyStatus(targetChar, "OVERENCUMBERED", 10)
"""
    )
    contents = patch_once(contents, stun_anchor, stun_replacement, "Archipelago server lua")

    dupe_anchor = 'elseif (string.sub(v, 1, 5) == "Dupe-") then\n'
    dupe_replacement = textwrap.dedent(
        """\
elseif (string.sub(v, 1, 10) == "ToTUnlock:" or string.sub(v, 1, 10) == "ToTFiller:") then
                        APSent[v] = true
                    elseif (string.sub(v, 1, 5) == "Dupe-") then
"""
    )
    return patch_once(contents, dupe_anchor, dupe_replacement, "Archipelago server lua")


def atlas_uv_bounds_with_size(
    texture_size: int,
    icon_size: int,
    slot_x: int,
    slot_y: int,
) -> tuple[float, float, float, float]:
    texture_size = float(texture_size)
    icon_size = float(icon_size)
    u1 = ((slot_x * icon_size) + 0.5) / texture_size
    u2 = (((slot_x + 1) * icon_size) - 0.5) / texture_size
    v1 = ((slot_y * icon_size) + 0.5) / texture_size
    v2 = (((slot_y + 1) * icon_size) - 0.5) / texture_size
    return u1, u2, v1, v2


def atlas_uv_bounds(slot_x: int, slot_y: int) -> tuple[float, float, float, float]:
    return atlas_uv_bounds_with_size(
        ARCHIPELAGO_ATLAS_TEXTURE_SIZE,
        ARCHIPELAGO_ATLAS_ICON_SIZE,
        slot_x,
        slot_y,
    )


def render_archipelago_ap_atlas(texture_path: str = "Assets/Textures/Icons/apAtlas.dds", uuid: str = ARCHIPELAGO_ATLAS_UUID) -> str:
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


def render_texture_bank_resource(name: str, source_file: str, uuid: str, template: str = "Icons_Items") -> str:
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
                    <attribute id="Template" type="FixedString" value="{escape(template)}" />
                    <attribute id="Type" type="int32" value="0" />
                    <attribute id="_OriginalFileVersion_" type="int64" value="144115188075855873" />
                </node>
            </children>
        </node>
    </region>
</save>"""


def compose_archipelago_ap_atlas_png(atlas_png_path: Path) -> None:
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


def compose_overlay_png(base_png_path: Path, destination_png_path: Path, icon_specs: tuple[dict[str, Any], ...]) -> None:
    destination_png_path.parent.mkdir(parents=True, exist_ok=True)
    script = [
        "Add-Type -AssemblyName System.Drawing",
        (
            '$bitmap = [System.Drawing.Bitmap]::FromFile("'
            + str(base_png_path.resolve()).replace("\\", "\\\\")
            + '")'
        ),
        "$graphics = [System.Drawing.Graphics]::FromImage($bitmap)",
        "$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic",
        "$graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality",
        "$graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality",
    ]

    for spec in icon_specs:
        slot_x = int(spec["slot_x"]) * SHAREDDEV_SKILL_ATLAS_ICON_SIZE
        slot_y = int(spec["slot_y"]) * SHAREDDEV_SKILL_ATLAS_ICON_SIZE
        source_png = Path(spec["source"])
        if not source_png.exists():
            raise FileNotFoundError(f"Missing icon source: {source_png}")
        script.extend(
            [
                f'$img = [System.Drawing.Image]::FromFile("{str(source_png.resolve()).replace("\\", "\\\\")}")',
                "$graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy",
                (
                    "$graphics.DrawImage($img, "
                    f"(New-Object System.Drawing.Rectangle {slot_x}, {slot_y}, {SHAREDDEV_SKILL_ATLAS_ICON_SIZE}, {SHAREDDEV_SKILL_ATLAS_ICON_SIZE}))"
                ),
                "$graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver",
                "$img.Dispose()",
            ]
        )

    script.extend(
        [
            (
                '$bitmap.Save("'
                + str(destination_png_path.resolve()).replace("\\", "\\\\")
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


def atlas_slot_from_uv(texture_size: int, icon_size: int, u1: str, v1: str) -> tuple[int, int]:
    slot_x = round((float(u1) * texture_size - 0.5) / icon_size)
    slot_y = round((float(v1) * texture_size - 0.5) / icon_size)
    return slot_x, slot_y


def iter_bg3_data_candidates() -> list[Path]:
    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))

    candidates = [
        Path(r"A:\SteamLibrary\steamapps\common\Baldurs Gate 3\Data"),
        Path(r"D:\SteamLibrary\steamapps\common\Baldurs Gate 3\Data"),
        Path(r"E:\SteamLibrary\steamapps\common\Baldurs Gate 3\Data"),
        Path(r"F:\SteamLibrary\steamapps\common\Baldurs Gate 3\Data"),
        program_files_x86 / "Steam" / "steamapps" / "common" / "Baldurs Gate 3" / "Data",
        program_files / "Steam" / "steamapps" / "common" / "Baldurs Gate 3" / "Data",
        local_appdata / "Programs" / "Baldurs Gate 3" / "Data",
    ]

    seen: set[str] = set()
    unique_candidates = []
    for candidate in candidates:
        normalized = str(candidate).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)
    return unique_candidates


def resolve_bg3_data_dir() -> Path:
    for candidate in iter_bg3_data_candidates():
        if (candidate / "Icons.pak").exists() and (candidate / "Shared.pak").exists():
            return candidate
    raise FileNotFoundError("Could not locate Baldur's Gate 3 Data directory with Icons.pak and Shared.pak")


def extract_package_cached(divine_path: str, source_pak: Path, destination_dir: Path) -> None:
    if destination_dir.exists():
        return
    extract_pak(divine_path, source_pak, destination_dir)


def patch_shareddev_skill_atlas(staged_mod_dir: Path, cache_dir: Path, divine_path: str) -> None:
    if not TEXCONV_PATH.exists():
        raise FileNotFoundError(f"Missing required tool: {TEXCONV_PATH}")

    bg3_data_dir = resolve_bg3_data_dir()
    icons_cache_dir = cache_dir / "GameIconsPak"
    shared_cache_dir = cache_dir / "GameSharedPak"
    extract_package_cached(divine_path, bg3_data_dir / "Icons.pak", icons_cache_dir)
    extract_package_cached(divine_path, bg3_data_dir / "Shared.pak", shared_cache_dir)

    base_dds_path = icons_cache_dir / SHAREDDEV_SKILL_ATLAS_RELATIVE_DDS
    base_lsx_path = shared_cache_dir / SHAREDDEV_SKILL_ATLAS_RELATIVE_LSX
    if not base_dds_path.exists():
        raise FileNotFoundError(f"Missing base SharedDev atlas DDS: {base_dds_path}")
    if not base_lsx_path.exists():
        raise FileNotFoundError(f"Missing base SharedDev atlas LSX: {base_lsx_path}")

    tree = ET.parse(base_lsx_path)
    root = tree.getroot()
    icon_nodes = root.findall(".//node[@id='IconUV']")
    icon_slots: dict[str, tuple[int, int]] = {}
    for node in icon_nodes:
        attrs = {attribute.attrib["id"]: attribute.attrib["value"] for attribute in node.findall("attribute")}
        map_key = attrs.get("MapKey", "")
        if not map_key:
            continue
        icon_slots[map_key] = atlas_slot_from_uv(
            SHAREDDEV_SKILL_ATLAS_TEXTURE_SIZE,
            SHAREDDEV_SKILL_ATLAS_ICON_SIZE,
            attrs["U1"],
            attrs["V1"],
        )

    overlay_specs: list[dict[str, Any]] = []
    for spec in SHAREDDEV_SKILL_ICON_OVERRIDES:
        slot = icon_slots.get(str(spec["icon_key"]))
        if slot is None:
            raise ValueError(f"Could not find SharedDev skill atlas slot for icon key {spec['icon_key']}")
        overlay_specs.append(
            {
                "icon_key": spec["icon_key"],
                "source": spec["source"],
                "slot_x": slot[0],
                "slot_y": slot[1],
            }
        )

    working_dir = cache_dir / "SharedDevSkillAtlasPatch"
    working_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(TEXCONV_PATH),
            "-ft",
            "png",
            "-y",
            "-o",
            str(working_dir),
            str(base_dds_path),
        ],
        check=True,
        cwd=ROOT,
    )

    source_png = working_dir / "Icons_Skills.png"
    source_png_upper = working_dir / "Icons_Skills.PNG"
    if source_png_upper.exists() and not source_png.exists():
        source_png_upper.rename(source_png)
    if not source_png.exists():
        raise FileNotFoundError(f"Failed to convert SharedDev atlas DDS to PNG: {source_png}")

    patched_png = working_dir / "Icons_Skills_AP.png"
    compose_overlay_png(source_png, patched_png, tuple(overlay_specs))
    subprocess.run(
        [
            str(TEXCONV_PATH),
            "-f",
            "DXT5",
            "-dx9",
            "-w",
            str(SHAREDDEV_SKILL_ATLAS_TEXTURE_SIZE),
            "-h",
            str(SHAREDDEV_SKILL_ATLAS_TEXTURE_SIZE),
            "-m",
            "0",
            "-y",
            "-o",
            str(working_dir),
            str(patched_png),
        ],
        check=True,
        cwd=ROOT,
    )

    generated_dds = working_dir / "Icons_Skills_AP.dds"
    generated_dds_upper = working_dir / "Icons_Skills_AP.DDS"
    if generated_dds_upper.exists() and not generated_dds.exists():
        generated_dds_upper.rename(generated_dds)
    if not generated_dds.exists():
        raise FileNotFoundError(f"Failed to rebuild SharedDev atlas DDS: {generated_dds}")

    override_dds_path = staged_mod_dir / SHAREDDEV_SKILL_ATLAS_RELATIVE_DDS
    override_dds_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(generated_dds, override_dds_path)


def patch_archipelago_atlas_assets(staged_mod_dir: Path) -> None:
    if not TEXCONV_PATH.exists():
        raise FileNotFoundError(f"Missing required tool: {TEXCONV_PATH}")

    public_root = next(path for path in (staged_mod_dir / "Public").iterdir() if path.is_dir())
    icons_dir = public_root / "Assets" / "Textures" / "Icons"
    gui_dir = public_root / "GUI"
    ui_dir = public_root / "Content" / "UI" / "[PAK]_UI"
    icons_dir.mkdir(parents=True, exist_ok=True)
    gui_dir.mkdir(parents=True, exist_ok=True)
    ui_dir.mkdir(parents=True, exist_ok=True)

    atlas_png_path = icons_dir / "apAtlas.png"
    compose_archipelago_ap_atlas_png(atlas_png_path)
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

    generated_dds = icons_dir / "apAtlas.dds"
    generated_dds_upper = icons_dir / "apAtlas.DDS"
    if generated_dds_upper.exists() and not generated_dds.exists():
        generated_dds_upper.rename(generated_dds)
    write_text(gui_dir / "apAtlas.lsx", render_archipelago_ap_atlas())
    write_text(
        ui_dir / "_merged.lsx",
        render_texture_bank_resource(
            name="apAtlas",
            source_file=f"Public/{public_root.name}/Assets/Textures/Icons/apAtlas.dds",
            uuid=ARCHIPELAGO_ATLAS_UUID,
        ),
    )


def stage_archipelago_mod(source_mod_dir: Path, staged_mod_dir: Path) -> None:
    shutil.copytree(source_mod_dir, staged_mod_dir, dirs_exist_ok=True)

    server_lua_path = (
        staged_mod_dir
        / "Mods"
        / "Archipelago_9d8340ef-8f94-1397-4634-3297a02800d5"
        / "ScriptExtender"
        / "Lua"
        / "Server"
        / "Archipelago_9d8340ef-8f94-1397-4634-3297a02800d5.lua"
    )
    patched = patch_archipelago_server_lua(server_lua_path.read_text(encoding="utf-8"))
    write_text(server_lua_path, patched)


def patch_combatmod_custom_atlas_assets(staged_mod_dir: Path, divine_path: str) -> None:
    if not TEXCONV_PATH.exists():
        raise FileNotFoundError(f"Missing required tool: {TEXCONV_PATH}")

    public_root = staged_mod_dir / "Public" / "CombatMod"
    icons_dir = public_root / "Assets" / "Textures" / "Icons"
    gui_dir = public_root / "GUI"
    ui_dir = public_root / "Content" / "UI" / "[PAK]_UI"
    icons_dir.mkdir(parents=True, exist_ok=True)
    gui_dir.mkdir(parents=True, exist_ok=True)
    ui_dir.mkdir(parents=True, exist_ok=True)

    atlas_png_path = icons_dir / "Icons_ArchipelagoTrials.png"
    compose_archipelago_ap_atlas_png(atlas_png_path)
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
        gui_dir / COMBATMOD_AP_ATLAS_LSX_NAME,
        render_archipelago_ap_atlas(
            texture_path=f"Assets/Textures/Icons/{COMBATMOD_AP_ATLAS_DDS_NAME}",
            uuid=ARCHIPELAGO_ATLAS_UUID,
        ),
    )
    write_text(
        ui_dir / "_merged.lsx",
        render_texture_bank_resource(
            name=COMBATMOD_AP_ATLAS_NAME,
            source_file=f"Public/CombatMod/Assets/Textures/Icons/{COMBATMOD_AP_ATLAS_DDS_NAME}",
            uuid=ARCHIPELAGO_ATLAS_UUID,
        ),
    )
    convert_resource(divine_path, ui_dir / "_merged.lsx", ui_dir / "_merged.lsf")


def iter_combatmod_candidates(config: dict[str, Any]) -> list[tuple[str, Path]]:
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

    for required_mod in config.get("test_bundle", {}).get("required_mods", []):
        label = str(required_mod.get("label", ""))
        if "combatmod" in label.lower() or "trials of tav" in label.lower():
            add(f"config:required_mod:{label}", required_mod.get("path", ""))

    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    user_profile = Path(os.environ.get("USERPROFILE", ""))

    common_candidates = [
        local_appdata / "Larian Studios" / "Baldur's Gate 3" / "Mods" / "CombatMod.pak",
        ROOT / "CombatMod.pak",
        ROOT / "third_party" / "CombatMod.pak",
        user_profile / "Downloads" / "CombatMod.pak",
    ]
    for candidate in common_candidates:
        add("common", candidate)

    vortex_root = Path(r"A:\Votex\Vortex Staging")
    if vortex_root.exists():
        for candidate in sorted(vortex_root.glob("**/CombatMod.pak")):
            add("vortex_staging", candidate)

    return candidates


def resolve_combatmod_source(config: dict[str, Any]) -> dict[str, str | bool]:
    for source, candidate in iter_combatmod_candidates(config):
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


def patch_bootstrap_require(bootstrap_path: Path, require_line: str) -> None:
    contents = bootstrap_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if require_line in contents:
        return
    write_text(bootstrap_path, contents.rstrip() + "\n" + require_line)


def remove_path_if_exists(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def render_ap_icon_atlas(spec: dict[str, str]) -> str:
    dds_path = f"Assets/Textures/Icons/{spec['dds_name']}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<save>
    <version major="4" minor="3" revision="0" build="0"/>
    <region id="IconUVList">
        <node id="root">
            <children>
                <node id="IconUV">
                    <attribute id="MapKey" type="FixedString" value="{escape(spec['icon_key'])}"/>
                    <attribute id="U1" type="float" value="0"/>
                    <attribute id="U2" type="float" value="1"/>
                    <attribute id="V1" type="float" value="0"/>
                    <attribute id="V2" type="float" value="1"/>
                </node>
            </children>
        </node>
    </region>
    <region id="TextureAtlasInfo">
        <node id="root">
            <children>
                <node id="TextureAtlasIconSize">
                    <attribute id="Height" type="int32" value="64"/>
                    <attribute id="Width" type="int32" value="64"/>
                </node>
                <node id="TextureAtlasPath">
                    <attribute id="Path" type="string" value="{escape(dds_path)}"/>
                    <attribute id="UUID" type="FixedString" value="{escape(spec['atlas_uuid'])}"/>
                </node>
                <node id="TextureAtlasTextureSize">
                    <attribute id="Height" type="int32" value="64"/>
                    <attribute id="Width" type="int32" value="64"/>
                </node>
            </children>
        </node>
    </region>
</save>"""


def build_archipelago_shop_icon_atlases(staged_mod_dir: Path) -> None:
    if not TEXCONV_PATH.exists():
        raise FileNotFoundError(f"Missing required tool: {TEXCONV_PATH}")

    icons_dir = staged_mod_dir / "Public" / "CombatMod" / "Assets" / "Textures" / "Icons"
    gui_dir = staged_mod_dir / "Public" / "CombatMod" / "GUI"
    icons_dir.mkdir(parents=True, exist_ok=True)
    gui_dir.mkdir(parents=True, exist_ok=True)

    for spec in AP_ICON_TEXTURE_SPECS:
        source_png = Path(spec["source"])
        if not source_png.exists():
            raise FileNotFoundError(f"Missing icon source: {source_png}")

        staged_png = icons_dir / f"{spec['stem']}.png"
        shutil.copy2(source_png, staged_png)
        subprocess.run(
            [
                str(TEXCONV_PATH),
                "-f",
                "DXT5",
                "-dx9",
                "-w",
                "64",
                "-h",
                "64",
                "-m",
                "0",
                "-y",
                "-o",
                str(icons_dir),
                str(staged_png),
            ],
            check=True,
            cwd=ROOT,
        )

        generated_dds = icons_dir / f"{spec['stem']}.dds"
        generated_dds_upper = icons_dir / f"{spec['stem']}.DDS"
        if generated_dds_upper.exists() and not generated_dds.exists():
            generated_dds_upper.rename(generated_dds)
        output_dds = icons_dir / spec["dds_name"]
        if output_dds.exists():
            output_dds.unlink()
        shutil.move(str(generated_dds), str(output_dds))
        write_text(gui_dir / spec["atlas_name"], render_ap_icon_atlas(spec))


def stage_combatmod_mod(source: Path, staged_mod_dir: Path, divine_path: str, cache_dir: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, staged_mod_dir, dirs_exist_ok=True)
    else:
        extract_pak(divine_path, source, staged_mod_dir)

    remove_path_if_exists(staged_mod_dir / "Mods" / "CombatMod" / "ScriptExtender" / "VirtualTextures.json")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Assets" / "VirtualTextures")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Assets" / "Textures" / "VTexConfig.xml")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "GUI" / "Icons_ArchipelagoTrials_Blue.lsx")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "GUI" / "Icons_ArchipelagoTrials_Color.lsx")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "GUI" / COMBATMOD_AP_ATLAS_LSX_NAME)
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Content" / "UI" / "[PAK]_UI" / "_merged.lsx")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Content" / "UI" / "[PAK]_UI" / "_merged.lsf")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Assets" / "Textures" / "Icons" / "ap_trials_icon_blue.png")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Assets" / "Textures" / "Icons" / "ap_trials_icon_color.png")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Assets" / "Textures" / "Icons" / "ap_trials_icon_blue_001.dds")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Assets" / "Textures" / "Icons" / "ap_trials_icon_color_001.dds")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Assets" / "Textures" / "Icons" / "Icons_ArchipelagoTrials.png")
    remove_path_if_exists(staged_mod_dir / "Public" / "CombatMod" / "Assets" / "Textures" / "Icons" / COMBATMOD_AP_ATLAS_DDS_NAME)
    remove_path_if_exists(staged_mod_dir / SHAREDDEV_SKILL_ATLAS_RELATIVE_LSX)
    remove_path_if_exists(staged_mod_dir / SHAREDDEV_SKILL_ATLAS_RELATIVE_DDS)

    shutil.copytree(COMBATMOD_PATCH_ROOT, staged_mod_dir, dirs_exist_ok=True)

    bootstrap_server_path = staged_mod_dir / "Mods" / "CombatMod" / "ScriptExtender" / "Lua" / "BootstrapServer.lua"
    patch_bootstrap_require(
        bootstrap_server_path,
        'Ext.Require("CombatMod/Server/ArchipelagoTrialsCompat.lua")',
    )
    bootstrap_client_path = staged_mod_dir / "Mods" / "CombatMod" / "ScriptExtender" / "Lua" / "BootstrapClient.lua"
    patch_bootstrap_require(
        bootstrap_client_path,
        'Ext.Require("CombatMod/Client/ArchipelagoTrialsCompatClient.lua")',
    )
    patch_shareddev_skill_atlas(staged_mod_dir, cache_dir, divine_path)
    patch_combatmod_custom_atlas_assets(staged_mod_dir, divine_path)


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


def copy_if_exists(source: Path, destination: Path) -> bool:
    if not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)
    return True


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
    return str(pak_destination), divine_info


def build_test_bundle(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    output_dir = ROOT / config["output_dir"]
    cache_dir = ROOT / config["cache_dir"]

    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    divine_info = resolve_divine_path(config)
    combatmod_info = resolve_combatmod_source(config)

    archipelago_bg3_cache = cache_dir / "ArchipelagoBG3"
    bg3_mod_cache = cache_dir / "BG3ArchipelagoMod"

    ensure_git_clone(
        archipelago_bg3_cache,
        config["upstream"]["archipelago_bg3_repo"],
        config["upstream"]["archipelago_bg3_ref"],
        refresh=args.refresh_cache,
    )
    ensure_git_clone(
        bg3_mod_cache,
        config["upstream"]["bg3_mod_repo"],
        config["upstream"]["bg3_mod_ref"],
        refresh=args.refresh_cache,
    )

    unlock_catalog = load_json(UNLOCK_CATALOG_PATH)

    staged_world_dir = output_dir / "staging" / APWORLD_PACKAGE_NAME
    stage_trials_apworld(archipelago_bg3_cache / "worlds" / "bg3", staged_world_dir)
    apworld_path = output_dir / "apworlds" / APWORLD_FILENAME
    zip_directory(staged_world_dir, apworld_path, APWORLD_PACKAGE_NAME)

    staged_bridge_dir = output_dir / "bg3_mods" / "ArchipelagoTrials_unpacked"
    shutil.copytree(COMPAT_MOD_ROOT, staged_bridge_dir, dirs_exist_ok=True)

    source_archipelago_mod_dir = next(
        path for path in bg3_mod_cache.iterdir() if path.is_dir() and path.name.startswith("Archipelago_")
    )
    staged_archipelago_mod_dir = output_dir / "bg3_mods" / source_archipelago_mod_dir.name
    stage_archipelago_mod(source_archipelago_mod_dir, staged_archipelago_mod_dir)

    artifacts: list[dict[str, str]] = [
        {"kind": "apworld", "path": str(apworld_path.resolve())},
        {"kind": "compat_mod_unpacked", "path": str(staged_bridge_dir.resolve())},
        {"kind": "archipelago_mod_unpacked", "path": str(staged_archipelago_mod_dir.resolve())},
    ]

    if divine_info["found"] and combatmod_info["found"]:
        staged_combatmod_dir = output_dir / "bg3_mods" / "CombatMod_unpacked"
        stage_combatmod_mod(Path(str(combatmod_info["path"])), staged_combatmod_dir, str(divine_info["path"]), cache_dir)
        artifacts.append({"kind": "combatmod_unpacked", "path": str(staged_combatmod_dir.resolve())})
        combatmod_pak_path = output_dir / "bg3_mods" / "CombatMod.pak"
        subprocess.run(
            [
                str(divine_info["path"]),
                "-g",
                "bg3",
                "-a",
                "create-package",
                "-s",
                str(staged_combatmod_dir),
                "-d",
                str(combatmod_pak_path),
            ],
            check=True,
            cwd=ROOT,
        )
        artifacts.append({"kind": "combatmod_pak", "path": str(combatmod_pak_path.resolve())})

    compat_pak_path = output_dir / "bg3_mods" / "ArchipelagoTrials.pak"
    built_compat_pak, _ = build_pak(config, staged_bridge_dir, compat_pak_path)
    if built_compat_pak:
        artifacts.append({"kind": "compat_mod_pak", "path": built_compat_pak})

    archipelago_pak_path = output_dir / "bg3_mods" / f"{source_archipelago_mod_dir.name}.pak"
    built_archipelago_pak, _ = build_pak(config, staged_archipelago_mod_dir, archipelago_pak_path)
    if built_archipelago_pak:
        artifacts.append({"kind": "archipelago_mod_pak", "path": built_archipelago_pak})

    copied_required_mods = []
    missing_required_mods = []
    for required_mod in config["test_bundle"]["required_mods"]:
        mod_path = Path(required_mod["path"]).expanduser() if required_mod["path"] else None
        if mod_path and mod_path.exists():
            target = output_dir / "bg3_mods" / mod_path.name
            copy_if_exists(mod_path, target)
            copied_required_mods.append({"label": required_mod["label"], "path": str(target.resolve())})
        else:
            missing_required_mods.append(required_mod)

    sample_yaml_path = output_dir / "player_yaml" / "bg3_trials_test.yaml"
    write_text(sample_yaml_path, render_sample_yaml(config, unlock_catalog))
    artifacts.append({"kind": "sample_yaml", "path": str(sample_yaml_path.resolve())})
    release_bundle_path = output_dir / "release" / f"{slugify_filename(config['project_name'])}-test-bundle.zip"

    instructions = textwrap.dedent(
        """
        Archipelago BG3 Trials test bundle

        This archive contains the files needed for public testing:
        - {APWORLD_FILENAME}
        - CombatMod.pak
        - Archipelago_9d8340ef-8f94-1397-4634-3297a02800d5.pak
        - ArchipelagoTrials.pak
        - bg3_trials_test.yaml

        Brief setup:
        1. Put {APWORLD_FILENAME} into your Archipelago custom_worlds folder.
        2. Put the three .pak files into your BG3 Mods folder.
        3. In BG3 Mod Manager, use this load order:
           Trials of Tav - Reloaded
           Archipelago
           Archipelago Trials Bridge
        4. Save load order, export to game, then launch BG3.

        For full instructions, troubleshooting, and current notes, read the repository README on GitHub.
        """
    ).strip()
    install_path = output_dir / "INSTALL.txt"
    write_text(install_path, instructions)

    release_bundle_archive = None
    release_bundle_missing = []
    release_bundle_candidates = [
        (apworld_path, APWORLD_FILENAME),
        (output_dir / "bg3_mods" / "CombatMod.pak", "CombatMod.pak"),
        (archipelago_pak_path, archipelago_pak_path.name),
        (compat_pak_path, compat_pak_path.name),
        (install_path, "INSTALL.txt"),
        (sample_yaml_path, sample_yaml_path.name),
    ]
    for source_path, relative_name in release_bundle_candidates:
        if not source_path.exists() and relative_name in {
            APWORLD_FILENAME,
            "CombatMod.pak",
            archipelago_pak_path.name,
            compat_pak_path.name,
        }:
            release_bundle_missing.append(relative_name)

    if not release_bundle_missing:
        release_bundle_archive = build_release_archive(config, release_bundle_path, release_bundle_candidates)
        artifacts.append({"kind": "release_zip", "path": release_bundle_archive})

    manifest = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "project": config["project_name"],
        "divine": divine_info,
        "combatmod": combatmod_info,
        "artifacts": artifacts,
        "release_bundle": {
            "created": release_bundle_archive is not None,
            "path": release_bundle_archive or str(release_bundle_path.resolve()),
            "missing_required_files": release_bundle_missing,
        },
        "copied_required_mods": copied_required_mods,
        "missing_required_mods": missing_required_mods,
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
        help="sync regenerates repo files only; build also creates dist artifacts.",
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
    if normalize_release_versions(config):
        dump_json(CONFIG_PATH, config)

    sync_repo_files(config)

    if args.command == "sync":
        print("Synced generated repo files from build_config.json")
        return

    manifest = build_test_bundle(config, args)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
