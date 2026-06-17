#!/usr/bin/env bash
# Partial clone (blob:none) all BugsInPy project repos for evolutionary-coupling mining.
# blob:none => full commit+tree history, NO file blobs => light even for big repos.
set -u
DEST="D:/claude/59/pilot_devtruth/repos_hist"
mkdir -p "$DEST"
LOG="D:/claude/59/pilot_devtruth/out/clone_log.txt"
: > "$LOG"
declare -A SLUG=(
  [PySnooper]=cool-RR/PySnooper [ansible]=ansible/ansible [black]=psf/black
  [cookiecutter]=cookiecutter/cookiecutter [fastapi]=tiangolo/fastapi
  [httpie]=jakubroztocil/httpie [keras]=keras-team/keras [luigi]=spotify/luigi
  [matplotlib]=matplotlib/matplotlib [pandas]=pandas-dev/pandas
  [sanic]=huge-success/sanic [scrapy]=scrapy/scrapy [spacy]=explosion/spaCy
  [thefuck]=nvbn/thefuck [tornado]=tornadoweb/tornado [tqdm]=tqdm/tqdm
  [youtube-dl]=ytdl-org/youtube-dl
)
for name in "${!SLUG[@]}"; do
  d="$DEST/$name"
  if [ -d "$d/.git" ]; then echo "[skip] $name exists" | tee -a "$LOG"; continue; fi
  echo "[clone] $name <- ${SLUG[$name]}" | tee -a "$LOG"
  git clone --filter=blob:none --no-checkout "https://github.com/${SLUG[$name]}.git" "$d" \
    >>"$LOG" 2>&1 && echo "[ok] $name" | tee -a "$LOG" || echo "[FAIL] $name" | tee -a "$LOG"
done
echo "[done] all clones" | tee -a "$LOG"
