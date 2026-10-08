# Software validation

## Run public checks

```bash
python -m unittest -v test_app
```

The suite uses synthetic inputs and images and checks frozen numerical examples, monotonicity, input validation, macOS launcher dispatch, handling of an existing local server, NIfTI/NIfTI-GZip/NRRD loading, spacing-aware slice dimensions, and authenticated HTTP upload/prediction/clear behavior and memory/count limits. It does not require participant data. These tests do not establish clinical validity or all image-orientation behavior.

## Optional original-data comparison

```bash
python -m pip install -r requirements-validation.txt
python scripts/verify_model.py --training-data /path/to/authorized/oai_train.parquet
```

The file must reproduce the original development analysis set and preprocessing and contain `age`, `sex_num`, `cart_area_PL`, `cart_area_FMA`, `bml_size_SS`, `event`, and `time_months`. Event is the original 0/1 event indicator; time is in months. This script refits the Cox model and checks coefficients, training means, median/tertile thresholds, and row-wise 5/10-year probabilities. It exports only aggregate comparison results. The training file and its preparation pipeline are not included. It is not a generic new-cohort evaluation script.

## Historical local evidence

The original developer record dated October 1 and October 4, 2026 reports matching the implementation to a refit on all 3937 development knee records, with maximum probability error 4.440892098500626e-16. This is a historical local record, not a new public-data replication. Browser checks used synthetic inputs/volumes. Windows was not tested on a physical Windows host. No patient screenshot is distributed in this repository candidate.

Repository-preparation checks and environment versions are recorded in `VALIDATION_CURRENT.md` after execution. Software consistency does not establish externally calibrated individual risk or clinical benefit.
