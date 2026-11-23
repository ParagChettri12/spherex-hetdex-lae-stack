#!/usr/bin/env python3
"""Sanity-check a merged cache: shapes, finiteness, wavelength range.

    python pipeline/validate_cache.py data/sed_cache_full.pkl"""
import pickle
import sys

import numpy as np


def main(path):
    with open(path, "rb") as fh:
        cache = pickle.load(fh)
    n, bad, npix, wmin, wmax = len(cache), 0, [], np.inf, -np.inf
    for sid, v in cache.items():
        try:
            w, r, c = (np.asarray(a, float) for a in v)
            assert len(w) == len(r) == len(c) >= 3
            assert np.all(np.isfinite(w)) and np.all(np.isfinite(r))
        except Exception:
            bad += 1
            continue
        npix.append(len(w)); wmin = min(wmin, w.min()); wmax = max(wmax, w.max())
    print(f"{path}: {n} galaxies, {bad} malformed")
    if npix:
        print(f"  pixels per galaxy: median {np.median(npix):.0f}, "
              f"range {min(npix)}-{max(npix)}")
        print(f"  rest-frame wavelength: {wmin:.3f}-{wmax:.3f} um")
    if n == 0 or bad > 0.01 * n:
        print("  FAILED"); sys.exit(1)
    print("  OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
