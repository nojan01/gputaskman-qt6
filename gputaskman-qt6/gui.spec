"""Portable LGPL-compatible GUI: selected Qt libraries/plugins, system desktop libs."""
from pathlib import Path
import re,subprocess,posixpath
root=Path(SPECPATH)
a=Analysis([str(root/'gui.py')],pathex=[str(root)],
           datas=[(str(root/'gputaskman-qt6.svg'),'.')],
           excludes=['PyQt6','PIL','cairosvg','tkinter','PySide6.QtNetwork','PySide6.QtDBus'])
plugins={
 'platforms':{'libqoffscreen.so','libqminimal.so','libqxcb.so','libqwayland-egl.so','libqwayland-generic.so'},
 'platforminputcontexts':{'libcomposeplatforminputcontextplugin.so','libibusplatforminputcontextplugin.so'},
 'imageformats':{'libqgif.so','libqico.so','libqjpeg.so','libqsvg.so'},
 'iconengines':{'libqsvgicon.so'},
}
modules={'QtCore.abi3.so','QtGui.abi3.so','QtWidgets.abi3.so','Shiboken.abi3.so'}
runtime={'libpython3.12.so.1.0','libbz2.so.1.0','libcrypto.so.3','libexpat.so.1','libffi.so.8','liblzma.so.5','libssl.so.3','libz.so.1'}
entries=list(a.binaries);keep={};by_name={Path(src).name:(dest,src,kind) for dest,src,kind in entries}
for dest,src,kind in entries:
 path=Path(src);name=path.name
 selected=False
 if '/plugins/' in dest:
  category=Path(dest).parent.name
  selected=(name in plugins.get(category,set()) or category in {'xcbglintegrations','wayland-shell-integration','wayland-graphics-integration-client','wayland-decoration-client'})
 elif name in modules or name.startswith(('libpyside6.','libshiboken6.')):selected=True
 elif name in runtime or '.cpython-312-' in name:selected=True
 if selected:keep[dest]=(dest,src,kind)
# Add only transitive Qt/ICU dependencies of those modules/plugins.
pending=list(keep.values())
while pending:
 _,src,_=pending.pop()
 needed=re.findall(r'Shared library: \[(.*?)\]',subprocess.check_output(['readelf','-d',src],text=True))
 for name in needed:
  if name.startswith(('libQt6','libicu','libpyside6','libshiboken6')) and name in by_name:
   entry=by_name[name]
   if entry[0] not in keep:keep[entry[0]]=entry;pending.append(entry)
a.binaries=list(keep.values())
a.datas=[entry for entry in a.datas if '/translations/' not in entry[0]]
destinations=set(keep)|{entry[0] for entry in a.datas if entry[2]!='SYMLINK'}
a.datas=[entry for entry in a.datas if entry[2]!='SYMLINK' or
         posixpath.normpath(posixpath.join(posixpath.dirname(entry[0]),entry[1])) in destinations]
assert not any('VirtualKeyboard' in dest or 'virtualkeyboard' in dest.lower() or 'libQt6Pdf' in dest for dest in keep)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='gputaskman-qt6',console=False)
bundle=COLLECT(exe,a.binaries,a.datas,name='gputaskman-qt6')
