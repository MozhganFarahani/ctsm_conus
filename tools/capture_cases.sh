#!/bin/bash
# capture_cases.sh: copy each CIME case folder, complete, into $REPO/cases/<case>/
# Usage: ./capture_cases.sh <repo_dir> [case ...]   (default: all six cases)
#   ./capture_cases.sh /glade/work/mozhgana/repo_staging
set -euo pipefail
SRC=/glade/work/mozhgana/ctsm_conus/cime/scripts
REPO=${1:?usage: capture_cases.sh <repo_dir> [case ...]}; shift
CASES=${*:-control irrigation_on evolving_landcover hillslope_on hillslope_eval prog_phenology}

for c in $CASES; do
  mkdir -p "$REPO/cases/$c"
  # -a keeps symlinks, timestamps and permissions; skip Jupyter autosaves and CIME's per-case .git
  rsync -a --exclude='.ipynb_checkpoints' --exclude='.git' "$SRC/$c/" "$REPO/cases/$c/"
  # save the case's own git history as text, since its .git is not copied
  git -C "$SRC/$c" log --stat > "$REPO/cases/$c/case_git_log.txt"
  echo "captured $c ($(du -sh "$REPO/cases/$c" | cut -f1))"
done