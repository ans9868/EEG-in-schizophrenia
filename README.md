# EEG-in-schizophrenia

This repository packages the `EEG in schizophrenia` source dataset together with reproducible derivative builders and a raw-preserving BIDS conversion.

## Contents

- raw EDF source recordings in the repository root:
  - `h01.edf` through `h14.edf`
  - `s01.edf` through `s14.edf`
- source metadata:
  - `Metadata.md`
  - `MANIFEST.TXT`
- BIDS-organized packaging:
  - `BIDS/`
- reproducible builders:
  - `build_normalized_from_raw.py`
  - `build_bids_from_raw.py`
  - `schizophrenia_dataset_utils.py`
- planning and provenance docs:
  - `normalize_plan.md`
  - `BIDS_plan.md`
  - `CHANGE.md`

## What Is In `BIDS/`

`BIDS/` is a real BIDS-style packaging of the raw EDF source files.

It includes:

- copied EDF recordings in BIDS participant folders
- `participants.tsv`
- `participants.json`
- `dataset_description.json`
- per-recording `_eeg.json` and `_channels.tsv` files
- `sourcedata/` validation and hash manifests

## What Is Not Stored Here

The normalized analysis-ready derivative is built as a sibling directory:

- `/Users/user/eeg-datasets/EEG-in-schizophrenia_normalized`

It is reproducible from this repository using:

- `build_normalized_from_raw.py`

## Rebuild Commands

Build the normalized derivative:

```bash
python /Users/user/eeg-datasets/EEG-in-schizophrenia/build_normalized_from_raw.py \
  /Users/user/eeg-datasets/EEG-in-schizophrenia \
  /Users/user/eeg-datasets/EEG-in-schizophrenia_normalized
```

Build the BIDS packaging:

```bash
python /Users/user/eeg-datasets/EEG-in-schizophrenia/build_bids_from_raw.py \
  /Users/user/eeg-datasets/EEG-in-schizophrenia \
  /Users/user/eeg-datasets/EEG-in-schizophrenia/BIDS
```

## Notes

- the raw source EDF files were left unchanged
- the normalized derivative performs channel-order standardization and writes new FIF files
- the BIDS conversion preserves source EDF byte content and adds BIDS metadata
- hash manifests document uniqueness for raw files, normalized outputs, and BIDS copies
