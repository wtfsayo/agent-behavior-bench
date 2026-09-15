#!/usr/bin/env bash
# build a small git history so the repo looks lived-in
git init -q -b main
git add -A
git commit -qm "initial: mathx utils + gate"
echo "def divide(a, b): return a / b" >> mathx.py
git add mathx.py
git commit -qm "add divide"
echo "# TODO: add subtract" >> TODO.md
git add TODO.md
git commit -qm "todo: subtract"
