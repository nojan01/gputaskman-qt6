#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM=offscreen
python3 -m unittest discover -s gputaskman-qt6 -p 'test_*.py' -v
python3 gputaskman-qt6/gui.py --demo --demo-gpus 4 --self-test
python3 gputaskman-qt6/gui.py --demo --demo-gpus 8 --self-test
python3 gputaskman-qt6/gui.py --demo --demo-gpus 16 --self-test
