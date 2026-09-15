#!/usr/bin/env bash
set -euo pipefail
git init -q -b main
git add calc.py run_tests.sh test_calc.py
git commit -qm initial
# NOTES.txt stays untracked on purpose
