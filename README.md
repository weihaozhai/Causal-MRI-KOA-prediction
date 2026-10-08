# OAI Knee Risk Studio

A local, single-user research application for viewing knee MRI volumes and calculating knee replacement net-risk estimates from a frozen five-predictor Cox model.

[Model documentation](docs/MODEL_CARD.md) · [Validation](docs/VALIDATION.md) · [Data availability](docs/DATA_AVAILABILITY.md)

## Scope

Enter age, sex, lateral patellar cartilage-area grade, anterior medial femoral cartilage-area grade, and tibial-spine BML-size grade manually. The application reports 5- and 10-year net-risk estimates, a training-cohort median group, and a training-cohort tertile group. MRI upload is optional. One calculation represents one knee; score and calculate the two knees separately.

This repository contains the calculator, MRI viewer, frozen aggregate model parameters, and software tests. It does **not** contain participant-level data, MRI images, model-development data, the full causal-analysis pipeline, or scripts reproducing all manuscript results. No automated segmentation or MOAKS scoring is performed.

Related manuscript: *MRI-Defined Structural Burden and Regional Abnormalities in Knee Osteoarthritis: Causal Estimates and Multi-Center Prognostic Validation*. Publication identifier has not yet been assigned.

## Installation and launch

Use Python 3.10 or later. Python 3.10 is the currently tested interpreter; other versions/platforms are not yet independently verified. From this repository directory, with your chosen Python environment active:

```bash
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8765 if the browser does not open automatically. Stop with Ctrl+C. To use another port or avoid opening the browser:

```bash
python app.py --port 8766 --no-browser
```

macOS: run `bash start_mac.command`. Windows: run `start_windows.bat` after installing Python. These launchers use the active/available Python and install missing runtime dependencies; initial installation requires internet access. Windows has not been tested on a physical Windows host. Once installed, the application uses local resources and can run offline.

## Manual prediction without the viewer

The prediction module uses only the Python standard library:

```bash
python -c 'import json; from predictor import predict; print(json.dumps(predict(json.load(open("examples/example_input.json"))), indent=2))'
```

The example is synthetic and does not represent a participant. See [input definitions and equations](docs/MODEL_CARD.md).

## Viewer

Self-contained `.nii`, `.nii.gz`, and `.nrrd` files are supported. Only 3D scalar volumes are accepted, up to 200 MB and 64 million voxels per file; at most 12 sequences and 512 MB of voxel arrays may be loaded. DICOM folders, 4D series, vector images, and NRRD external-data references are not supported. Use de-identified images with correct spatial orientation and millimeter spacing.

Each of the sagittal, coronal, and axial panels can select a separate sequence and adjust its slice/window/zoom. Sequences are not registered and slice positions are not synchronized. Oblique data retain acquisition axes rather than being resampled to orthogonal anatomical planes. Proper MOAKS assessment requires appropriate sequences and a complete professional reading.

## Verify the software

```bash
python -m unittest -v test_app
```

Tests create synthetic volumes and run a temporary loopback HTTP server. No study data or internet connection is required after dependencies are installed. An optional, separately documented [training-data comparison](docs/VALIDATION.md) requires authorized data access and additional packages.

## Interpretation and local data handling

The probabilities are death-censored Cox **net risks**, not competing-risk cumulative incidences. External individual-risk calibration, prediction intervals, and clinical utility have not been established. The median/tertile groups are cohort-relative categories, not thresholds for surgery. Inputs outside the OAI enrollment age range of 45–79 years are flagged as extrapolation. Research use only; outputs must not determine patient management.

The server binds to `127.0.0.1`; it is intended for one local user and does not upload to a cloud service. Image state is shared within the process. Temporary files are deleted after reading; image arrays remain in process memory until cleared or the process exits. Exported prediction JSON excludes images and file names. This does not guarantee secure erasure of OS swap/browser memory or de-identification of imported images.

## Citation and permissions

Software version: 1.0.0. Machine-readable software citation metadata are in `CITATION.cff`; the related manuscript is identified above. Cite the release/tag actually used once the authors publish it.

A reuse license has not yet been selected. See [LICENSE_NOTICE.md](LICENSE_NOTICE.md); public repository visibility alone does not grant a software reuse license. Dependency licenses remain with their respective projects. Manuscript correspondence: Yong Lu, 18917762053@163.com.

## Repository contents

```text
app.py                 Local viewer and HTTP server
predictor.py           Frozen Cox prediction implementation
model.json             Coefficients, means, survival values, thresholds
static/                Local HTML, JavaScript, and CSS
examples/              Synthetic prediction example only
test_app.py            Synthetic software and HTTP tests
scripts/verify_model.py  Optional authorized training-data comparison
docs/                  Model, validation, and data documentation
requirements.txt       Runtime dependency ranges
requirements-validation.txt  Optional comparison dependencies
CITATION.cff           Software citation metadata
```
