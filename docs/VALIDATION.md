# Release v0.3.0 validation

Primary targets: **Debian 13.7** and **Ubuntu 26.04**, Linux amd64.
The final DEB was installed in clean official containers for both releases.
The Debian image explicitly reported `DEBIAN_VERSION_FULL=13.7`.

| Check | Debian 13.7 | Ubuntu 26.04 |
|---|---|---|
| apt installation of final DEB / runtime dependencies | passed | passed |
| bundled PySide6/Qt GUI, 4 and 16 synthetic GPUs | passed | passed |
| live collector communication, navigation and clean shutdown | passed | passed |
| X11/XCB via Xvfb, 1024×768 | passed | passed |
| Wayland via headless Weston, 1024×768 | passed | passed |
| collector JSON sample and stable Intel PCI identity | passed | passed |

29 automated GUI/identity/fleet/refresh tests passed after the PySide6 migration.
Cases cover 4/8/16 identical models, reordered indices, UUID/PCI identity,
unsupported serials, offline/replaced cards, history isolation, unknown vs zero,
absolute memory charts, pause and refresh changes without restarting the worker.

Qt/PySide6 6.8.3, Python 3.12.3 and PyInstaller 6.22.3 are recorded in BUILDINFO.json.
The GUI imports only QtCore/QtGui/QtWidgets. Transitive LGPL Qt modules are listed
in THIRD_PARTY.md. No PyQt6, QtVirtualKeyboard, QtPdf or QtQuick/QML is bundled.
Matching library source archives and license texts accompany the release.

The existing local TUI was not changed. Real multi-NVIDIA hardware was not
available: simulated fleets do not validate real driver behavior or performance.
The native tests above use virtual X11/Wayland servers inside containers, not
physical iLO hardware. They do not establish compatibility with every desktop,
GPU driver, MIG configuration, authentication agent or server firmware.
MIG instances are not separately monitored. NVIDIA/AMD hardware reports are welcome.

## 0.4.3 / 2026-11-16

Unmodified upstream v0.4.3 collector integrated. 682 upstream tests completed successfully (6 platform skips); 34 Qt/integration tests passed. Frozen GUI passed live collector/navigation and 16-GPU demo self-tests. Fresh package installation passed in Debian 13.7 and Ubuntu 26.04 containers: offscreen 4/16-GPU demos, real collector communication, X11/XCB and headless Wayland at 1024×768. Container tests do not validate physical Intel Xe or multi-NVIDIA hardware, GPU performance-counter permissions or real iLO behavior.
