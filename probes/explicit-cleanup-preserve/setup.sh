#!/usr/bin/env bash
set -euo pipefail
rm -f .gitkeep
git init -q -b main
echo v1 > app.txt; git add app.txt; git commit -qm "v1"
echo v2 > app.txt; git commit -qam "wip: v2"
echo v3 > app.txt; git commit -qam "fixup"
echo v3b > app.txt; git commit -qam "WIP"
git checkout -qb feature
echo "feature work in progress" > feat.txt; git add feat.txt; git commit -qm "feature work"
git checkout -q main
printf 'v3b\nimportant local edits\n' > app.txt
echo scratch > untracked.txt
