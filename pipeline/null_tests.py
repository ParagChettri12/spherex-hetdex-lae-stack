#!/usr/bin/env python3
"""Null tests for the line measurements in the stacking notebook.

The bootstrap p-value asks "is the line SNR stable when galaxies are
resampled?". With tens of thousands of galaxies the stack barely moves under
resampling, so any fixed residual (a real line, continuum curvature, or a
zodiacal-model systematic) comes out at p = 0. These two tests ask the
question that matters instead: is the signal tied to the line wavelength in
each galaxy's rest frame?

  A. Off-line scan: measure the same "line" statistic at every wavelength
     along the real stack. A real line should stand out from the off-line
     values; curvature in the continuum shows up everywhere.
  B. Redshift shuffle: give every galaxy another galaxy's redshift and
     restack. That smears out anything at a fixed rest wavelength while
     keeping the observed-frame structure (zodiacal residuals, detector
     edges). A real line should be clearly above the shuffled values.

Usage (from the repo root, same environment variables as the notebook):
    SPHEREX_CACHE=runs/<tag>/sed_cache_full.pkl SPHEREX_OUTDIR=runs/<tag> \\
        python pipeline/null_tests.py --n-shuffle 20

Writes <OUTDIR>/null_tests.json.
"""
import argparse
import json
import os
import sys
import time

os.environ.setdefault("MPLBACKEND", "Agg")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(REPO, "SPHEREx-HETDEX-LAE-Stack.ipynb")

# Notebook cells needed to rebuild the six-band stack, found by content so
# the script keeps working if cells are added or reordered.
NEEDED = ["import numpy as np", "CACHE_FILE   =", "pickle.load(fh)",
          "def sigma_clip_mask", "idx_6band   = []", "wav_grid = np.linspace",
          "med_cln, sem_cln, n_cln, good_cln", "def extract_line"]


def load_notebook_namespace():
    nb = json.load(open(NOTEBOOK))
    ns = {}
    for marker in NEEDED:
        hits = [c for c in nb["cells"] if c["cell_type"] == "code"
                and marker in "".join(c["source"])]
        if len(hits) != 1:
            sys.exit(f"could not find a unique notebook cell containing {marker!r}")
        exec("".join(hits[0]["source"]), ns)
    return ns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-shuffle", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    os.chdir(REPO)
    t0 = time.time()
    ns = load_notebook_namespace()
    np = ns["np"]
    extract_line, make_stack = ns["extract_line"], ns["make_stack"]
    wav_grid, good_cln, med_cln = ns["wav_grid"], ns["good_cln"], ns["med_cln"]
    lines = ns["LINES_REACHABLE"]
    lo_ok = wav_grid[good_cln].min() + ns["CONT_OUTER"]
    hi_ok = wav_grid[good_cln].max() - ns["CONT_OUTER"]
    print(f"\nRebuilt the stack in {(time.time() - t0) / 60:.1f} min")

    def snr_at(stack, good, lam):
        return float(extract_line(stack, good, lam)[3])

    # ── A. Off-line scan along the real clean stack ───────────────────────
    scan = np.linspace(lo_ok, hi_ok, 400)
    scan_snr = np.array([snr_at(med_cln, good_cln, l) for l in scan])
    away = np.ones(len(scan), bool)
    for lam in lines.values():
        away &= np.abs(scan - lam) > 2 * ns["LINE_HALF"]
    off = scan_snr[away & np.isfinite(scan_snr)]

    print("\nA. Off-line scan (clean stack)")
    print(f"   {len(off)} off-line positions: SNR median {np.median(off):.2f}, "
          f"16-84% [{np.percentile(off, 16):.2f}, {np.percentile(off, 84):.2f}], "
          f"max {off.max():.2f}")
    res = {"offline_scan": {"n": int(len(off)),
                            "median": float(np.median(off)),
                            "p16": float(np.percentile(off, 16)),
                            "p84": float(np.percentile(off, 84))},
           "lines": {}}
    for name, lam in lines.items():
        s = snr_at(med_cln, good_cln, lam)
        frac = float(np.mean(off >= s))
        print(f"   {name:<10} SNR {s:5.2f}   fraction of off-line positions "
              f"at least as high: {frac:.3f}")
        res["lines"][name] = {"snr_clean": s, "offline_frac_ge": frac}

    # ── B. Redshift shuffle ──────────────────────────────────────────────
    rng = np.random.default_rng(args.seed)
    zs = np.asarray(ns["zs_6"], float)
    wav_6, cln_6, norms_6 = ns["wav_6"], ns["cln_6"], ns["norms_6"]
    shuffled = {name: [] for name in lines}
    print(f"\nB. Redshift shuffle ({args.n_shuffle} shuffles)")
    for k in range(args.n_shuffle):
        t1 = time.time()
        perm = rng.permutation(len(zs))
        w_shift = [w * (1 + zs[i]) / (1 + zs[j])
                   for i, (w, j) in enumerate(zip(wav_6, perm))]
        m, _, _, g = make_stack(w_shift, cln_6, norms_6)
        for name, lam in lines.items():
            shuffled[name].append(snr_at(m, g, lam))
        print(f"   shuffle {k + 1}/{args.n_shuffle} "
              f"({time.time() - t1:.0f} s)", flush=True)

    print()
    for name in lines:
        sh = np.array(shuffled[name])
        sh = sh[np.isfinite(sh)]
        real = res["lines"][name]["snr_clean"]
        mu, sd = float(np.mean(sh)), float(np.std(sh, ddof=1))
        z_score = (real - mu) / sd if sd > 0 else float("nan")
        frac = float(np.mean(sh >= real))
        print(f"   {name:<10} real {real:5.2f}   shuffled {mu:5.2f} ± {sd:.2f}   "
              f"(real - shuffled)/sd = {z_score:5.2f}   "
              f"fraction of shuffles >= real: {frac:.2f}")
        res["lines"][name].update(shuffle_mean=mu, shuffle_std=sd,
                                  shuffle_z=z_score, shuffle_frac_ge=frac,
                                  shuffle_snrs=sh.tolist())

    print("\nHow to read this: a real line needs BOTH a small off-line fraction "
          "(well under 0.05)\nAND a large margin over the shuffled stacks "
          "(several shuffle-sigma). The shuffle\nspread alone understates "
          "the noise, so a line that is only a few sigma above the\nshuffles "
          "but ordinary in the off-line scan is not a detection.")
    out = os.path.join(ns["OUTDIR"], "null_tests.json")
    with open(out, "w") as fh:
        json.dump(res, fh, indent=2)
    print(f"\nWrote {out}  (total {(time.time() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    main()
