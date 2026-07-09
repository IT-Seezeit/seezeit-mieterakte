from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


FOLDER_PREFIX = "1160_"


@dataclass(frozen=True)
class TargetPaths:
    residence_path: str
    wg_path: str
    wg_history_path: str
    room_path: str
    room_history_path: str
    past_tenants_path: str
    person_path: str

    @property
    def folders(self) -> list[str]:
        return [
            self.residence_path,
            self.wg_path,
            self.wg_history_path,
            self.room_path,
            self.room_history_path,
            self.past_tenants_path,
            self.person_path,
        ]


def normalize_folder_name(value: object, fallback: str = "unbekannt") -> str:
    normalized = str(value or "").strip()
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or fallback


def add_folder_prefix(name: str) -> str:
    return name if name.startswith(FOLDER_PREFIX) else f"{FOLDER_PREFIX}{name}"


def parse_vo_suchname(vo_suchname: object) -> dict[str, str]:
    parts = str(vo_suchname or "").split("-", 2)
    if len(parts) != 3 or not all(parts):
        raise ValueError(f"Invalid VO_Suchname format: {vo_suchname!r}")

    kst, wg_number, room_number = parts
    normalized_wg = normalize_folder_name(wg_number)
    if normalized_wg == "0":
        normalized_wg = "00"
    return {
        "kst": normalize_folder_name(kst),
        "wg": normalized_wg,
        "room": normalize_folder_name(room_number),
    }


def build_target_paths(root_path: str, row: dict[str, object]) -> TargetPaths:
    parsed = parse_vo_suchname(row.get("VO_SUCHNAME") or row.get("vo_suchname"))
    wohnheim_suchname = normalize_folder_name(
        row.get("WOHNHEIM_SUCHNAME") or row.get("wohnheim_suchname") or parsed["kst"]
    )
    wohnheim_name = normalize_folder_name(
        row.get("WOHNHEIM_NAME") or row.get("wohnheim_name") or "Wohnheim"
    )
    person_id = normalize_folder_name(row.get("PERSON_ID") or row.get("person_id"))
    vorname = normalize_folder_name(row.get("VORNAME") or row.get("vorname"))
    name = normalize_folder_name(row.get("NAME") or row.get("name"))

    residence_folder = add_folder_prefix(f"{wohnheim_suchname}-{wohnheim_name}")
    wg_base_name = f"{wohnheim_suchname}-WG-{parsed['wg']}"
    room_base_name = f"{wohnheim_suchname}-{parsed['wg']}-Zi-{parsed['room']}"
    person_base_name = (
        f"{wohnheim_suchname}-{parsed['wg']}-{parsed['room']}-"
        f"{person_id}-{vorname}-{name}"
    )
    wg_folder = add_folder_prefix(wg_base_name)
    room_folder = add_folder_prefix(room_base_name)
    person_folder = add_folder_prefix(person_base_name)
    wg_history_folder = f"{wg_folder}-Historie"
    room_history_folder = f"{room_folder}-Historie"
    past_tenants_folder = f"{room_folder}-Vergangene-Mieter"

    root = PurePosixPath(root_path)
    residence_path = str(root / residence_folder)
    wg_path = str(PurePosixPath(residence_path) / wg_folder)
    room_path = str(PurePosixPath(wg_path) / room_folder)

    return TargetPaths(
        residence_path=residence_path,
        wg_path=wg_path,
        wg_history_path=str(PurePosixPath(wg_path) / wg_history_folder),
        room_path=room_path,
        room_history_path=str(PurePosixPath(room_path) / room_history_folder),
        past_tenants_path=str(PurePosixPath(room_path) / past_tenants_folder),
        person_path=str(PurePosixPath(room_path) / person_folder),
    )
