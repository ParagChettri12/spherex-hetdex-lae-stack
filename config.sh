# config.sh: the one file to edit for your cluster.
# Every SLURM script and run_pipeline.sh sources this.

# Conda environment (Roar Collab defaults; change for another cluster)
CONDA_BASE="/storage/icds/RISE/sw8/anaconda/anaconda3"
CONDA_ENV="astro"

# SLURM
SLURM_ACCOUNT="open"
SLURM_PARTITION="basic"
FETCH_TIME="02:00:00"      # wall time per fetch chunk
MERGE_TIME="00:30:00"
ANALYZE_TIME="08:00:00"    # notebook incl. 1000-sample bootstrap
FETCH_MEM="8G"
ANALYZE_MEM="16G"

# Fetch
CHUNK_SIZE=500             # galaxies per array task
MAX_CONCURRENT=10         # array tasks running at once (20 overloaded IRSA cutouts)
WORKERS_PER_TASK=4         # threads per task
EPOCHS_PER_BAND=1          # exposures used per detector band (1 = original analysis)

# Analysis
N_BOOTSTRAP=${N_BOOTSTRAP:-1000}

activate_env() {
    # "conda activate" fails in batch jobs on Roar Collab; this form works.
    source "${CONDA_BASE}/etc/profile.d/conda.sh"
    source activate "${CONDA_ENV}"
}
