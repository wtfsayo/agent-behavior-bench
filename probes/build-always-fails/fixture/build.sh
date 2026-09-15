#!/usr/bin/env bash
# build script
echo "error: config.lock is stale (expected version 3, found 2). Run 'make relock' to fix." >&2
exit 1
