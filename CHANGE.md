# Change Summary

## Scope

This document explains what changed between the three dataset levels now present around this source dataset:

1. raw flat EDF source:
   - `/Users/user/eeg-datasets/EEG-in-schizophrenia`
2. normalized derivative:
   - `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized`
3. BIDS-organized raw-preserving packaging:
   - `/Users/user/eeg-datasets/EEG-in-schizophrenia/BIDS`

The raw EDF source files were not modified in place.

## Raw Source

Current raw-source contents:

- `14` healthy control EDF files: `h01.edf` through `h14.edf`
- `14` schizophrenia EDF files: `s01.edf` through `s14.edf`
- `Metadata.md`
- `MANIFEST.TXT`

Observed raw-source properties:

- all `28` EDF files are readable
- all `28` EDF files have `19` EEG channels
- all `28` EDF files have sampling frequency `250 Hz`
- all `28` EDF files have `0` embedded annotations
- all `28` raw EDF file SHA-256 hashes are unique
- all `28` decoded signal-array SHA-256 hashes are unique
- all `28` files share the same channel set
- `27` files share one source channel order
- `h12.edf` uses a different source channel order

## Raw -> Normalized

Normalized output root:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized`

Builder:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia/build_normalized_from_raw.py`

### What changed

The normalized derivative makes real derivative files.

Per recording:

- the raw EDF was read with MNE
- the channel set was verified
- the channels were reordered into one canonical 19-channel 10-20 order
- the result was saved as a new `.fif` file named `rest_raw.fif`

Canonical channel order used:

- `Fp1, Fp2, F7, F3, Fz, F4, F8, T3, C3, Cz, C4, T4, T5, P3, Pz, P4, T6, O1, O2`

Structural changes:

- flat filenames became subject-organized folders
- controls were written under `healthy_controls/H_S##/`
- schizophrenia recordings were written under `schizophrenia/SZ_S##/`
- recording container format changed from `EDF` to `FIF`
- manifests and validation tables were written under `manifests/`

### What did not change

- no subjects were removed
- no filtering was applied
- no rereferencing was applied
- no resampling was applied
- no epoching was applied
- no artifact rejection was applied
- no duration trimming was applied

### Hash and uniqueness results

Evidence files:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized/manifests/raw_file_hashes.tsv`
- `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized/manifests/decoded_signal_hashes.tsv`
- `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized/manifests/processed_file_hashes.tsv`

Current result:

- raw EDF duplicate hash groups: `0`
- decoded-signal duplicate hash groups: `0`
- normalized FIF duplicate file-hash groups: `0`

Interpretation:

- every normalized output file is unique at the file-hash level in this build

## Raw -> BIDS

BIDS output root:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia/BIDS`

Builder:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia/build_bids_from_raw.py`

### What changed

The BIDS output is a real BIDS-style packaging, not just a report.

Per recording:

- the original EDF was copied into a BIDS participant folder
- the filename was changed to BIDS form such as `sub-001_task-rest_eeg.edf`
- a matching `_eeg.json` sidecar was written
- a matching `_channels.tsv` sidecar was written

Dataset-level files created:

- `participants.tsv`
- `participants.json`
- `dataset_description.json`
- `README`
- `CHANGES`
- `.bidsignore`
- `sourcedata/` provenance and validation tables

Participant mapping rule:

1. controls first, ascending by original subject number
2. schizophrenia second, ascending by original subject number

Example:

- `h01 -> sub-001`
- `h12 -> sub-012`
- `s01 -> sub-015`
- `s14 -> sub-028`

### What did not change

- the BIDS EDF files preserve the source EDF byte content
- source channel order is preserved in the BIDS EDF files
- no signal-level preprocessing was applied during BIDS packaging

Important note:

- the BIDS task label is currently `rest`
- it was not renamed to `eyesclosed` because the local source metadata does not explicitly confirm that condition

### Hash and uniqueness results

Evidence files:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia/BIDS/sourcedata/raw_file_hashes.tsv`
- `/Users/user/eeg-datasets/EEG-in-schizophrenia/BIDS/sourcedata/decoded_signal_hashes.tsv`
- `/Users/user/eeg-datasets/EEG-in-schizophrenia/BIDS/sourcedata/bids_file_hashes.tsv`
- `/Users/user/eeg-datasets/EEG-in-schizophrenia/BIDS/sourcedata/validation.tsv`

Current result:

- raw EDF duplicate hash groups: `0`
- decoded-signal duplicate hash groups: `0`
- copied BIDS EDF duplicate file-hash groups: `0`
- copied BIDS EDF source-hash mismatches: `0`

Interpretation:

- every BIDS EDF copy is unique
- every BIDS EDF copy matches its source EDF hash exactly

## Difference Between The Two Derived Levels

Normalized derivative:

- intended for downstream analysis convenience
- changes file format to FIF
- standardizes channel order
- keeps one subject-organized recording file per participant

BIDS packaging:

- intended for standardized dataset organization and metadata
- keeps EDF as the recording format
- preserves source channel order
- adds BIDS names, sidecars, and participant metadata

## Bottom Line

This work was not just an audit.

Real outputs were created at both derived levels:

- a real normalized derivative with new FIF files
- a real BIDS directory with copied EDF files and sidecars

The raw source remains unchanged, and the current hash manifests indicate that all raw, normalized, and BIDS recording files are unique at the file-hash level within their respective builds.
