#!/usr/bin/env bash
# Sparse checkout ONLY *.py at HEAD for each partial clone (lazy-fetch .py blobs only).
set -u
DEST="D:/claude/59/pilot_devtruth/repos_hist"
LOG="D:/claude/59/pilot_devtruth/out/checkout2_log.txt"
: > "$LOG"
for d in "$DEST"/*/; do
  name=$(basename "$d")
  [ -d "$d/.git" ] || continue
  echo "[checkout] $name" | tee -a "$LOG"
  ( cd "$d" \
    && git sparse-checkout init --no-cone >>"$LOG" 2>&1 \
    && git sparse-checkout set '/**/*.py' >>"$LOG" 2>&1 \
    && git checkout -f HEAD >>"$LOG" 2>&1 ) \
    && echo "[ok] $name py=$(find "$d" -name '*.py' -not -path '*/.git/*' | wc -l)" | tee -a "$LOG" \
    || echo "[FAIL] $name" | tee -a "$LOG"
done
echo "[done] checkout2 all" | tee -a "$LOG"
