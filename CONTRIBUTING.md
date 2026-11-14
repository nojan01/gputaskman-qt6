# Contributing

Use the build/test instructions in README.md. Changes should keep unavailable
values distinct from zero, preserve measured/inferred/runtime-reported evidence,
and never attribute model weights to a device without evidence.

For GPU reports include OS/kernel/driver, GPU model, whether standard or full
access was used, the relevant identity/counter warning and reproduction steps.
Redact serials, UUIDs, local paths and model names before sharing snapshots.
Tests with mocked 4/8/16-card fleets do not establish real hardware support.

New contributions are accepted under MIT, preserving third-party notices.
Do not add GPL-only Qt modules to the LGPL runtime bundle.
