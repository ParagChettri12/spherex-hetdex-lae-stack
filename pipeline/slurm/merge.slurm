#!/bin/bash
# Merge chunk files, validate, and report anything missing.
#SBATCH --nodes=1
#SBATCH --ntasks=1
set -eo pipefail
cd "$SLURM_SUBMIT_DIR"
source config.sh
activate_env
python pipeline/merge_chunks.py --run-dir "$RUN_DIR"
python pipeline/validate_cache.py "$RUN_DIR/sed_cache_full.pkl"
# Non-zero exit here blocks the analysis job until missing chunks are rerun
python pipeline/check_run.py --run-dir "$RUN_DIR"
