# Repository preparation checks

Date: October 8, 2026. Platform: macOS. Interpreter: Python 3.10.20.

- All 6 existing software test methods passed, including synthetic image handling and end-to-end loopback HTTP requests.
- The public optional model-comparison CLI responds to `--help`; a new training-data refit was not performed during this packaging task.
- Application, prediction, test, and static frontend code are byte-identical to the supplied software.
- All numerical model parameters, including coefficients, training means, baseline survival values, grouping thresholds, and training summary, are unchanged. Only the provenance description was made independent of local file paths.
- The screenshot, compiled caches, existing ZIP, and participant-level data are excluded. No credential file or absolute author-computer path is included in the upload candidate.
- Windows is not independently validated. Automated tests do not replace clinical validation or a manual review of every supported image orientation.

Runtime versions: numpy 2.2.6, SimpleITK 2.5.4, Pillow 12.2.0. See `requirements-tested.txt` for the exact runtime dependency pins.
