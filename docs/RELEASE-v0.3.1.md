Editorial update using neutral product descriptions throughout the current application and documentation.

- Updated README, attribution text, in-app help and Debian package descriptions.
- MIT application license and required original/third-party copyright notices remain intact.
- No changes to measurements, GPU identification, refresh behavior or interface layout.
- Runtime libraries and native dependencies are unchanged from v0.3.0.
- 29 automated tests passed; the rebuilt portable GUI passed its four-GPU demo self-test.

Close the existing GUI before installing:

```sh
sudo apt install ./gputaskman-qt6_0.3.1-1_amd64.deb
```

The release includes the DEB, application/collector source archive, matching library source archive and SHA256SUMS. Corresponding-library source access and LGPL replacement instructions remain available.

Debian 13.7 and Ubuntu 26.04 X11/Wayland validation was performed on v0.3.0; this update changes descriptions only. Real NVIDIA multi-GPU hardware remains unvalidated. Earlier Git history and the previous release are retained.
