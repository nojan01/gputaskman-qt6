#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a portable AppImage from the tested DEB payload."""
import argparse,os,shutil,subprocess,tempfile
from pathlib import Path
here=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--appimagetool',required=True);parser.add_argument('--runtime-file',required=True)
args=parser.parse_args()
version='0.4.4-1'
with tempfile.TemporaryDirectory(prefix='gputaskman-appdir-') as folder:
    root=Path(folder)/'GPU-Task-Manager.AppDir';root.mkdir()
    subprocess.run(['dpkg-deb','-x',str(here/'release'/f'gputaskman-qt6_{version}_amd64.deb'),str(root)],check=True)
    root.chmod(0o755)
    # AppImage does not install system policy files or launchers.
    shutil.rmtree(root/'usr/share/polkit-1');shutil.rmtree(root/'usr/bin')
    desktop=root/'gputaskman-qt6.desktop'
    shutil.copy2(root/'usr/share/applications/gputaskman-qt6.desktop',desktop)
    desktop.write_text(desktop.read_text().replace('Exec=gputaskman-qt6','Exec=AppRun'))
    shutil.copy2(here/'gputaskman-qt6.png',root/'gputaskman-qt6.png')
    (root/'.DirIcon').symlink_to('gputaskman-qt6.png')
    (root/'AppRun').write_text('''#!/bin/sh
set -eu
appdir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
helper=/opt/gputaskman-qt6/collector/gputaskman-collector
if [ -x "$helper" ]; then
    exec "$appdir/opt/gputaskman-qt6/gui/gputaskman-qt6" --worker "$helper" "$@"
fi
exec "$appdir/opt/gputaskman-qt6/gui/gputaskman-qt6" --worker "$appdir/opt/gputaskman-qt6/collector/gputaskman-collector" --standard-access "$@"
''')
    (root/'AppRun').chmod(0o755)
    (root/'usr/share/doc/gputaskman-qt6/APPIMAGE.md').write_text('''Portable mode uses the bundled collector with standard user permissions. For full GPU counter access install the matching DEB, which installs the trusted collector and Polkit policy. When that collector exists the AppImage uses it and authentication works as in the DEB. No system files are installed by the AppImage. Run --appimage-extract-and-run if FUSE is unavailable. Linux x86_64, glibc >= 2.38 and desktop X11/Wayland/OpenGL runtime libraries are required; hardware drivers come from the host.\n''')
    shutil.copytree(here/'third-party/appimage',root/'usr/share/doc/gputaskman-qt6/third-party/appimage',dirs_exist_ok=True)
    env={**os.environ,'ARCH':'x86_64','APPIMAGE_EXTRACT_AND_RUN':'1'}
    subprocess.run([str(Path(args.appimagetool).resolve()),'--no-appstream','--runtime-file',str(Path(args.runtime_file).resolve()),str(root),str(here/'release'/f'GPU-Task-Manager-{version}-x86_64.AppImage')],env=env,check=True)
