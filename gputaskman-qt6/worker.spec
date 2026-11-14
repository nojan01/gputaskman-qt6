from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata
root = Path(SPECPATH)
a = Analysis([str(root / 'worker.py')], pathex=[str(root.parent / 'gputaskman-source/src')],
             datas=copy_metadata('gputaskman', recursive=True),
             excludes=['PyQt6', 'PySide6', 'PIL', 'cairosvg'])
forbidden = ('libnvidia-ml.so', 'libcuda.so', 'libamd_smi.so')
a.binaries = [entry for entry in a.binaries if not any(Path(entry[0]).name.startswith(n) for n in forbidden)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='gputaskman-collector', console=True)
bundle = COLLECT(exe, a.binaries, a.datas, name='gputaskman-collector')
