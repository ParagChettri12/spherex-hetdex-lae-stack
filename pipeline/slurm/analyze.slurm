#!/bin/bash
# Execute the analysis notebook against this run's cache.
#SBATCH --nodes=1
#SBATCH --ntasks=1
set -eo pipefail
cd "$SLURM_SUBMIT_DIR"
source config.sh
activate_env
SPHEREX_CACHE="$RUN_DIR/sed_cache_full.pkl" \
SPHEREX_OUTDIR="$RUN_DIR" \
SPHEREX_N_BOOTSTRAP="${N_BOOTSTRAP:-1000}" \
jupyter nbconvert --to notebook --execute \
    --ExecutePreprocessor.timeout=-1 \
    --ExecutePreprocessor.kernel_name=python3 \
    --output-dir "$RUN_DIR" --output results.ipynb \
    SPHEREx-HETDEX-LAE-Stack.ipynb
echo "Done. Summary:"
cat "$RUN_DIR/summary.json"
