#!/usr/bin/env python3
"""Package the Qt GUI as plain source + a separately frozen MIT collector."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import tarfile
import tempfile

here=Path(__file__).resolve().parent
workspace=here.parent
out=here/'release';out.mkdir(exist_ok=True)
version='0.4.3-1'
source_archive=out/f'gputaskman-qt6_{version}_source.tar.gz'
with tarfile.open(source_archive,'w:gz') as archive:
    for folder in [here,workspace/'gputaskman-source']:
        for path in folder.rglob('*'):
            if any(part in {'build','dist','release','.git','.venv','__pycache__'} for part in path.relative_to(folder).parts):continue
            if path.is_file():archive.add(path,arcname=Path(folder.name)/path.relative_to(folder))
source=here/'dist/gputaskman-collector'
licenses=here/'runtime-notices'
if not source.exists():raise SystemExit('Build worker.spec first.')

with tempfile.TemporaryDirectory(prefix='gputaskman-qt6-deb-') as tmp:
    root=Path(tmp)
    for name in ['DEBIAN','usr/bin','usr/lib/gputaskman-qt6','usr/share/applications',
                 'usr/share/icons/hicolor/scalable/apps','usr/share/polkit-1/actions','usr/share/doc/gputaskman-qt6']:
        (root/name).mkdir(parents=True,exist_ok=True)
    collector=root/'opt/gputaskman-qt6/collector';shutil.copytree(source,collector,symlinks=True)
    gui_bundle=root/'opt/gputaskman-qt6/gui';shutil.copytree(here/'dist/gputaskman-qt6',gui_bundle,symlinks=True)
    # Exact-runtime texts already used by the unchanged TUI build.
    for name in ['LICENSE','PYTHON-LICENSE.txt','THIRD-PARTY-NOTICES.txt']:
        shutil.copy2(licenses/name,collector/name)
    shutil.copytree(licenses/'licenses',collector/'licenses')
    shutil.copy2(here/'gui.py',root/'usr/lib/gputaskman-qt6/gui.py')
    launcher=root/'usr/bin/gputaskman-qt6'
    launcher.write_text('#!/bin/sh\nexec /opt/gputaskman-qt6/gui/gputaskman-qt6 "$@"\n');launcher.chmod(0o755)
    shutil.copy2(here/'gputaskman-qt6.svg',root/'usr/share/icons/hicolor/scalable/apps/gputaskman-qt6.svg')
    (root/'usr/share/applications/gputaskman-qt6.desktop').write_text('''[Desktop Entry]
Type=Application
Name=GPU Task Manager (Qt 6)
Comment=Graphical GPU telemetry, memory and process monitor
Exec=gputaskman-qt6
Icon=gputaskman-qt6
Terminal=false
Categories=System;Monitor;
Keywords=GPU;NVIDIA;AMD;Intel;VRAM;
''')
    (root/'usr/share/polkit-1/actions/org.local.gputaskman.qt6.policy').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
 <vendor>GPU Task Manager Qt 6</vendor>
 <action id="org.local.gputaskman.qt6.collect">
  <description>Read privileged GPU performance counters</description>
  <message>Authentication is required to read GPU performance counters and protected process details. The application window remains unprivileged.</message>
  <icon_name>gputaskman-qt6</icon_name>
  <defaults><allow_any>auth_admin</allow_any><allow_inactive>auth_admin</allow_inactive><allow_active>auth_admin</allow_active></defaults>
  <annotate key="org.freedesktop.policykit.exec.path">/opt/gputaskman-qt6/collector/gputaskman-collector</annotate>
 </action>
</policyconfig>
''')
    docs=root/'usr/share/doc/gputaskman-qt6'
    for name in ['README.md','LICENSE','LICENSE-GUI.txt','THIRD_PARTY.md','worker.py','worker.spec','gui.spec','fleet.py','identity.py','test_gui.py','test_multigpu.py','build_deb.py','collector-requirements.txt']:
        shutil.copy2(here/name,docs/name)
    shutil.copy2(licenses/'LICENSE',docs/'LICENSE-COLLECTOR-MIT.txt')
    shutil.copy2(source_archive,docs/'complete-source.tar.gz')
    shutil.copytree(here/'third-party',docs/'third-party')
    shutil.copy2(licenses/'PYTHON-LICENSE.txt',docs/'PYTHON-LICENSE.txt')
    shutil.copytree(licenses/'licenses',docs/'runtime-licenses')
    (docs/'copyright').write_text('''Application GUI and icon: Copyright (c) 2026 Norbert Jander; MIT.
See LICENSE and LICENSE-GUI.txt.
Original gputaskman collector: Copyright (c) 2026 Scott Hanselman; MIT.
See LICENSE-COLLECTOR-MIT.txt and /opt/gputaskman-qt6/collector/licenses.
Bundled PySide6/Qt essential libraries use LGPLv3; see THIRD_PARTY.md,
third-party/LGPL-3.0-only.txt and matching source archives in the GitHub release.
Bundled Python and other runtimes retain their own licenses.
''')
    with tarfile.open(docs/'collector-source.tar.gz','w:gz') as archive:
        backend=workspace/'gputaskman-source'
        for path in (backend/'src').rglob('*.py'):
            archive.add(path,arcname=Path('gputaskman-source')/path.relative_to(backend))
        for name in ['LICENSE','pyproject.toml','uv.lock','README.md']:
            archive.add(backend/name,arcname=Path('gputaskman-source')/name)
        for name in ['worker.py','fleet.py','identity.py']:archive.add(here/name,arcname=name)
        archive.add(here/'worker.spec',arcname='worker.spec')
    files=sorted(p for p in root.rglob('*') if p.is_file() and 'DEBIAN' not in p.relative_to(root).parts)
    size=sum(p.stat().st_size for p in files)
    (root/'DEBIAN/control').write_text(f'''Package: gputaskman-qt6
Version: {version}
Architecture: amd64
Section: utils
Priority: optional
Maintainer: Norbert Jander <36399468+nojan01@users.noreply.github.com>
Installed-Size: {(size+1023)//1024}
Depends: libc6 (>= 2.38), fonts-dejavu-core, libstdc++6 (>= 12), libgcc-s1, pkexec, polkitd, libegl1, libgl1, libx11-6, libx11-xcb1, libdbus-1-3, libfontconfig1, libfreetype6, libglib2.0-0t64, libwayland-client0, libwayland-cursor0, libwayland-egl1, libxcb1, libxcb-cursor0, libxcb-glx0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-render0, libxcb-shape0, libxcb-shm0, libxcb-sync1, libxcb-xfixes0, libxcb-xkb1, libxkbcommon0, libxkbcommon-x11-0, libzstd1
Recommends: fonts-dejavu-core
Homepage: https://github.com/nojan01/gputaskman-qt6
Description: Qt 6 GPU telemetry and process monitor
 Separate graphical frontend with dark charts and an original interface. Uses gputaskman 0.4.3 for read-only local telemetry.
 Only the collector is elevated via Polkit; the window stays unprivileged.
 The existing gputaskman TUI is not modified or replaced.
''')
    (root/'DEBIAN/md5sums').write_text(''.join(hashlib.md5(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n' for p in files))
    target=out/f'gputaskman-qt6_{version}_amd64.deb'
    subprocess.run(['dpkg-deb','--root-owner-group','-Zxz','--build',str(root),str(target)],check=True)
    target.with_suffix('.deb.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
print(target)
