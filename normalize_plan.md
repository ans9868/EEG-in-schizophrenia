# Normalize Plan

## Goal

Create a reproducible, analysis-ready normalized derivative from the flat EDF dataset in:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia`

The normalized derivative should:

- preserve all 28 available recordings unless a clear data-integrity problem is found
- keep provenance back to the original raw EDF file for every output
- make channel order uniform across all recordings
- document hashes, validation checks, and any exclusions explicitly
- be rebuildable from the raw folder by one Python script

## What We Observed In The Current Raw Folder

Current source layout:

- `14` healthy control files: `h01.edf` through `h14.edf`
- `14` schizophrenia files: `s01.edf` through `s14.edf`
- `MANIFEST.TXT`
- `Metadata.md`

Observed structural facts:

- all `28` EDF files are readable with MNE
- all `28` files have `19` EEG channels
- all `28` files have sampling frequency `250 Hz`
- all `28` files have `0` embedded annotations
- all `28` files have unique byte-level SHA-256 hashes
- all `28` files also have unique decoded-signal SHA-256 hashes
- all `28` files share the same channel set
- `27` files share one channel order
- `h12.edf` has the same channels but a different order
- durations vary substantially, so recording length should not be normalized by truncation in the first pass

Interpretation:

- there is currently no evidence for exact duplicate files
- there is currently no evidence for hidden duplicate signals with different headers
- the main normalization need is channel-order standardization and explicit manifesting

## Normalized Output Design

Recommended output root:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized`

Recommended structure:

```text
EEG-in-schizophrenia_normalized/
  README.md
  build_from_raw.py
  healthy_controls/
    H_S01/
      rest_raw.fif
    ...
    H_S14/
      rest_raw.fif
  schizophrenia/
    SZ_S01/
      rest_raw.fif
    ...
    SZ_S14/
      rest_raw.fif
  manifests/
    raw_file_hashes.tsv
    decoded_signal_hashes.tsv
    raw_inventory.tsv
    derivative_inventory.tsv
    validation.tsv
    exclusions.tsv
```

Notes:

- use subject-organized folders rather than keeping a flat dump
- use `.fif` for the normalized derivative because it is convenient for MNE-based downstream work
- preserve one output file per subject because this dataset appears to contain one resting recording per participant

## Canonical Subject Mapping

Recommended normalized naming:

- controls:
  - `h01.edf -> healthy_controls/H_S01/rest_raw.fif`
  - ...
  - `h14.edf -> healthy_controls/H_S14/rest_raw.fif`
- schizophrenia:
  - `s01.edf -> schizophrenia/SZ_S01/rest_raw.fif`
  - ...
  - `s14.edf -> schizophrenia/SZ_S14/rest_raw.fif`

The normalized folder name should not discard the original file identity. Each manifest row should still carry:

- original filename
- original group code
- original subject label
- normalized subject label

## Canonical Channel Order

Use one explicit canonical order for every normalized recording:

`Fp1, Fp2, F7, F3, Fz, F4, F8, T3, C3, Cz, C4, T4, T5, P3, Pz, P4, T6, O1, O2`

Reason:

- this is the 19-channel 10-20 order stated in `Metadata.md`
- it makes the derivative easier to use for tabular feature extraction and model inputs
- it resolves the one known order inconsistency in `h12.edf`

## Normalization Rules

The first-pass normalized derivative should apply only conservative structural normalization.

Include:

1. Read each EDF with `mne.io.read_raw_edf(..., preload=True, infer_types=True)`.
2. Confirm that the file contains exactly the expected 19-channel set.
3. Reorder channels into the canonical order above.
4. Preserve the original sampling frequency of `250 Hz`.
5. Preserve the full recording duration.
6. Preserve the original signal values apart from channel reordering and format conversion.
7. Save as `rest_raw.fif`.

Do not apply in the first pass:

- filtering
- rereferencing
- ICA
- interpolation
- bad-channel removal
- resampling
- epoching
- artifact rejection
- duration trimming

## Duplicate And Hash Policy

This dataset should start with a "do not exclude unless justified" policy.

Rules:

1. Compute byte-level SHA-256 for every raw EDF.
2. Compute decoded-signal SHA-256 after reading the numeric signal array.
3. If two files share the same raw SHA-256, flag them as exact duplicates.
4. If two files differ at the file level but share the same decoded-signal hash, flag them as signal duplicates.
5. Do not remove anything automatically unless duplicate evidence is real and documented.
6. If an exclusion is ever made, write the reason and both hashes to `manifests/exclusions.tsv`.

Current expected outcome from the audit already run:

- exact duplicate groups: `0`
- decoded-signal duplicate groups: `0`

## Validation Plan

For each output file, verify:

- readable as FIF
- exactly `19` channels
- exact canonical channel order
- sampling frequency `250 Hz`
- output duration equals input duration
- normalized subject mapping is correct

Recommended manifest tables:

- `raw_file_hashes.tsv`
  - original filename
  - group
  - subject_id
  - bytes
  - raw_sha256
- `decoded_signal_hashes.tsv`
  - original filename
  - n_channels
  - sfreq
  - n_times
  - duration_sec
  - channel_order
  - signal_sha256
- `raw_inventory.tsv`
  - one row per raw EDF with all structural metadata
- `derivative_inventory.tsv`
  - one row per normalized output with source and output linkage
- `validation.tsv`
  - post-write checks for each derivative file
- `exclusions.tsv`
  - explicit removal decisions, if any

## README Content For The Normalized Derivative

The normalized `README.md` should explain:

- what the raw source folder contained
- that all 28 files were retained unless later evidence changes that
- that the dataset is a single-rest-recording-per-subject collection
- that all files share the same 19-channel set and 250 Hz sampling rate
- that one file had a different source channel order and was reordered
- that no exact duplicate or decoded-signal duplicate was found in the initial audit
- what preprocessing was and was not applied
- how to rebuild the derivative from the raw folder

## Script Design

Recommended builder:

- `build_from_raw.py`

Suggested behavior:

- input 1: raw source root
- input 2: normalized output root
- optional flags:
  - `--clean`
  - `--overwrite`
  - `--audit-only`

Recommended execution:

```bash
python /Users/user/eeg-datasets/EEG-in-schizophrenia_normalized/build_from_raw.py \
  /Users/user/eeg-datasets/EEG-in-schizophrenia \
  /Users/user/eeg-datasets/EEG-in-schizophrenia_normalized
```

## Open Questions

These should be documented but should not block the first normalized build:

- whether the recording condition should be labeled more specifically than generic resting state
- whether the header patient identifiers should be preserved in manifests or considered too identifying for shared releases
- whether later modeling should use full continuous data or a fixed-duration crop

## Bottom Line

This dataset appears clean enough that the normalized derivative should be a light-touch structural derivative, not a heavy cleaning pipeline.

The strongest expected value comes from:

- deterministic subject organization
- canonical channel order
- explicit hash manifests
- explicit validation tables
- one-script reproducibility
