First public MIT/PySide6 release of GPU Task Manager Qt 6.

- Application code and original icon: MIT; original Scott Hanselman collector attribution preserved.
- PyQt6 replaced by PySide6; selected Qt/PySide shared libraries remain LGPLv3.
- Portable GUI runtime; no target-side pip/PyQt installation required.
- Exact Debian 13.7 and Ubuntu 26.04 DEB installation, offscreen, X11 and Wayland tests passed.
- Stable NVIDIA UUID / full PCI identity, optional serial numbers, All GPUs view and independent histories.
- GPU selection and refresh changes do not restart the privileged collector or re-prompt for a password.
- Absolute memory charts when GPU capacity is unavailable; unknown values remain n/a.
- 29 automated tests passed. Four/eight/sixteen-card fleets are simulated, not real hardware validation.

Install after closing the existing GUI:

```sh
sudo apt install ./gputaskman-qt6_0.3.0-1_amd64.deb
```

The window runs as your user; only the read-only collector uses Polkit elevation.
The existing TUI is unchanged. No kernel settings or GPU drivers are modified.

Assets:
- `gputaskman-qt6_0.3.0-1_amd64.deb`: amd64 package.
- `gputaskman-qt6_0.3.0-1_source.tar.gz`: application + original collector source/build files.
- `gputaskman-qt6_0.3.0_third-party-sources.tar`: matching unmodified Qt/PySide/Shiboken/ICU sources.
- `SHA256SUMS`: checksums for the above.

Please preserve third-party license texts and equivalent source access when redistributing binaries.
See THIRD_PARTY.md for LGPL library replacement/relinking instructions and source details.
Real NVIDIA multi-GPU servers and physical iLO sessions still need community validation.
