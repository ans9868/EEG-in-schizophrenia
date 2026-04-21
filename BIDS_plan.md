# BIDS Plan

## Goal

Create a BIDS-organized EEG dataset from the flat EDF source in:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia`

The BIDS conversion should:

- preserve the raw EDF recordings as the recording layer when possible
- avoid unnecessary signal changes
- assign canonical BIDS participant IDs
- store diagnosis/group in metadata instead of filenames
- include strong provenance and validation tables
- remain honest about any uncertainty in the original recording-condition label

## Recommended BIDS Strategy

For this dataset, BIDS should be built directly from the raw EDF files rather than from a normalized FIF derivative.

Reason:

- EDF is already a valid EEG recording format for BIDS
- all files are readable and structurally consistent
- the source data does not appear to require aggressive cleaning before BIDS packaging
- preserving source EDF files in the BIDS layer keeps the conversion closer to the original archive

The normalized derivative should still exist, but it should be a separate derivative path rather than the source for the first BIDS release.

## Proposed BIDS Root

Recommended output root:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia_BIDS`

Recommended structure:

```text
EEG-in-schizophrenia_BIDS/
  README
  CHANGES
  dataset_description.json
  participants.tsv
  participants.json
  sourcedata/
    original_manifest.tsv
    raw_file_hashes.tsv
    decoded_signal_hashes.tsv
    recording_inventory.tsv
    validation.tsv
  sub-001/
    eeg/
      sub-001_task-rest_eeg.edf
      sub-001_task-rest_eeg.json
      sub-001_task-rest_channels.tsv
  ...
  sub-028/
    eeg/
      ...
```

## Canonical Participant IDs

Use neutral BIDS subject IDs and preserve diagnosis in metadata only.

Recommended deterministic mapping:

1. healthy controls first, ascending by original number
2. schizophrenia second, ascending by original number

Example mapping:

- `h01 -> sub-001`
- `h02 -> sub-002`
- ...
- `h14 -> sub-014`
- `s01 -> sub-015`
- ...
- `s14 -> sub-028`

Store original identities in metadata:

- `group = control` or `schizophrenia`
- `original_subject_id = h01 ... h14 / s01 ... s14`

## BIDS Task Label

The safest initial BIDS task label is:

- `task-rest`

Reason:

- the local source files contain no embedded annotations indicating condition
- `Metadata.md` describes the montage and groups but does not explicitly say eyes open or eyes closed
- secondary literature suggests this may be eyes-closed resting-state EEG, but that should be verified against a primary dataset description before hard-coding `task-eyesclosed`

Recommended rule:

- first BIDS build uses `task-rest`
- if a primary-source confirmation is obtained later, a documented rename to `task-eyesclosed` can be performed

## BIDS Sidecar Content

Each recording should have:

- `.edf` file copied from the source archive or rewritten only if necessary for BIDS naming
- `_eeg.json`
- `_channels.tsv`

Recommended `_eeg.json` fields:

- `TaskName`
- `SamplingFrequency`
- `EEGReference`
- `RecordingType`
- `EEGChannelCount`
- `EEGPlacementScheme`
- `PowerLineFrequency`
- `SoftwareFilters`

Recommended values from current evidence:

- `SamplingFrequency`: `250`
- `RecordingType`: `continuous`
- `EEGChannelCount`: `19`
- `EEGPlacementScheme`: `International 10-20 system`
- `PowerLineFrequency`: `n/a` unless confirmed from a primary source
- `SoftwareFilters`: `n/a`
- `EEGReference`: describe the source reference as stated in `Metadata.md`

Recommended `_channels.tsv` content:

- `name`
- `type`
- `units`
- `sampling_frequency`
- `reference`
- `status`
- `status_description`

## Channel Order Policy In BIDS

Important distinction:

- the BIDS dataset should preserve source recording content as faithfully as possible
- the normalized derivative should enforce canonical channel order for downstream analysis

Because `h12.edf` has a different channel order from the other files, we should choose one of two explicit policies and document it.

Recommended policy:

- keep the original source order in the BIDS recording file
- write the observed channel order accurately in `_channels.tsv`
- reserve channel-order standardization for the normalized derivative

Reason:

- this keeps the BIDS layer closer to source truth
- it avoids silent signal rearrangement in what is supposed to be the raw-organized layer

## Duplicate And Hash Policy For BIDS

Before writing BIDS, generate source-validation tables:

- `raw_file_hashes.tsv`
- `decoded_signal_hashes.tsv`
- `recording_inventory.tsv`
- `validation.tsv`

Decision rules:

1. If exact raw-file duplicates are present, keep one canonical file and document the omitted duplicate in `sourcedata`.
2. If decoded-signal duplicates are present across different filenames, do not exclude automatically; flag them for review first.
3. If no duplicates are found, explicitly state that outcome in `README`.

Current expected result from the audit already run:

- exact raw duplicates: `0`
- decoded-signal duplicates: `0`

## Participants Metadata

Recommended `participants.tsv` columns:

- `participant_id`
- `group`
- `original_subject_id`
- `source_filename`
- `recording_duration_sec`

Recommended `participants.json` descriptions:

- define `group`
- define `original_subject_id`
- explain that `participant_id` is a canonical BIDS identifier assigned during conversion

## Dataset-Level Documentation

The BIDS `README` should explain:

- the original folder was a flat EDF dataset
- there are `14` controls and `14` schizophrenia recordings
- all files are single continuous EEG recordings with `19` channels at `250 Hz`
- the initial audit found no exact duplicate files
- the initial audit found no duplicate decoded signals
- one file had a different source channel order
- BIDS preserves source EDF organization, while normalized derivatives handle canonical channel order
- the task label is provisionally `rest` unless primary-source confirmation supports a more specific label

The `CHANGES` file should log:

- initial BIDS conversion date
- mapping rule used for canonical participant IDs
- audit outcome for duplicates and channel-order findings

The `dataset_description.json` should include:

- dataset name
- BIDS version
- dataset type `raw`
- generator script information
- source dataset description

## Validation Plan

After building BIDS, verify:

- BIDS root files exist
- all `28` participant folders exist
- each participant has one EEG recording
- each EEG recording has matching `_eeg.json` and `_channels.tsv`
- `participants.tsv` and `participants.json` reconcile with the files
- source filename to BIDS filename mapping is complete
- file counts match the source inventory
- SHA-256 values recorded in `sourcedata` match the source archive

Optional but recommended:

- run `bids-validator` and save a short validator report

## Script Design

Recommended builder:

- `build_bids_from_raw.py`

Suggested behavior:

- input 1: raw source root
- input 2: BIDS output root
- optional flags:
  - `--clean`
  - `--overwrite`
  - `--task-label rest`

Recommended execution:

```bash
python /Users/user/eeg-datasets/EEG-in-schizophrenia_BIDS/build_bids_from_raw.py \
  /Users/user/eeg-datasets/EEG-in-schizophrenia \
  /Users/user/eeg-datasets/EEG-in-schizophrenia_BIDS
```

## Relationship Between BIDS And Normalized Data

Recommended overall project logic:

1. raw flat EDF source
2. BIDS-organized raw-preserving dataset
3. normalized derivative for analysis convenience

In other words:

- BIDS answers: "how do we organize and document the source data cleanly?"
- normalization answers: "how do we make modeling and downstream analysis consistent?"

Keeping these separate avoids confusion between provenance preservation and analysis convenience.

## Bottom Line

This dataset is already close to BIDS-ready.

The main BIDS work is not heavy cleaning. It is:

- deterministic subject mapping
- metadata sidecars
- provenance tables
- explicit duplicate/hash documentation
- clear documentation of the one observed channel-order inconsistency
