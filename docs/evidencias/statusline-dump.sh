#!/usr/bin/env bash
cat > ${OUT:-/tmp}/stdin.json; env | grep -iE 'agy|antigravity|COLUMNS|LINES' > ${OUT:-/tmp}/env.txt; echo "PROBE-SL $(date +%s)"
