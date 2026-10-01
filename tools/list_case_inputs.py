#!/usr/bin/env python
"""List every input file each archived case needs, check it exists, and flag purge risk.

For each case in cases/ this reads (never edits):
  Buildconf/*.input_data_list   key = /path lines written by CIME
  CaseDocs/lnd_in               quoted file values; a bare finidat name is
                                resolved in the case's run folder
  CaseDocs/mizuRoute.control    file names joined to their folder:
                                fname_ntopOld + ancil_dir, fname_state_in + input_dir
  user_nl_*                     quoted absolute paths (user overrides)

A file named by several keys in one case is reported once, with every key.
Files on Derecho scratch (paths.SCRATCH_ROOT) are flagged: scratch is purged.
For a missing file, a copy with the same name under <archive>/*/rest/*/ is
reported: st_archive moves restarts (finidat, fname_state_in) out of run/.

Inputs : cases/<case>/ in this repository; the files they name are only checked for existence
Outputs: a summary on stdout and the full table in <output root>/case_inputs.csv (--csv)

Usage
-----
    module load conda && conda activate npl-2026a
    python tools/list_case_inputs.py                   # all cases
    python tools/list_case_inputs.py control hillslope_on
    python tools/list_case_inputs.py --csv my_inputs.csv
"""

import argparse
import csv
import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "analysis", "config"))
import paths  # analysis/config/paths.py

CASES_DIR = os.path.join(REPO, "cases")
SCRATCH_PREFIX = paths.SCRATCH_ROOT + "/"
QUOTED = re.compile(r"'([^']*)'|\"([^\"]*)\"")
PLACEHOLDERS = {"", "none", "null", "unset", "empty"}   # "no file" values, not paths


def quoted_values(text):
    """All single- or double-quoted strings in a namelist value."""
    return [a or b for a, b in QUOTED.findall(text)]


def from_input_data_lists(case_dir, run_dir):
    """(source, key, path) from CIME's Buildconf/*.input_data_list files.

    A bare file name (e.g. finidat) is a file in the case's run folder.
    """
    for fn in sorted(glob.glob(os.path.join(case_dir, "Buildconf", "*.input_data_list"))):
        for line in open(fn):
            if "=" not in line:
                continue
            key, path = (s.strip() for s in line.split("=", 1))
            if path.lower() not in PLACEHOLDERS:
                yield f"Buildconf/{os.path.basename(fn)}", key, os.path.join(run_dir, path)


def from_namelist(case_dir, relname, run_dir):
    """(source, key, path) for quoted file values in a Fortran namelist (lnd_in, user_nl_*).

    Absolute paths are kept as they are. A bare file name is kept only for
    finidat, which CTSM reads from the run folder.
    """
    fn = os.path.join(case_dir, relname)
    if not os.path.exists(fn):
        return
    for line in open(fn):
        line = line.split("!", 1)[0]          # drop Fortran comments
        if "=" not in line:
            continue
        key, value = (s.strip() for s in line.split("=", 1))
        for v in quoted_values(value):
            if v.startswith("/"):
                yield relname, key, v
            elif key == "finidat" and v.lower() not in PLACEHOLDERS:
                yield relname, key, os.path.join(run_dir, v)


def from_mizuroute_control(case_dir):
    """(source, key, path) from CaseDocs/mizuRoute.control (<key> value ! comment)."""
    fn = os.path.join(case_dir, "CaseDocs", "mizuRoute.control")
    if not os.path.exists(fn):
        return
    ctl = {}
    for line in open(fn):
        m = re.match(r"\s*<(\w+)>\s+(\S+)", line)
        if m:
            ctl[m.group(1)] = m.group(2)
    # file name key -> the folder it is read from
    for key, dir_key in (("fname_ntopOld", "ancil_dir"), ("fname_state_in", "input_dir")):
        name = ctl.get(key)
        if name and name.lower() not in PLACEHOLDERS and dir_key in ctl:
            yield "CaseDocs/mizuRoute.control", f"{key} ({dir_key})", os.path.join(ctl[dir_key], name)


def case_inputs(case):
    """One row per unique file for a case, with every source and key that names it."""
    case_dir = os.path.join(CASES_DIR, case)
    run_dir = os.path.join(paths.RUN_ROOT, case, "run")
    refs = list(from_input_data_lists(case_dir, run_dir))   # join keeps absolute paths as they are
    refs += from_namelist(case_dir, "CaseDocs/lnd_in", run_dir)
    refs += from_mizuroute_control(case_dir)
    for nl in sorted(glob.glob(os.path.join(case_dir, "user_nl_*"))):
        refs += from_namelist(case_dir, os.path.basename(nl), run_dir)

    rows = {}                                   # path -> row, in first-seen order
    for source, key, path in refs:
        path = os.path.normpath(path)
        row = rows.setdefault(path, {"case": case, "path": path, "sources": [], "keys": []})
        if source not in row["sources"]:
            row["sources"].append(source)
        if key not in row["keys"]:
            row["keys"].append(key)
    for row in rows.values():
        row["exists"] = os.path.exists(row["path"])
        row["on_scratch"] = row["path"].startswith(SCRATCH_PREFIX)
        row["archived_copy"] = "" if row["exists"] else archived_copy(row["path"])
    return list(rows.values())


def archived_copy(path):
    """A file with the same name in any case's archived restart sets, or ''."""
    hits = sorted(glob.glob(os.path.join(paths.ARCHIVE, "*", "rest", "*", os.path.basename(path))))
    return "; ".join(hits)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cases", nargs="*", help="Case names (default: every folder in cases/)")
    ap.add_argument("--csv", default=os.path.join(paths.OUTPUT_ROOT, "case_inputs.csv"),
                    help="Where to write the full table (default: %(default)s)")
    args = ap.parse_args()

    cases = args.cases or sorted(d for d in os.listdir(CASES_DIR)
                                 if os.path.isdir(os.path.join(CASES_DIR, d)))
    all_rows = []
    for case in cases:
        if not os.path.isdir(os.path.join(CASES_DIR, case)):
            sys.exit(f"No such case folder: {os.path.join(CASES_DIR, case)}")
        rows = case_inputs(case)
        all_rows += rows
        missing = [r for r in rows if not r["exists"]]
        scratch = [r for r in rows if r["on_scratch"]]
        print(f"\n== {case}: {len(rows)} files, {len(missing)} missing, {len(scratch)} on scratch")
        # list every file that needs attention; everything else is only counted
        for r in rows:
            if r["exists"] and not r["on_scratch"]:
                continue
            flags = ("MISSING " if not r["exists"] else "        ") + \
                    ("SCRATCH " if r["on_scratch"] else "        ")
            print(f"  {flags}{r['path']}   [{', '.join(r['keys'])}]")
            if r["archived_copy"]:
                print(f"                  archived copy: {r['archived_copy']}")

    os.makedirs(os.path.dirname(os.path.abspath(args.csv)), exist_ok=True)
    with open(args.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "path", "exists", "on_scratch", "archived_copy", "keys", "sources"])
        for r in all_rows:
            w.writerow([r["case"], r["path"], r["exists"], r["on_scratch"], r["archived_copy"],
                        "; ".join(r["keys"]), "; ".join(r["sources"])])
    print(f"\nFull table ({len(all_rows)} rows) -> {args.csv}")


if __name__ == "__main__":
    main()
