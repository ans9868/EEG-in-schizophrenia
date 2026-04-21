#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import mne


BIDS_VERSION = "1.11.1"
CANONICAL_CHANNEL_ORDER = (
    "Fp1",
    "Fp2",
    "F7",
    "F3",
    "Fz",
    "F4",
    "F8",
    "T3",
    "C3",
    "Cz",
    "C4",
    "T4",
    "T5",
    "P3",
    "Pz",
    "P4",
    "T6",
    "O1",
    "O2",
)
EXPECTED_CHANNEL_SET = frozenset(CANONICAL_CHANNEL_ORDER)
GROUP_ORDER = {
    "control": 0,
    "schizophrenia": 1,
}


@dataclass(frozen=True)
class RawRecord:
    source_path: Path
    source_name: str
    group: str
    original_subject_id: str
    normalized_subject_id: str
    subject_number: int
    source_bytes: int
    raw_sha256: str
    signal_sha256: str
    n_channels: int
    sfreq: float
    n_times: int
    duration_sec: float
    channel_order: tuple[str, ...]
    channel_set_hash: str
    channel_order_variant: str
    annotations_count: int
    header_patient_id: str
    meas_date_iso: str


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_channel_order(channel_order: Iterable[str]) -> str:
    joined = "|".join(channel_order).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def parse_source_name(source_name: str) -> tuple[str, int]:
    match = re.fullmatch(r"([hs])(\d{2})\.edf", source_name)
    if not match:
        raise ValueError(f"Unexpected source EDF filename: {source_name}")
    prefix, subject_number = match.groups()
    if prefix == "h":
        return ("control", int(subject_number))
    return ("schizophrenia", int(subject_number))


def original_subject_id(group: str, subject_number: int) -> str:
    prefix = "h" if group == "control" else "s"
    return f"{prefix}{subject_number:02d}"


def normalized_subject_id(group: str, subject_number: int) -> str:
    prefix = "H_S" if group == "control" else "SZ_S"
    return f"{prefix}{subject_number:02d}"


def group_folder_name(group: str) -> str:
    if group == "control":
        return "healthy_controls"
    return "schizophrenia"


def channel_order_string(channel_order: Iterable[str]) -> str:
    return "|".join(channel_order)


def normalize_meas_date(raw: mne.io.BaseRaw) -> str:
    meas_date = raw.info.get("meas_date")
    if meas_date is None:
        return ""
    return meas_date.isoformat()


def extract_header_patient_id(raw: mne.io.BaseRaw) -> str:
    subject_info = raw.info.get("subject_info")
    if not subject_info:
        return ""
    if hasattr(subject_info, "get"):
        value = subject_info.get("his_id", "")
        return "" if value is None else str(value)
    value = getattr(subject_info, "his_id", "")
    return "" if value is None else str(value)


def collect_raw_records(raw_root: Path) -> list[RawRecord]:
    raw_root = raw_root.resolve()
    source_paths = sorted(raw_root.glob("*.edf"))
    if not source_paths:
        raise FileNotFoundError(f"No EDF files found under {raw_root}")

    order_to_variant: dict[tuple[str, ...], str] = {}
    records: list[RawRecord] = []
    mne.set_log_level("ERROR")

    for source_path in source_paths:
        group, subject_number = parse_source_name(source_path.name)
        raw = mne.io.read_raw_edf(source_path, preload=True, infer_types=True, verbose="ERROR")
        channel_order = tuple(raw.ch_names)
        channel_order_variant = order_to_variant.setdefault(
            channel_order,
            f"variant_{len(order_to_variant) + 1:02d}",
        )
        data = raw.get_data().astype("float32", copy=False)
        signal_sha256 = hashlib.sha256(data.tobytes()).hexdigest()
        records.append(
            RawRecord(
                source_path=source_path,
                source_name=source_path.name,
                group=group,
                original_subject_id=original_subject_id(group, subject_number),
                normalized_subject_id=normalized_subject_id(group, subject_number),
                subject_number=subject_number,
                source_bytes=source_path.stat().st_size,
                raw_sha256=compute_sha256(source_path),
                signal_sha256=signal_sha256,
                n_channels=len(channel_order),
                sfreq=float(raw.info["sfreq"]),
                n_times=raw.n_times,
                duration_sec=raw.n_times / float(raw.info["sfreq"]),
                channel_order=channel_order,
                channel_set_hash=hash_channel_order(sorted(channel_order)),
                channel_order_variant=channel_order_variant,
                annotations_count=len(raw.annotations),
                header_patient_id=extract_header_patient_id(raw),
                meas_date_iso=normalize_meas_date(raw),
            )
        )

    return sorted(records, key=lambda record: (GROUP_ORDER[record.group], record.subject_number))


def build_hash_groups(records: list[RawRecord]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    raw_hash_groups: dict[str, list[str]] = {}
    signal_hash_groups: dict[str, list[str]] = {}
    for record in records:
        raw_hash_groups.setdefault(record.raw_sha256, []).append(record.source_name)
        signal_hash_groups.setdefault(record.signal_sha256, []).append(record.source_name)
    return raw_hash_groups, signal_hash_groups


def ensure_expected_channel_sets(records: list[RawRecord]) -> None:
    bad_records = [
        record
        for record in records
        if frozenset(record.channel_order) != EXPECTED_CHANNEL_SET
    ]
    if not bad_records:
        return
    details = ", ".join(record.source_name for record in bad_records)
    raise ValueError(f"Unexpected channel set found in: {details}")


def bids_participant_ids(records: list[RawRecord]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for index, record in enumerate(records, start=1):
        mapping[record.source_name] = f"sub-{index:03d}"
    return mapping


def parse_manifest_txt(manifest_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not manifest_path.exists():
        return rows
    pattern = re.compile(r"(.+?) \((.+?)\) (\d+) bytes\.")
    for line_number, raw_line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        match = pattern.fullmatch(line)
        if match:
            filename, mime_type, size_bytes = match.groups()
            rows.append(
                {
                    "line_number": str(line_number),
                    "source_name": filename,
                    "mime_type": mime_type,
                    "manifest_size_bytes": size_bytes,
                    "raw_line": raw_line,
                }
            )
        else:
            rows.append(
                {
                    "line_number": str(line_number),
                    "source_name": "",
                    "mime_type": "",
                    "manifest_size_bytes": "",
                    "raw_line": raw_line,
                }
            )
    return rows
