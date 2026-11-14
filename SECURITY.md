# Security

Only the installed read-only collector is elevated through Polkit. The GUI is
unprivileged; no driver configuration, process termination, kernel setting change
or remote telemetry is performed. Never make the collector or its runtime
writable by ordinary users. The GUI must not authorize arbitrary interpreters.

Do not post unredacted process snapshots, serials, UUIDs, paths or credentials in
public issues. For a security issue, use GitHub private vulnerability reporting
when enabled, or contact the repository owner privately.

The first public release is experimental. Real multi-NVIDIA hardware, native
Wayland/X11 combinations and driver-failure recovery need community validation.
Dependency/runtime updates require rechecking source and LGPL notices.
