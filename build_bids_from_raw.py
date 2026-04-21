#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path

import mne

from schizophrenia_dataset_utils import (
    BIDS_VERSION,
    bids_participant_ids,
    build_hash_groups,
    channel_order_string,
    collect_raw_records,
    compute_sha256,
    ensure_expected_channel_sets,
    parse_manifest_txt,
    write_json,
    write_text,
    write_tsv,
)


GENERATED_ROOT_FILES = (
    ".bidsignore",
    "CHANGES",
    "README",
    "dataset_description.json",
    "participants.tsv",
    "participants.json",
)


def parse_args() -> argparse.Namespace:
    script_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Build a raw-preserving BIDS conversion for the EEG-in-schizophrenia dataset."
    )
    parser.add_argument(
        "raw_root",
        nargs="?",
        type=Path,
        default=script_root,
        help="Path to the raw flat EDF dataset. Defaults to the directory containing this script.",
    )
    parser.add_argument(
        "output_root",
        nargs="?",
        type=Path,
        default=script_root / "BIDS",
        help="BIDS output root. Defaults to <raw_root>/BIDS.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove previously generated BIDS subject folders and root metadata before writing.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing BIDS recording files.",
    )
    parser.add_argument(
        "--task-label",
        default="rest",
        help="Task label to use in BIDS filenames. Defaults to 'rest'.",
    )
    return parser.parse_args()


def cleanup_output_root(output_root: Path) -> None:
    if not output_root.exists():
        return
    for child in output_root.iterdir():
        if child.is_dir() and child.name.startswith("sub-"):
            shutil.rmtree(child)
    sourcedata_path = output_root / "sourcedata"
    if sourcedata_path.exists():
        shutil.rmtree(sourcedata_path)
    for file_name in GENERATED_ROOT_FILES:
        path = output_root / file_name
        if path.exists():
            path.unlink()


def bids_relpath(participant_id: str, task_label: str) -> Path:
    return Path(participant_id) / "eeg" / f"{participant_id}_task-{task_label}_eeg.edf"


def eeg_sidecar(record, task_label: str) -> dict:
    return {
        "TaskName": task_label,
        "SamplingFrequency": record.sfreq,
        "PowerLineFrequency": "n/a",
        "SoftwareFilters": "n/a",
        "EEGReference": "Reference electrode placed between Fz and Cz, as described in Metadata.md.",
        "RecordingType": "continuous",
        "EEGChannelCount": record.n_channels,
        "EEGPlacementScheme": "International 10-20 system (19 channels).",
    }


def channels_rows(record) -> list[dict[str, str]]:
    return [
        {
            "name": channel_name,
            "type": "EEG",
            "units": "V",
            "sampling_frequency": f"{record.sfreq:g}",
            "reference": "Fz-Cz midpoint",
            "status": "good",
            "status_description": "n/a",
        }
        for channel_name in record.channel_order
    ]


def participants_json() -> dict:
    return {
        "participant_id": {
            "Description": "Canonical BIDS participant identifier assigned during conversion.",
        },
        "group": {
            "Description": "Diagnostic cohort preserved from the source EDF dataset.",
            "Levels": {
                "control": "Healthy control participant.",
                "schizophrenia": "Participant with schizophrenia.",
            },
        },
        "original_subject_id": {
            "Description": "Original source subject identifier from the flat EDF archive.",
        },
        "source_filename": {
            "Description": "Original EDF filename in the flat source archive.",
        },
        "recording_duration_sec": {
            "Description": "Continuous recording duration in seconds.",
        },
    }


def dataset_description(raw_root: Path) -> dict:
    return {
        "Name": "EEG in Schizophrenia BIDS Conversion",
        "BIDSVersion": BIDS_VERSION,
        "DatasetType": "raw",
        "GeneratedBy": [
            {
                "Name": "build_bids_from_raw.py",
                "Version": "1.0.0",
                "Description": "Copies the flat EDF source dataset into a BIDS-organized layout with metadata sidecars.",
            }
        ],
        "SourceDatasets": [
            {
                "URL": raw_root.as_uri(),
                "Description": "Flat EDF source dataset with 14 controls and 14 schizophrenia recordings.",
            }
        ],
        "ReferencesAndLinks": [
            "https://doi.org/10.18150/repod.0107441",
        ],
        "License": "n/a",
    }


def build_readme(
    records,
    output_root: Path,
    task_label: str,
    raw_hash_groups,
    signal_hash_groups,
    bids_duplicate_groups: int,
) -> str:
    controls = sum(1 for record in records if record.group == "control")
    schizophrenia = sum(1 for record in records if record.group == "schizophrenia")
    duplicate_raw_groups = sum(1 for files in raw_hash_groups.values() if len(files) > 1)
    duplicate_signal_groups = sum(1 for files in signal_hash_groups.values() if len(files) > 1)
    channel_order_variants = sorted({record.channel_order_variant for record in records})
    return "\n".join(
        [
            "# EEG In Schizophrenia BIDS Conversion",
            "",
            "This directory is a BIDS-organized packaging of the flat EDF source dataset.",
            "",
            "## Summary",
            "",
            f"- controls: `{controls}`",
            f"- schizophrenia: `{schizophrenia}`",
            f"- total participants: `{len(records)}`",
            f"- task label: `{task_label}`",
            f"- exact raw duplicate groups found in the source: `{duplicate_raw_groups}`",
            f"- decoded-signal duplicate groups found in the source: `{duplicate_signal_groups}`",
            f"- copied BIDS EDF duplicate file-hash groups found: `{bids_duplicate_groups}`",
            f"- observed source channel-order variants: `{', '.join(channel_order_variants)}`",
            "",
            "## Mapping Rule",
            "",
            "Canonical participant IDs were assigned deterministically as:",
            "",
            "1. controls first, ascending by original subject number",
            "2. schizophrenia second, ascending by original subject number",
            "",
            "## Notes",
            "",
            "- this BIDS layer preserves the source EDF recordings rather than rebuilding them from a derivative",
            "- source EDF channel order is preserved in the copied BIDS recordings and documented in each `_channels.tsv` file",
            "- copied BIDS EDF file hashes are recorded in `sourcedata/bids_file_hashes.tsv`",
            "- the normalized derivative is the place where channel order is standardized for downstream analysis",
            "- the current task label is `rest` because the local source metadata does not explicitly encode eyes-open versus eyes-closed",
            "",
            "## Validation",
            "",
            f"- validation tables live under `{output_root / 'sourcedata'}`",
            "- copied EDF SHA-256 hashes were checked against source hashes",
            "- sidecar files were generated for every recording",
        ]
    )


def build_changes(records) -> str:
    return "\n".join(
        [
            date.today().isoformat(),
            "- Created the initial BIDS conversion from the flat EDF source dataset.",
            "- Assigned canonical participant IDs with controls first and schizophrenia second.",
            f"- Packaged {len(records)} EDF recordings into the BIDS tree.",
        ]
    )


def build_bidsignore() -> str:
    return ".DS_Store"


def main() -> None:
    args = parse_args()
    raw_root = args.raw_root.resolve()
    output_root = args.output_root.resolve()

    if args.clean:
        cleanup_output_root(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    records = collect_raw_records(raw_root)
    ensure_expected_channel_sets(records)
    raw_hash_groups, signal_hash_groups = build_hash_groups(records)
    participant_ids = bids_participant_ids(records)

    participant_rows: list[dict[str, str]] = []
    recording_inventory_rows: list[dict[str, str]] = []
    bids_file_rows: list[dict[str, str]] = []
    validation_rows: list[dict[str, str]] = []

    mne.set_log_level("ERROR")

    for record in records:
        participant_id = participant_ids[record.source_name]
        output_relpath = bids_relpath(participant_id, args.task_label)
        output_path = output_root / output_relpath
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if args.overwrite or not output_path.exists():
            shutil.copy2(record.source_path, output_path)

        eeg_json_path = output_path.with_suffix(".json")
        channels_tsv_path = output_path.parent / f"{output_path.stem.replace('_eeg', '')}_channels.tsv"
        write_json(eeg_json_path, eeg_sidecar(record, args.task_label))
        write_tsv(
            channels_tsv_path,
            ["name", "type", "units", "sampling_frequency", "reference", "status", "status_description"],
            channels_rows(record),
        )

        copied_sha256 = compute_sha256(output_path)
        reopened = mne.io.read_raw_edf(output_path, preload=False, infer_types=True, verbose="ERROR")

        participant_rows.append(
            {
                "participant_id": participant_id,
                "group": record.group,
                "original_subject_id": record.original_subject_id,
                "source_filename": record.source_name,
                "recording_duration_sec": f"{record.duration_sec:g}",
            }
        )
        recording_inventory_rows.append(
            {
                "participant_id": participant_id,
                "group": record.group,
                "original_subject_id": record.original_subject_id,
                "source_name": record.source_name,
                "bids_relpath": str(output_relpath),
                "source_bytes": str(record.source_bytes),
                "raw_sha256": record.raw_sha256,
                "signal_sha256": record.signal_sha256,
                "n_channels": str(record.n_channels),
                "sfreq": f"{record.sfreq:g}",
                "n_times": str(record.n_times),
                "duration_sec": f"{record.duration_sec:g}",
                "channel_order_variant": record.channel_order_variant,
                "channel_order": channel_order_string(record.channel_order),
                "header_patient_id": record.header_patient_id,
                "meas_date_iso": record.meas_date_iso,
            }
        )
        bids_file_rows.append(
            {
                "participant_id": participant_id,
                "source_name": record.source_name,
                "bids_relpath": str(output_relpath),
                "bids_bytes": str(output_path.stat().st_size),
                "bids_sha256": copied_sha256,
            }
        )
        validation_rows.append(
            {
                "participant_id": participant_id,
                "source_name": record.source_name,
                "bids_relpath": str(output_relpath),
                "copied_sha256": copied_sha256,
                "source_hash_match": "yes" if copied_sha256 == record.raw_sha256 else "no",
                "eeg_json_exists": "yes" if eeg_json_path.exists() else "no",
                "channels_tsv_exists": "yes" if channels_tsv_path.exists() else "no",
                "channel_count_match": "yes"
                if len(reopened.ch_names) == record.n_channels
                else "no",
                "channel_order_match": "yes"
                if tuple(reopened.ch_names) == record.channel_order
                else "no",
            }
        )

    bids_hash_groups: dict[str, list[dict[str, str]]] = {}
    for row in bids_file_rows:
        bids_hash_groups.setdefault(row["bids_sha256"], []).append(row)
    for row in bids_file_rows:
        row["bids_duplicate_group_size"] = str(len(bids_hash_groups[row["bids_sha256"]]))
    bids_duplicate_groups = sum(1 for rows in bids_hash_groups.values() if len(rows) > 1)

    sourcedata_root = output_root / "sourcedata"
    sourcedata_root.mkdir(parents=True, exist_ok=True)

    write_tsv(
        output_root / "participants.tsv",
        list(participant_rows[0].keys()),
        participant_rows,
    )
    write_json(output_root / "participants.json", participants_json())
    write_json(output_root / "dataset_description.json", dataset_description(raw_root))
    write_text(
        output_root / "README",
        build_readme(
            records,
            output_root,
            args.task_label,
            raw_hash_groups,
            signal_hash_groups,
            bids_duplicate_groups,
        ),
    )
    write_text(output_root / "CHANGES", build_changes(records))
    write_text(output_root / ".bidsignore", build_bidsignore())

    write_tsv(
        sourcedata_root / "original_manifest.tsv",
        ["line_number", "source_name", "mime_type", "manifest_size_bytes", "raw_line"],
        parse_manifest_txt(raw_root / "MANIFEST.TXT"),
    )
    write_tsv(
        sourcedata_root / "raw_file_hashes.tsv",
        [
            "source_name",
            "group",
            "original_subject_id",
            "source_bytes",
            "raw_sha256",
            "raw_duplicate_group_size",
        ],
        [
            {
                "source_name": record.source_name,
                "group": record.group,
                "original_subject_id": record.original_subject_id,
                "source_bytes": str(record.source_bytes),
                "raw_sha256": record.raw_sha256,
                "raw_duplicate_group_size": str(len(raw_hash_groups[record.raw_sha256])),
            }
            for record in records
        ],
    )
    write_tsv(
        sourcedata_root / "decoded_signal_hashes.tsv",
        [
            "source_name",
            "group",
            "original_subject_id",
            "n_channels",
            "sfreq",
            "n_times",
            "duration_sec",
            "channel_order",
            "signal_sha256",
            "signal_duplicate_group_size",
        ],
        [
            {
                "source_name": record.source_name,
                "group": record.group,
                "original_subject_id": record.original_subject_id,
                "n_channels": str(record.n_channels),
                "sfreq": f"{record.sfreq:g}",
                "n_times": str(record.n_times),
                "duration_sec": f"{record.duration_sec:g}",
                "channel_order": channel_order_string(record.channel_order),
                "signal_sha256": record.signal_sha256,
                "signal_duplicate_group_size": str(len(signal_hash_groups[record.signal_sha256])),
            }
            for record in records
        ],
    )
    write_tsv(
        sourcedata_root / "recording_inventory.tsv",
        list(recording_inventory_rows[0].keys()),
        recording_inventory_rows,
    )
    write_tsv(
        sourcedata_root / "bids_file_hashes.tsv",
        list(bids_file_rows[0].keys()),
        bids_file_rows,
    )
    write_tsv(
        sourcedata_root / "validation.tsv",
        list(validation_rows[0].keys()),
        validation_rows,
    )

    print(f"Source root: {raw_root}")
    print(f"BIDS output root: {output_root}")
    print(f"Participants packaged: {len(records)}")
    print(f"Manifest date: {date.today().isoformat()}")


if __name__ == "__main__":
    main()
