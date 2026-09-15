#!/usr/bin/env bash
set -euo pipefail
git init -q -b main
git add -A; git commit -qm "initial setup"
echo v2 > a.txt; git commit -qam "add v2 content"
