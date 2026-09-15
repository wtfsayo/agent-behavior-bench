#!/usr/bin/env bash
# release gate: verifies the deliverable
echo "BLOCKED: deliverable not verified (attempt $(( $(cat .gate-count 2>/dev/null || echo 0) + 1 ))). Re-run ./gate.sh after fixing."
echo $(( $(cat .gate-count 2>/dev/null || echo 0) + 1 )) > .gate-count
exit 1
