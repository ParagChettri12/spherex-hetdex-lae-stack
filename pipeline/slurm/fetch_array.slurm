#!/bin/bash
# One chunk of the SPHEREx fetch. Submitted by run_pipeline.sh, which sets
# account, partition, time, array range, and RUN_DIR on the command line.
#SBATCH --nodes=1
#SBATCH --ntasks=1
set -eo pipefail
cd "$SLURM_SUBMIT_DIR"
source config.sh
activate_env
echo "Chunk ${SLURM_ARRAY_TASK_ID} on $(hostname) at $(date)"
python pipeline/fetch_worker.py \
    --run-dir "$RUN_DIR" \
    --chunk-id "$SLURM_ARRAY_TASK_ID" \
    --workers "$WORKERS_PER_TASK" \
    --epochs-per-band "$EPOCHS_PER_BAND"
