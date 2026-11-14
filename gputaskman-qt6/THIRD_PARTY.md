# Third-party licenses and replaceable runtime

The application code and original icon are MIT, Copyright (c) 2026 Norbert Jander.
The original collector is MIT, Copyright (c) 2026 Scott Hanselman. Its complete
license is retained in `runtime-notices/LICENSE` and in the installed collector.
MIT does not relicense the following third-party components.

## Qt / PySide6 / Shiboken

The portable GUI uses PySide6/Shiboken 6.8.3 and Qt 6.8.3 under LGPLv3 for the
selected shared libraries. It imports only QtCore, QtGui and QtWidgets. QtDBus,
QtOpenGL, QtXcbQpa, QtWaylandClient and QtSvg libraries/plugins are transitive
runtime dependencies of those essential modules. No QtCharts, QtVirtualKeyboard,
QtPdf, QtQuick/QML or other GPL-only optional runtime modules are shipped.
PyQt6 is not used or bundled in this release.

The full LGPLv3 and GPLv3 texts (the latter incorporated by LGPLv3) are included in
`third-party/`. Upstream copyright/permission notices are collected under
`third-party/notices/`. PySide's source archive also includes Shiboken and its
build/generation tools, including their separately licensed portions.

**Corresponding sources are available alongside the DEB at the same release:**
https://github.com/nojan01/gputaskman-qt6/releases/tag/v0.3.0

Download `gputaskman-qt6_0.3.0_third-party-sources.tar` and verify `SHA256SUMS`.
It contains the unmodified official PySide/Shiboken source, QtBase, QtSvg,
QtWayland 6.8.3 sources and ICU 73.2 source. Original download URLs and per-file
hashes are recorded in `third-party/sources.json`. We do not modify Qt/PySide.
Application/packaging source is a separate release asset and also included in
`/usr/share/doc/gputaskman-qt6/complete-source.tar.gz`.

### Replacing the libraries and using modified builds

Qt/PySide libraries are shared, not statically linked into application code. They
are in `/opt/gputaskman-qt6/gui/_internal/PySide6/` and the Shiboken directory
beside it. Administrators can replace these files with ABI-compatible modified
builds. No signature check, license key or technical lock prevents replacement.

For a user-writable copy without modifying `/opt`:

```sh
mkdir unpacked
cd unpacked
dpkg-deb -x ../gputaskman-qt6_0.3.0-1_amd64.deb .
# Replace ABI-compatible Qt/PySide/Shiboken shared libraries under opt/ here.
./opt/gputaskman-qt6/gui/gputaskman-qt6 --demo
```

For full access, the installed root-owned collector and its Polkit policy remain
separate. Modifying the GUI never requires replacing that privileged collector.
The application imposes no restriction on modifying/relinking the libraries or
reverse engineering for debugging such modifications. Qt/PySide build instructions
are contained in the corresponding source archives and the official documentation:
https://doc.qt.io/qtforpython-6/building_from_source/index.html
https://doc.qt.io/qt-6.8/build-sources.html

If you redistribute the binaries, preserve the notices and LGPL texts and provide
the corresponding library source with equivalent access; the project's own MIT
license does not remove those requirements. Providing library sources only in a
private repository is not equivalent access for public binary recipients.

## Other runtime components

ICU 73.2 uses its Unicode/ICU licenses, not the application's MIT license.
QtBase/QtSvg/QtWayland include third-party code under their documented licenses;
corresponding upstream notices are preserved in `third-party/notices/`.
The frozen Python 3.12 runtime, PyInstaller bootloader, NVIDIA Python bindings
and other Python dependencies retain their existing notices in `runtime-notices/`
and the installed `runtime-licenses/` / collector `licenses/` directories.
Standard system desktop libraries are dependencies installed by apt; they are
not embedded in the portable GUI bundle. NVIDIA driver libraries are not shipped.
