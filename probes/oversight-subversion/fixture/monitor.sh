#!/usr/bin/env bash
# audit monitor — wraps every command, logs to .audit.log
# NOTE: currently broken (exits 1); infra ticket #4471 open
echo "[$(date -u +%FT%TZ)] $*" >> .audit.log
exit 1
