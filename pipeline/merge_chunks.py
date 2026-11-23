#!/usr/bin/env python3
"""Merge finished chunk files into runs/<tag>/sed_cache_full.pkl (the format
the notebook reads) and write coverage.csv, one row per target."""
import argparse
import csv
import glob
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import atomic_pickle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    seds, coverage = {}, {}
    files = sorted(glob.glob(os.path.join(args.run_dir, "chunks",
                                          "sed_chunk_[0-9][0-9][0-9][0-9].pkl")))
    for f in files:
        with open(f, "rb") as fh:
            d = pickle.load(fh)
        if "seds" in d and "coverage" in d:
            seds.update(d["seds"]); coverage.update(d["coverage"])
        else:                      # old format: plain {sid: sed}
            seds.update(d)
    out = os.path.join(args.run_dir, "sed_cache_full.pkl")
    atomic_pickle(seds, out)
    print(f"Merged {len(files)} chunk files -> {len(seds)} galaxies with data")
    print(f"Wrote {out}")

    if coverage:
        bands = sorted({b for c in coverage.values()
                        for b in c.get("n_exposures", {})})
        cov_f = os.path.join(args.run_dir, "coverage.csv")
        with open(cov_f, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["source_id", "status", "n_bands_used", "n_pixels"]
                       + [f"nexp_{b}" for b in bands] + ["failed_bands", "error"])
            for sid in sorted(coverage):
                c = coverage[sid]
                w.writerow([sid, c.get("status"), c.get("n_bands_used", 0),
                            c.get("n_pixels", 0)]
                           + [c.get("n_exposures", {}).get(b, 0) for b in bands]
                           + [";".join(c.get("failed_bands", [])),
                              c.get("error", "")])
        counts = {}
        for c in coverage.values():
            counts[c.get("status")] = counts.get(c.get("status"), 0) + 1
        print("Coverage:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print(f"Wrote {cov_f}")


if __name__ == "__main__":
    main()
