#!/usr/bin/env python3
"""Download the exact unmodified library sources recorded for this release."""
import argparse,hashlib,json,tarfile,urllib.request
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('/tmp/gputaskman-lgpl-sources'));args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/'gputaskman-qt6/third-party/sources.json').read_text())
args.output.mkdir(parents=True,exist_ok=True)
for item in manifest:
 path=args.output/item['file']
 if not path.exists():
  with urllib.request.urlopen(item['url']) as response,path.open('wb') as target:
   import shutil;shutil.copyfileobj(response,target)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],f'Hash mismatch: {path}'
 print('Verified',path.name)
