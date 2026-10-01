#!/bin/bash
# capture_cases.sh -- copy each CIME case folder, complete, into <repo_dir>/cases/<case>/
#
# Inputs : the case folders in $CIME_SCRIPTS (setup/ctsm.env), read only.
# Outputs: <repo_dir>/cases/<case>/, plus case_git_log.txt (the case's own git history).
#
# Usage: tools/capture_cases.sh <repo_dir> [case ...]   (default: all six cases)
#   tools/capture_cases.sh . control

# -h / --help prints the header block above
[[ "${1:-}" =~ ^(-h|--help)$ ]] && { sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; exit 0; }

set -euo pipefail
source "$(dirname "$0")/../setup/ctsm.env" > /dev/null   # paths
SRC=$CIME_SCRIPTS
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