#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path

import mne

from schizophrenia_dataset_utils import (
    CANONICAL_CHANNEL_ORDER,
    build_hash_groups,
    channel_order_string,
    collect_raw_records,
    compute_sha256,
    group_folder_name,
    split_records_by_channel_policy,
    write_text,
    write_tsv,
)


GENERATED_DIRS = ("healthy_controls", "schizophrenia", "manifests")
GENERATED_FILES = ("README.md",)


def parse_args() -> argparse.Namespace:
    script_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Build a normalized derivative for the EEG-in-schizophrenia dataset."
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
        default=script_root.parent / f"{script_root.name}_normalized",
        help="Normalized output root. Defaults to a sibling *_normalized directory.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove previously generated normalized folders and manifests before writing.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    return parser.parse_args()


def cleanup_output_root(output_root: Path) -> None:
    if not output_root.exists():
        return
    for directory_name in GENERATED_DIRS:
        path = output_root / directory_name
        if path.exists():
            shutil.rmtree(path)
    for file_name in GENERATED_FILES:
        path = output_root / file_name
        if path.exists():
            path.unlink()


def normalized_relpath(record) -> Path:
    return Path(group_folder_name(record.group)) / record.normalized_subject_id / "rest_raw.fif"


def build_readme(
    all_records,
    retained_records,
    excluded_records,
    raw_root: Path,
    output_root: Path,
    raw_hash_groups,
    signal_hash_groups,
    processed_duplicate_groups: int,
) -> str:
    controls = sum(1 for record in retained_records if record.group == "control")
    schizophrenia = sum(1 for record in retained_records if record.group == "schizophrenia")
    min_duration = min(record.duration_sec for record in retained_records)
    max_duration = max(record.duration_sec for record in retained_records)
    duplicate_raw_groups = sum(1 for files in raw_hash_groups.values() if len(files) > 1)
    duplicate_signal_groups = sum(1 for files in signal_hash_groups.values() if len(files) > 1)
    dropped_extra_channel_count = sum(1 for record in retained_records if record.extra_channels)
    reorder_only_count = sum(1 for record in retained_records if record.channel_policy == "keep_reorder_only")
    exact_match_count = sum(1 for record in retained_records if record.channel_policy == "keep_exact_target_channels")
    subject_12_reordered = any(record.source_name == "h12.edf" for record in retained_records if record.channel_policy == "keep_reorder_only")

    lines = [
        "# EEG In Schizophrenia Normalized",
        "",
        "This directory is a normalized, analysis-ready derivative built from the raw flat EDF dataset at:",
        "",
        f"- `{raw_root}`",
        "",
        "## Summary",
        "",
        f"- raw source recordings seen: `{len(all_records)}`",
        f"- normalized recordings retained: `{len(retained_records)}`",
        f"- controls retained: `{controls}`",
        f"- schizophrenia retained: `{schizophrenia}`",
        f"- recordings excluded for missing required channels: `{len(excluded_records)}`",
        f"- retained recordings with extra channels dropped before normalization: `{dropped_extra_channel_count}`",
        f"- retained recordings that only needed channel reordering: `{reorder_only_count}`",
        f"- retained recordings already in canonical order: `{exact_match_count}`",
        f"- channel count after normalization: `{len(CANONICAL_CHANNEL_ORDER)}`",
        f"- sampling frequency: `{retained_records[0].sfreq:g} Hz`",
        f"- duration range: `{min_duration:g}` to `{max_duration:g}` seconds",
        f"- exact raw duplicate groups found: `{duplicate_raw_groups}`",
        f"- decoded-signal duplicate groups found: `{duplicate_signal_groups}`",
        f"- normalized output duplicate file-hash groups found: `{processed_duplicate_groups}`",
        "",
        "## Channel Policy",
        "",
        "Normalization uses a fixed target channel set for all retained subjects.",
        "",
        f"- target order used in outputs: `{', '.join(CANONICAL_CHANNEL_ORDER)}`",
        "- if a subject has the full target set in a different order, keep the subject and reorder channels",
        "- if a subject has extra channels but also contains the full target set, keep the subject and drop only the extra channels",
        "- if a subject is missing any required target channel, exclude the subject from the normalized derivative",
        "",
        "## What This Build Did",
        "",
        "1. Read each raw EDF recording with MNE.",
        "2. Classified each subject by channel compatibility before writing outputs.",
        "3. Dropped extra channels when present and reordered retained recordings into the cohort-majority order expected by the downstream pipeline.",
        "4. Preserved the original sampling frequency and full continuous duration for retained subjects.",
        "5. Saved each retained normalized recording as `rest_raw.fif` under a subject folder.",
        "6. Wrote hash manifests, inventories, exclusion tables, and validation tables under `manifests/`.",
        "",
        "## Notes",
        "",
        "- the raw audit found no exact duplicate EDF files",
        "- the raw audit found no duplicate decoded signal arrays",
        "- normalized output FIF file hashes are recorded in `manifests/processed_file_hashes.tsv`",
        "- subject-level exclusion reasons are recorded in `manifests/exclusions.tsv`",
        "- `h12.edf` was the only source file with a different source channel order in the current source archive",
        f"- subject 12 hardcoded reorder applied in normalization: `{'yes' if subject_12_reordered else 'no'}`",
        "- no filtering, rereferencing, resampling, epoching, or artifact rejection was applied",
        "",
        "## Excluded Subjects",
        "",
    ]
    if excluded_records:
        for record in excluded_records:
            lines.append(
                f"- `{record.source_name}`: excluded because required channels were missing "
                f"(`missing={channel_order_string(record.missing_channels) or 'none'}`, "
                f"`extra={channel_order_string(record.extra_channels) or 'none'}`)"
            )
    else:
        lines.append("- None. No source subject was missing required target channels in the current dataset.")

    lines.extend(
        [
            "",
            "## Rebuild",
            "",
            "Use the builder in the raw dataset root:",
            "",
            f"- `{raw_root / 'build_normalized_from_raw.py'}`",
            "",
            "Example:",
            "",
            "```bash",
            f"python {raw_root / 'build_normalized_from_raw.py'} \\",
            f"  {raw_root} \\",
            f"  {output_root}",
            "```",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    raw_root = args.raw_root.resolve()
    output_root = args.output_root.resolve()

    if args.clean:
        cleanup_output_root(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    records = collect_raw_records(raw_root)
    retained_records, excluded_records = split_records_by_channel_policy(records)
    if not retained_records:
        raise RuntimeError("No subjects remain after channel-compatibility filtering.")
    raw_hash_groups, signal_hash_groups = build_hash_groups(records)

    derivative_rows: list[dict[str, str]] = []
    processed_file_rows: list[dict[str, str]] = []
    validation_rows: list[dict[str, str]] = []
    exclusions_rows: list[dict[str, str]] = []

    mne.set_log_level("ERROR")

    for record in retained_records:
        output_path = output_root / normalized_relpath(record)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if args.overwrite or not output_path.exists():
            raw = mne.io.read_raw_edf(record.source_path, preload=True, infer_types=True, verbose="ERROR")
            raw.pick(list(CANONICAL_CHANNEL_ORDER))
            raw.reorder_channels(list(CANONICAL_CHANNEL_ORDER))
            raw.save(output_path, overwrite=True, verbose="ERROR")

        reopened = mne.io.read_raw_fif(output_path, preload=False, verbose="ERROR")
        output_relpath = output_path.relative_to(output_root)
        output_sha256 = compute_sha256(output_path)

        derivative_rows.append(
            {
                "source_name": record.source_name,
                "group": record.group,
                "original_subject_id": record.original_subject_id,
                "normalized_subject_id": record.normalized_subject_id,
                "output_relpath": str(output_relpath),
                "source_n_channels": str(record.n_channels),
                "output_n_channels": str(len(CANONICAL_CHANNEL_ORDER)),
                "sfreq": f"{record.sfreq:g}",
                "n_times": str(record.n_times),
                "duration_sec": f"{record.duration_sec:g}",
                "channel_policy": record.channel_policy,
                "missing_channels": channel_order_string(record.missing_channels),
                "extra_channels_dropped": channel_order_string(record.extra_channels),
                "canonical_channel_order": channel_order_string(CANONICAL_CHANNEL_ORDER),
            }
        )
        processed_file_rows.append(
            {
                "source_name": record.source_name,
                "group": record.group,
                "original_subject_id": record.original_subject_id,
                "normalized_subject_id": record.normalized_subject_id,
                "output_relpath": str(output_relpath),
                "output_bytes": str(output_path.stat().st_size),
                "output_sha256": output_sha256,
                "channel_policy": record.channel_policy,
            }
        )
        validation_rows.append(
            {
                "source_name": record.source_name,
                "output_relpath": str(output_relpath),
                "output_sha256": output_sha256,
                "channel_policy": record.channel_policy,
                "readable": "yes",
                "n_channels_match": "yes" if len(reopened.ch_names) == len(CANONICAL_CHANNEL_ORDER) else "no",
                "channel_order_match": "yes"
                if tuple(reopened.ch_names) == tuple(CANONICAL_CHANNEL_ORDER)
                else "no",
                "sfreq_match": "yes"
                if abs(float(reopened.info["sfreq"]) - record.sfreq) < 1e-9
                else "no",
                "duration_match": "yes"
                if reopened.n_times == record.n_times
                else "no",
            }
        )

    processed_hash_groups: dict[str, list[dict[str, str]]] = {}
    for row in processed_file_rows:
        processed_hash_groups.setdefault(row["output_sha256"], []).append(row)
    for row in processed_file_rows:
        row["processed_duplicate_group_size"] = str(len(processed_hash_groups[row["output_sha256"]]))
    processed_duplicate_groups = sum(1 for rows in processed_hash_groups.values() if len(rows) > 1)

    manifests_root = output_root / "manifests"
    manifests_root.mkdir(parents=True, exist_ok=True)

    write_tsv(
        manifests_root / "raw_file_hashes.tsv",
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
        manifests_root / "decoded_signal_hashes.tsv",
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
        manifests_root / "raw_inventory.tsv",
        [
            "source_name",
            "group",
            "original_subject_id",
            "normalized_subject_id",
            "header_patient_id",
            "meas_date_iso",
            "source_bytes",
            "n_channels",
            "sfreq",
            "n_times",
            "duration_sec",
            "annotations_count",
            "channel_policy",
            "missing_channels",
            "extra_channels",
            "channel_order_variant",
            "channel_order",
            "channel_set_hash",
            "raw_sha256",
            "signal_sha256",
        ],
        [
            {
                "source_name": record.source_name,
                "group": record.group,
                "original_subject_id": record.original_subject_id,
                "normalized_subject_id": record.normalized_subject_id,
                "header_patient_id": record.header_patient_id,
                "meas_date_iso": record.meas_date_iso,
                "source_bytes": str(record.source_bytes),
                "n_channels": str(record.n_channels),
                "sfreq": f"{record.sfreq:g}",
                "n_times": str(record.n_times),
                "duration_sec": f"{record.duration_sec:g}",
                "annotations_count": str(record.annotations_count),
                "channel_policy": record.channel_policy,
                "missing_channels": channel_order_string(record.missing_channels),
                "extra_channels": channel_order_string(record.extra_channels),
                "channel_order_variant": record.channel_order_variant,
                "channel_order": channel_order_string(record.channel_order),
                "channel_set_hash": record.channel_set_hash,
                "raw_sha256": record.raw_sha256,
                "signal_sha256": record.signal_sha256,
            }
            for record in records
        ],
    )
    exclusions_rows = [
        {
            "reason": record.channel_policy,
            "source_name": record.source_name,
            "group": record.group,
            "original_subject_id": record.original_subject_id,
            "missing_channels": channel_order_string(record.missing_channels),
            "extra_channels": channel_order_string(record.extra_channels),
            "notes": "Excluded from normalized derivative because one or more required target channels were missing.",
        }
        for record in excluded_records
    ]
    write_tsv(
        manifests_root / "derivative_inventory.tsv",
        list(derivative_rows[0].keys()),
        derivative_rows,
    )
    write_tsv(
        manifests_root / "processed_file_hashes.tsv",
        list(processed_file_rows[0].keys()),
        processed_file_rows,
    )
    write_tsv(
        manifests_root / "validation.tsv",
        list(validation_rows[0].keys()),
        validation_rows,
    )
    write_tsv(
        manifests_root / "exclusions.tsv",
        ["reason", "source_name", "group", "original_subject_id", "missing_channels", "extra_channels", "notes"],
        exclusions_rows,
    )

    write_text(
        output_root / "README.md",
        build_readme(
            records,
            retained_records,
            excluded_records,
            raw_root,
            output_root,
            raw_hash_groups,
            signal_hash_groups,
            processed_duplicate_groups,
        ),
    )

    print(f"Source root: {raw_root}")
    print(f"Output root: {output_root}")
    print(f"Recordings normalized: {len(records)}")
    print(f"Manifest date: {date.today().isoformat()}")


if __name__ == "__main__":
    main()
