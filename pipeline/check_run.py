#!/usr/bin/env python3
"""Report which chunks of a run are finished.

    python pipeline/check_run.py --run-dir runs/20261110
    python pipeline/check_run.py --run-dir runs/20261110 --list-todo

Exits 1 if any chunk is unfinished, so the analysis job does not start on
an incomplete cache."""
import argparse
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import chunk_path, ckpt_path, compress_ranges, load_run_info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--list-todo", action="store_true",
                    help="Print unfinished chunk ids in SLURM --array syntax")
    args = ap.parse_args()

    info = load_run_info(args.run_dir)
    n = info["n_chunks"]
    todo = [i for i in range(n) if not os.path.exists(chunk_path(args.run_dir, i))]
    if args.list_todo:
        print(compress_ranges(todo))
        return

    tag = os.path.basename(os.path.normpath(args.run_dir))
    print(f"Run {tag}: {n - len(todo)}/{n} chunks finished "
          f"({info['n_targets']} targets)")
    if todo:
        partial = [i for i in todo if os.path.exists(ckpt_path(args.run_dir, i))]
        n_err = 0
        for i in partial:
            try:
                with open(ckpt_path(args.run_dir, i), "rb") as fh:
                    n_err += len(pickle.load(fh).get("errors", {}))
            except Exception:
                pass
        print(f"  unfinished: {compress_ranges(todo)}")
        if partial:
            print(f"  with checkpoints: {compress_ranges(partial)} "
                  f"({n_err} galaxies waiting on retry)")
        print(f"  fix: ./run_pipeline.sh --tag {tag}")
        sys.exit(1)
    print("  complete")


if __name__ == "__main__":
    main()
