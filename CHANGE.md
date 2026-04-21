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
- the channel set was checked against one required target channel set
- if extra channels were present, they would be dropped before writing the normalized derivative
- if required channels were missing, the subject would be excluded from the normalized derivative
- retained subjects had their channels reordered into the cohort-majority order expected by the downstream pipeline
- the result was saved as a new `.fif` file named `rest_raw.fif`

Target output order used:

- `Fp2, F8, T4, T6, O2, Fp1, F7, T3, T5, O1, F4, C4, P4, F3, C3, P3, Fz, Cz, Pz`

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

### Channel compatibility rule

Normalization now follows this explicit rule:

- same required channels, different order:
  keep subject and reorder channels
- required channels plus extras:
  keep subject and drop extras
- missing any required channel:
  exclude subject from the normalized derivative

### Hash and uniqueness results

Evidence files:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized/manifests/raw_file_hashes.tsv`
- `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized/manifests/decoded_signal_hashes.tsv`
- `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized/manifests/processed_file_hashes.tsv`

Current result:

- raw EDF duplicate hash groups: `0`
- decoded-signal duplicate hash groups: `0`
- normalized FIF duplicate file-hash groups: `0`
- normalized exclusions for missing required channels: `0`
- subject `h12.edf` is retained and explicitly reordered into the target output order

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

- the source EDF was packaged into a BIDS participant folder
- the filename was changed to BIDS form such as `sub-001_task-rest_eeg.edf`
- a matching `_eeg.json` sidecar was written
- a matching `_channels.tsv` sidecar was written
- for `h12.edf`, the EDF was intentionally rewritten into the target output order before being placed in BIDS

Before a source subject is packaged into BIDS:

- if the subject has the full required target channel set, it is retained
- if the subject is missing any required target channel, it is excluded from BIDS entirely
- excluded source subjects do not leave gaps in BIDS participant numbering

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

- `27` BIDS EDF files preserve the source EDF byte content exactly
- `h12.edf` does not preserve source byte content exactly because it is intentionally reordered to the expected cohort-majority order
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
- copied BIDS EDF intentional source-hash mismatches: `1`
- BIDS exclusions for missing required channels: `0`

Interpretation:

- every BIDS EDF copy is unique
- all retained BIDS EDF files except `h12.edf` match their source EDF hash exactly
- `h12.edf` is intentionally rewritten into the expected channel order and therefore has a different file hash

## Difference Between The Two Derived Levels

Normalized derivative:

- intended for downstream analysis convenience
- changes file format to FIF
- standardizes channel order
- keeps one subject-organized recording file per participant

BIDS packaging:

- intended for standardized dataset organization and metadata
- keeps EDF as the recording format
- preserves source channel order for all subjects except the known `h12` outlier
- excludes source subjects if required target channels are missing
- adds BIDS names, sidecars, and participant metadata

## Bottom Line

This work was not just an audit.

Real outputs were created at both derived levels:

- a real normalized derivative with new FIF files
- a real BIDS directory with copied EDF files and sidecars

The raw source remains unchanged, and the current hash manifests indicate that all raw, normalized, and BIDS recording files are unique at the file-hash level within their respective builds.

For the current source dataset, no subject triggered the missing-channel exclusion rule, so both derived levels still contain all `28` source subjects.

The one deliberate hardcoded exception is subject `h12.edf`, which is rewritten in both derived levels so its channel order matches the cohort-majority order expected by the downstream pipeline.
