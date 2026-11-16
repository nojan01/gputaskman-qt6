Integrate the unmodified gputaskman v0.4.3 collector (commit dd5c4a17920aa8a75943409bb9184090ce04a468).

- Adopt Intel Xe process memory/cycle accounting and primary-GT frequency/throttle support. Hardware validation remains limited to upstream contributor reports; not independently verified here.
- Include upstream vLLM/llama-server gauges and show available request counts / KV-cache pool usage in process details, explicitly runtime-reported at server scope.
- Retain Qt multi-GPU identities, charts, recording, playback and recording duration. The compact TUI is unchanged.
- Qt and upstream version numbers now align: 0.4.3; Debian revision -1. The sidebar and --version identify the version. Future integration-only fixes use Debian revisions.
- The collector also incorporates upstream AMD-WSL and model-path fixes; our supported package scope remains native Linux.

Qt recordings retain their own all-GPU JSONL format; upstream terminal summary/replay commands are not added to the Qt interface and their single-snapshot format is not interchangeable.

Install after closing the application:

```sh
sudo apt install ./gputaskman-qt6_0.4.3-1_amd64.deb
```

Validation: 682 upstream tests completed (6 platform skips), 34 Qt/integration tests passed. Native OS package verification is recorded in VALIDATION.md. Physical multi-NVIDIA and Intel Xe hardware have not been independently tested.

MIT application and upstream copyright notices are preserved. LGPL libraries and matching corresponding sources retain their own licenses.
