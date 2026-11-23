#!/usr/bin/env python3
"""Tabulate summary.json from every run (runs/ and results/), oldest first, to see how the
sample and the limits change between SPHEREx releases.

    python pipeline/compare_runs.py"""
import glob
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = []
for f in sorted(glob.glob(os.path.join(REPO, "runs", "*", "summary.json"))
                + glob.glob(os.path.join(REPO, "results", "*", "summary.json"))):
    with open(f) as fh:
        s = json.load(fh)
    rows.append((os.path.basename(os.path.dirname(f)), s))
if not rows:
    raise SystemExit("No runs/*/summary.json yet.")

lines = list(rows[0][1].get("lines", {}))
hdr = f"{'run':<18}{'N_cov':>8}{'N_6band':>9}{'ZODI':>7}"
for ln in lines:
    hdr += f"{ln + ' p':>14}{ln + ' UL':>14}"
print(hdr); print("-" * len(hdr))
for tag, s in rows:
    out = (f"{tag:<18}{s.get('n_with_coverage', 0):>8}"
           f"{s.get('n_six_band', 0):>9}{s.get('zodi_fraction', float('nan')):>7.3f}")
    for ln in lines:
        d = s.get("lines", {}).get(ln, {})
        p, ul = d.get("p_clean"), d.get("ul_3sigma")
        out += f"{p if p is not None else float('nan'):>14.3f}"
        out += f"{ul if ul is not None else float('nan'):>14.3f}"
    print(out)
