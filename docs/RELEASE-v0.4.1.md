Record and replay GPU measurements, with optional automatic recording duration.

- Record complete all-GPU samples to JSONL files.
- Load recordings, pause/resume, rewind and play at 0.5× to 4× speed. Live collection stops during playback.
- Set recording duration from 1 minute to 7 days, or choose Unlimited. A countdown shows remaining elapsed time; acquisition pauses count toward the duration. Files close automatically while live monitoring continues.
- Display device counter warnings once in All GPUs, next to the affected GPU.
- Preserve MIT application licensing and required third-party notices/source access.

Close the application before installing:

```sh
sudo apt install ./gputaskman-qt6_0.4.1-1_amd64.deb
```

Recordings can include hardware identifiers, process details and local paths. Playback currently loads files up to 256 MB into memory. Recording streams to disk.

Validation: 33 automated tests and the frozen four-GPU GUI self-test passed. Tests cover recording round-trip, playback controls, invalid headers, automatic expiry during pause and unlimited recording. Debian 13.7 and Ubuntu 26.04 X11/Wayland installation checks were performed on v0.3.0; collector and runtime dependencies are unchanged. This version has not repeated those full OS checks. Real multi-NVIDIA hardware remains unvalidated.

Assets include the DEB, application/collector sources, corresponding library sources and SHA256SUMS.
