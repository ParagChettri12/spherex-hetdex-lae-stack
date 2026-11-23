#!/usr/bin/env python3
"""Copy a finished run's results into results/<name>/ so they can be committed.

    python pipeline/publish_run.py --run-dir runs/20261122 --name dr1_20261122 --promote

Copies the executed notebook, summary.json, null_tests.json, coverage.csv,
run_info.json and the figures (never the .pkl caches). With --promote, the
executed notebook also replaces the top-level notebook, so GitHub shows the
figures and numbers without anyone running it. Warns if any copied file
still contains a cluster or home-directory path.
"""
import argparse
import glob
import os
import re
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["results.ipynb", "summary.json", "null_tests.json",
         "coverage.csv", "run_info.json"]
PRIVATE = re.compile(r"/scratch/|/storage/|/home/[a-z]|C:\\\\Users|/Users/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--name", required=True, help="e.g. dr1_20261122")
    ap.add_argument("--promote", action="store_true",
                    help="also replace the top-level notebook with the executed one")
    args = ap.parse_args()

    out = os.path.join(REPO, "results", args.name)
    os.makedirs(out, exist_ok=True)
    copied = []
    for f in FILES + [os.path.basename(p) for p in glob.glob(os.path.join(args.run_dir, "*.png"))]:
        src = os.path.join(args.run_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out, f))
            copied.append(f)
        else:
            print(f"  missing (skipped): {f}")
    print(f"Copied {len(copied)} files to {os.path.relpath(out, REPO)}/")

    if args.promote and "results.ipynb" in copied:
        dst = os.path.join(REPO, "SPHEREx-HETDEX-LAE-Stack.ipynb")
        shutil.copy2(os.path.join(out, "results.ipynb"), dst)
        print("Top-level notebook replaced with the executed run.")

    hits = []
    for f in copied + (["../../SPHEREx-HETDEX-LAE-Stack.ipynb"] if args.promote else []):
        p = os.path.normpath(os.path.join(out, f))
        if p.endswith(".png"):
            continue
        for n, line in enumerate(open(p, errors="ignore"), 1):
            if PRIVATE.search(line):
                hits.append(f"{os.path.relpath(p, REPO)}:{n}: {line.strip()[:100]}")
    if hits:
        print("\nWARNING: these lines contain local paths; edit them before pushing:")
        print("\n".join(hits[:20]))
    else:
        print("No local paths found.")


if __name__ == "__main__":
    main()
