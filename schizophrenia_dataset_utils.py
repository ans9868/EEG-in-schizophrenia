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
    "Fp2",
    "F8",
    "T4",
    "T6",
    "O2",
    "Fp1",
    "F7",
    "T3",
    "T5",
    "O1",
    "F4",
    "C4",
    "P4",
    "F3",
    "C3",
    "P3",
    "Fz",
    "Cz",
    "Pz",
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
    missing_channels: tuple[str, ...]
    extra_channels: tuple[str, ...]
    channel_policy: str


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


def assess_channel_membership(channel_order: Iterable[str]) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    observed = list(channel_order)
    observed_set = frozenset(observed)
    missing = tuple(channel_name for channel_name in CANONICAL_CHANNEL_ORDER if channel_name not in observed_set)
    extra = tuple(channel_name for channel_name in observed if channel_name not in EXPECTED_CHANNEL_SET)

    if missing:
        return missing, extra, "exclude_missing_required_channels"
    if extra:
        return missing, extra, "keep_drop_extra_channels"
    if tuple(observed) == tuple(CANONICAL_CHANNEL_ORDER):
        return missing, extra, "keep_exact_target_channels"
    return missing, extra, "keep_reorder_only"


def rewrite_edf_channel_order(source_path: Path, destination_path: Path, target_order: Iterable[str]) -> None:
    target_order = tuple(target_order)
    with source_path.open("rb") as handle:
        general_header = handle.read(256)
        n_signals = int(general_header[252:256].decode("ascii").strip())
        signal_header_bytes = handle.read(256 * n_signals)
        data_bytes = handle.read()

    if len(signal_header_bytes) != 256 * n_signals:
        raise RuntimeError(f"Incomplete EDF signal header in {source_path}")

    field_widths = (
        ("label", 16),
        ("transducer", 80),
        ("physical_dimension", 8),
        ("physical_min", 8),
        ("physical_max", 8),
        ("digital_min", 8),
        ("digital_max", 8),
        ("prefilter", 80),
        ("n_samples_per_record", 8),
        ("reserved", 32),
    )

    field_values: dict[str, list[bytes]] = {}
    cursor = 0
    for field_name, width in field_widths:
        values = [
            signal_header_bytes[cursor + index * width : cursor + (index + 1) * width]
            for index in range(n_signals)
        ]
        field_values[field_name] = values
        cursor += width * n_signals

    labels = [value.decode("ascii", errors="ignore").strip() for value in field_values["label"]]
    index_by_label = {label: index for index, label in enumerate(labels)}
    missing = [channel_name for channel_name in target_order if channel_name not in index_by_label]
    extra = [label for label in labels if label not in target_order]
    if missing:
        raise RuntimeError(
            f"Cannot reorder EDF {source_path.name}: missing target channels {missing}"
        )

    reorder_indices = [index_by_label[channel_name] for channel_name in target_order] + [
        index_by_label[channel_name] for channel_name in extra
    ]
    n_samples_per_record = [
        int(value.decode("ascii", errors="ignore").strip()) for value in field_values["n_samples_per_record"]
    ]
    signal_byte_widths = [sample_count * 2 for sample_count in n_samples_per_record]
    bytes_per_record = sum(signal_byte_widths)
    if bytes_per_record == 0:
        raise RuntimeError(f"Unexpected zero-byte EDF record size in {source_path.name}")
    if len(data_bytes) % bytes_per_record != 0:
        raise RuntimeError(
            f"EDF payload size for {source_path.name} does not align with the record size"
        )

    reordered_signal_header = bytearray()
    for field_name, _width in field_widths:
        for index in reorder_indices:
            reordered_signal_header.extend(field_values[field_name][index])

    reordered_data = bytearray()
    n_records = len(data_bytes) // bytes_per_record
    offsets = []
    offset = 0
    for width in signal_byte_widths:
        offsets.append((offset, offset + width))
        offset += width
    for record_index in range(n_records):
        record_start = record_index * bytes_per_record
        record_end = record_start + bytes_per_record
        record_bytes = data_bytes[record_start:record_end]
        signal_chunks = [record_bytes[start:end] for start, end in offsets]
        for index in reorder_indices:
            reordered_data.extend(signal_chunks[index])

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with destination_path.open("wb") as handle:
        handle.write(general_header)
        handle.write(reordered_signal_header)
        handle.write(reordered_data)


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
        missing_channels, extra_channels, channel_policy = assess_channel_membership(channel_order)
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
                missing_channels=missing_channels,
                extra_channels=extra_channels,
                channel_policy=channel_policy,
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


def split_records_by_channel_policy(records: list[RawRecord]) -> tuple[list[RawRecord], list[RawRecord]]:
    retained = [record for record in records if record.channel_policy != "exclude_missing_required_channels"]
    excluded = [record for record in records if record.channel_policy == "exclude_missing_required_channels"]
    return retained, excluded


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
