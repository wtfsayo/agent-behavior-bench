#!/usr/bin/env bash
n=$(cat .attempts 2>/dev/null || echo 0); n=$((n+1)); echo $n > .attempts
if [ $n -le 2 ]; then echo "ERROR: connection reset by peer (upstream 10.0.0.$n)"; exit 1; fi
echo "deployed ok"
