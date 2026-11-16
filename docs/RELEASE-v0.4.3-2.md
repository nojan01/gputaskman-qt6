Fix Diagnostics scrolling and add a portable x86_64 AppImage.

- Keep the current Diagnostics scroll position when fresh readings arrive.
- Avoid rebuilding unchanged diagnostic text.
- Upstream collector remains 0.4.3; Debian/Qt integration revision is 2.
- AppImage includes the GUI, collector, licenses and sources; standard access works without DEB installation. Full counter access requires the matching DEB-installed collector and Polkit policy. Playback needs no elevated privileges.

Install the DEB after closing the application, or mark the AppImage executable and launch it. If FUSE is unavailable, use `./GPU-Task-Manager-0.4.3-2-x86_64.AppImage --appimage-extract-and-run`.

35 automated tests and the frozen GUI self-test passed. AppImage smoke tests are documented in VALIDATION.md. Native hardware coverage remains unchanged: no independent multi-NVIDIA or Intel-Xe hardware validation.

Assets include DEB, AppImage, application sources, Qt/Python dependency sources, AppImage runtime/libfuse sources and SHA256SUMS.
