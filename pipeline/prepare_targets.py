#!/usr/bin/env python3
"""Download the HETDEX catalog (once), select LAEs, and freeze the target
list for a run. The target list is written once per run and never
rewritten, so chunk N always means the same galaxies within a run."""
import argparse
import datetime
import json
import os
import sys
import urllib.request

import numpy as np
from astropy.table import Table, unique

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CATALOG_FILE, CATALOG_URL, CONF_MIN, DATA_DIR, Z_MAX, Z_MIN


def get_catalog():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CATALOG_FILE):
        print(f"Downloading HETDEX catalog to {CATALOG_FILE} ...", flush=True)
        part = CATALOG_FILE + ".part"
        urllib.request.urlretrieve(CATALOG_URL, part)
        os.replace(part, CATALOG_FILE)
    return Table.read(CATALOG_FILE, format="ascii.ecsv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--chunk-size", type=int, default=500)
    ap.add_argument("--limit", type=int, default=None,
                    help="Keep only the first N LAEs (test runs)")
    args = ap.parse_args()

    targets = os.path.join(args.run_dir, "targets.csv")
    info_f = os.path.join(args.run_dir, "run_info.json")
    os.makedirs(args.run_dir, exist_ok=True)

    if os.path.exists(targets) and os.path.exists(info_f):
        with open(info_f) as fh:
            info = json.load(fh)
        print(f"Using existing target list: {info['n_targets']} LAEs, "
              f"{info['n_chunks']} chunks (created {info['created']})")
        return

    cat = get_catalog()
    m = ((cat["source_type"] == "lae") &
         (cat["z_hetdex"] > Z_MIN) & (cat["z_hetdex"] < Z_MAX) &
         (cat["z_hetdex_conf"] > CONF_MIN))
    laes = cat[m]["source_id", "RA", "DEC", "z_hetdex"]
    n_rows = len(laes)
    # The catalog repeats some sources as identical rows; fetch each once
    laes = unique(laes, keys="source_id")
    laes.sort("source_id")
    if len(laes) < n_rows:
        print(f"Dropped {n_rows - len(laes)} duplicate source_id rows")
    if args.limit:
        rng = np.random.default_rng(0)
        keep = np.sort(rng.choice(len(laes), size=min(args.limit, len(laes)),
                                  replace=False))
        laes = laes[keep]

    laes.write(targets, format="ascii.csv", overwrite=True)
    n_chunks = int(np.ceil(len(laes) / args.chunk_size))
    info = {
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "n_targets": len(laes),
        "chunk_size": args.chunk_size,
        "n_chunks": n_chunks,
        "test_limit": args.limit,
        "selection": f"source_type=='lae', {Z_MIN}<z<{Z_MAX}, "
                     f"z_hetdex_conf>{CONF_MIN}",
        "catalog": os.path.basename(CATALOG_FILE),
    }
    with open(info_f, "w") as fh:
        json.dump(info, fh, indent=2)
    with open(os.path.join(args.run_dir, "n_chunks"), "w") as fh:
        fh.write(f"{n_chunks}\n")
    print(f"Selected {len(laes)} LAEs -> {n_chunks} chunks of {args.chunk_size}")


if __name__ == "__main__":
    main()
