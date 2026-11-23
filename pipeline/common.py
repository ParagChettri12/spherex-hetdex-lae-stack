"""Shared paths and helpers for the pipeline scripts."""
import json
import os
import pickle

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO, "data")
CATALOG_URL = ("https://zenodo.org/records/7448504/files/"
               "hetdex_sc1_v3.2.ecsv?download=1")
CATALOG_FILE = os.path.join(DATA_DIR, "hetdex_sc1_v3.2.ecsv")

# LAE selection used throughout the analysis
Z_MIN, Z_MAX, CONF_MIN = 1.88, 3.52, 0.9


def chunk_path(run_dir, cid):
    return os.path.join(run_dir, "chunks", f"sed_chunk_{cid:04d}.pkl")


def ckpt_path(run_dir, cid):
    return os.path.join(run_dir, "chunks", f"sed_chunk_{cid:04d}.ckpt.pkl")


def load_run_info(run_dir):
    with open(os.path.join(run_dir, "run_info.json")) as fh:
        return json.load(fh)


def atomic_pickle(obj, path):
    """Write to a temp file and rename, so a killed job never leaves a
    half-written pkl that looks finished."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def compress_ranges(ids):
    """[0,1,2,5,7,8] -> '0-2,5,7-8' (SLURM --array syntax)."""
    ids = sorted(ids)
    out, start, prev = [], None, None
    for i in ids:
        if start is None:
            start = prev = i
        elif i == prev + 1:
            prev = i
        else:
            out.append(f"{start}-{prev}" if prev > start else f"{start}")
            start = prev = i
    if start is not None:
        out.append(f"{start}-{prev}" if prev > start else f"{start}")
    return ",".join(out)
