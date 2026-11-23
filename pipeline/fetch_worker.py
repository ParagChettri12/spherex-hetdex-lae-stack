#!/usr/bin/env python3
"""Fetch SPHEREx spectral-image pixels at every LAE in one chunk.

For each galaxy, one TAP query returns every SPHEREx science exposure in the
archive that covers its position (no TOP limit; calibration collections such
as spherex_dr1_cal are excluded), so a new data release is picked up
automatically. The first EPOCHS_PER_BAND exposures of each detector band
are opened as small cutouts, and a 1x9 pixel strip along the dispersion
axis is read from the IMAGE (HDU 1) and ZODI (HDU 4) extensions.

Output: runs/<tag>/chunks/sed_chunk_NNNN.pkl containing
    {"seds": {source_id: (wav_rest_um, flux_raw, flux_clean)},
     "coverage": {source_id: {...status, exposures per band...}}}
"""
import argparse
import concurrent.futures
import logging
import os
import pickle
import socket
import sys
import threading
import time
from collections import defaultdict

import numpy as np
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.table import Table
from astropy.utils.data import conf
from astropy.wcs import WCS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import atomic_pickle, chunk_path, ckpt_path, load_run_info

logging.getLogger("astropy").setLevel(logging.ERROR)
conf.remote_timeout = 30
socket.setdefaulttimeout(30)

TAP_URL = "https://irsa.ipac.caltech.edu/TAP"
SIZE = 0.02            # cutout size, degrees
STRIP_LEN = 9          # pixels along the dispersion axis
MIN_PIXELS = 3
FALLBACKS = 4          # extra exposures tried per band if one fails
CHECKPOINT_EVERY = 50
RETRIES = 3

MAX_ATTEMPTS = 3       # job-level attempts before a galaxy is given up on
_local = threading.local()


def tap():
    # one TAP client per thread
    if not hasattr(_local, "svc"):
        import pyvo
        _local.svc = pyvo.dal.TAPService(TAP_URL)
    return _local.svc


def retry(fn, *a, transient=(Exception,), **kw):
    """Call fn, retrying with backoff (2 s, 4 s) on transient errors."""
    for attempt in range(RETRIES):
        try:
            return fn(*a, **kw)
        except transient:
            if attempt == RETRIES - 1:
                raise
            time.sleep(2 ** (attempt + 1))


def query_exposures(ra, dec):
    """All SPHEREx exposures covering (ra, dec), grouped by band and sorted
    by time. Returns {band: [uri, ...]}."""
    q = f"""
SELECT
    'https://irsa.ipac.caltech.edu/' || a.uri
        || '?center={ra},{dec}d&size={SIZE}' AS uri,
    p.energy_bandpassname AS band,
    p.time_bounds_lower AS t0
FROM spherex.artifact a
JOIN spherex.plane p ON a.planeid = p.planeid
JOIN spherex.observation o ON p.obsid = o.obsid
WHERE 1 = CONTAINS(POINT('ICRS', {ra}, {dec}), p.poly)
  AND o.collection NOT LIKE '%cal%'
"""
    tab = retry(lambda: tap().search(q, maxrec=100000).to_table())
    by_band = defaultdict(list)
    for r in tab:
        by_band[str(r["band"])].append((float(r["t0"]), str(r["uri"])))
    return {b: [uri for _, uri in sorted(v)] for b, v in sorted(by_band.items())}


def extract_strip(uri, ra_val, dec_val, z):
    """1x9 strip along y from one cutout. Logic unchanged from the
    validated 2026 analysis."""
    wavs, raws, cleans = [], [], []
    half = STRIP_LEN // 2
    with fits.open(uri, cache=False) as hdul:
        hdr = hdul[1].header
        swcs = WCS(hdr)
        coord = SkyCoord(ra=ra_val, dec=dec_val, unit="deg", frame="icrs")
        x, y = swcs.world_to_pixel(coord)
        xi = int(round(float(x)))
        yi = int(round(float(y)))
        h, w = hdul[1].data.shape

        spec_wcs = WCS(hdr, fobj=hdul, key="W")
        spec_wcs.sip = None

        for dy in range(-half, half + 1):
            yi_p, xi_p = yi + dy, xi
            if not (0 <= yi_p < h and 0 <= xi_p < w):
                continue
            flux_raw = float(hdul[1].data[yi_p, xi_p])
            flux_zodi = float(hdul[4].data[yi_p, xi_p])
            if not np.isfinite(flux_raw):
                continue
            flux_clean = (flux_raw - flux_zodi
                          if np.isfinite(flux_zodi) else flux_raw)
            wav_obs, _ = spec_wcs.pixel_to_world(xi_p, yi_p)
            wav_rest = wav_obs.to(u.micrometer).value / (1 + z)
            wavs.append(wav_rest)
            raws.append(flux_raw)
            cleans.append(flux_clean)
    return wavs, raws, cleans


def get_sed(row, epochs_per_band=1):
    """Returns (sed or None, coverage dict)."""
    ra, dec, z = float(row["RA"]), float(row["DEC"]), float(row["z_hetdex"])
    cov = {"status": "ok", "n_exposures": {}, "n_bands_used": 0,
           "n_pixels": 0, "error": ""}
    try:
        exposures = query_exposures(ra, dec)
    except Exception as e:
        cov.update(status="error", error=f"TAP: {e}"[:200])
        return None, cov
    cov["n_exposures"] = {b: len(v) for b, v in exposures.items()}
    if not exposures:
        cov["status"] = "no_coverage"
        return None, cov

    wavs, raws, cleans = [], [], []
    failed = []                       # bands with exposures but no usable cutout
    for band, uris in exposures.items():
        n_ok, n_net_err = 0, 0
        # Take the earliest exposures, but if one fails (timeout, or the
        # strip falls off the cutout) move on to the next one instead of
        # losing the band. Caps the work at FALLBACKS extra tries per band.
        for uri in uris[:epochs_per_band + FALLBACKS]:
            if n_ok >= epochs_per_band:
                break
            try:
                # only network errors (URLError, timeouts) are worth retrying here
                w, r, c = retry(extract_strip, uri, ra, dec, z,
                                transient=(OSError,))
            except Exception as e:
                n_net_err += 1
                cov["error"] = f"{band}: {e}"[:200]
                continue
            if len(w) == 0:
                continue
            wavs += w; raws += r; cleans += c
            n_ok += 1
        if n_ok:
            cov["n_bands_used"] += 1
        else:
            failed.append((band, n_net_err))

    cov["failed_bands"] = [b for b, _ in failed]
    if any(n_err for _, n_err in failed):
        # A band the archive covers was lost to network errors. Mark the
        # galaxy as errored so the chunk is retried (up to MAX_ATTEMPTS jobs)
        # rather than silently entering the stack with fewer bands.
        cov["status"] = "error"
        return None, cov

    cov["n_pixels"] = len(wavs)
    if len(wavs) < MIN_PIXELS:
        cov["status"] = "too_few_pixels"
        return None, cov
    return (np.array(wavs), np.array(raws), np.array(cleans)), cov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--chunk-id", type=int, required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--epochs-per-band", type=int, default=1)
    args = ap.parse_args()
    cid = args.chunk_id

    out_file = chunk_path(args.run_dir, cid)
    ckpt_file = ckpt_path(args.run_dir, cid)
    if os.path.exists(out_file):
        print(f"[chunk {cid}] already finished, nothing to do")
        return

    info = load_run_info(args.run_dir)
    targets = Table.read(os.path.join(args.run_dir, "targets.csv"),
                         format="ascii.csv")
    start = cid * info["chunk_size"]
    rows = targets[start:start + info["chunk_size"]]
    print(f"[chunk {cid}] rows {start}-{start + len(rows) - 1} "
          f"of {len(targets)}", flush=True)

    state = {"seds": {}, "coverage": {}, "errors": {}}
    if os.path.exists(ckpt_file):
        with open(ckpt_file, "rb") as fh:
            state = pickle.load(fh)
        state.setdefault("errors", {})
        print(f"[chunk {cid}] resuming: {len(state['coverage'])} done",
              flush=True)

    # Galaxies that errored on MAX_ATTEMPTS previous jobs are recorded as
    # errors and no longer block the chunk.
    errors = state.get("errors", {})
    for sid, cov in list(errors.items()):
        if cov.get("attempts", 1) >= MAX_ATTEMPTS:
            state["coverage"][sid] = cov
            del errors[sid]
    state["errors"] = errors

    todo = [r for r in rows if int(r["source_id"]) not in state["coverage"]]
    t0, n = time.time(), 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(get_sed, r, args.epochs_per_band): int(r["source_id"])
                for r in todo}
        for fut in concurrent.futures.as_completed(futs):
            sid = futs[fut]
            try:
                sed, cov = fut.result()
            except Exception as e:
                sed, cov = None, {"status": "error", "error": str(e)[:200]}
            # Errored galaxies are not marked done, so a rerun retries them
            if cov["status"] != "error":
                state["coverage"][sid] = cov
                if sed is not None:
                    state["seds"][sid] = sed
            elif sid not in state["coverage"]:
                # (a duplicate catalog row that already succeeded must not
                # be overwritten by a failed copy of itself)
                cov["attempts"] = state["errors"].get(sid, {}).get("attempts", 0) + 1
                state["errors"][sid] = cov
            n += 1
            if n % CHECKPOINT_EVERY == 0:
                atomic_pickle(state, ckpt_file)
                rate = n / max((time.time() - t0) / 60, 1e-9)
                print(f"[chunk {cid}] {n}/{len(todo)}  "
                      f"{len(state['seds'])} with data  {rate:.1f} gal/min",
                      flush=True)

    state["errors"] = {s: c for s, c in state["errors"].items()
                       if s not in state["coverage"]}
    n_err = len(state["errors"])
    if n_err:
        # Keep the checkpoint and exit non-zero so check_run flags this
        # chunk and a rerun retries only the errored galaxies.
        atomic_pickle(state, ckpt_file)
        print(f"[chunk {cid}] {n_err} galaxies errored; checkpoint kept. "
              f"Rerun the same tag to retry.", flush=True)
        sys.exit(2)

    state.pop("errors", None)
    atomic_pickle(state, out_file)
    if os.path.exists(ckpt_file):
        os.remove(ckpt_file)
    print(f"[chunk {cid}] done: {len(state['seds'])}/{len(rows)} with data "
          f"in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
