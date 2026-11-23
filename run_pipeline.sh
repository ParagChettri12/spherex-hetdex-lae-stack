#!/usr/bin/env bash
# run_pipeline.sh: query all of SPHEREx at every HETDEX LAE, merge, analyze.
#
#   ./run_pipeline.sh                    # new run tagged with today's date
#   ./run_pipeline.sh --tag 20261110     # resume or re-check an existing run
#   ./run_pipeline.sh --test 200         # small end-to-end test (200 LAEs)
#   ./run_pipeline.sh --no-analyze       # fetch and merge only
#
# Everything for a run lives in runs/<tag>/. Re-running with the same tag
# skips finished chunks, so it doubles as the recovery command.
set -eo pipefail
cd "$(dirname "$0")"
REPO="$(pwd)"
source config.sh

TAG="$(date +%Y%m%d)"; LIMIT=""; ANALYZE=1
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag) TAG="$2"; shift 2 ;;
        --test) LIMIT="$2"; shift 2 ;;
        --no-analyze) ANALYZE=0; shift ;;
        -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done
[[ -n "$LIMIT" && "$TAG" != *test* ]] && TAG="${TAG}_test${LIMIT}"

RUN_DIR="${REPO}/runs/${TAG}"
mkdir -p "${RUN_DIR}/chunks" "${RUN_DIR}/logs"
echo "Run directory: ${RUN_DIR}"

activate_env
python pipeline/prepare_targets.py --run-dir "$RUN_DIR" \
    --chunk-size "$CHUNK_SIZE" ${LIMIT:+--limit "$LIMIT"}
N_CHUNKS=$(cat "${RUN_DIR}/n_chunks")

# Only submit chunks that are not finished yet
TODO=$(python pipeline/check_run.py --run-dir "$RUN_DIR" --list-todo)
if [[ -z "$TODO" ]]; then
    echo "All ${N_CHUNKS} chunks already fetched."
    DEP=""
else
    MAXARR=$(scontrol show config 2>/dev/null | awk '/MaxArraySize/ {print $3}')
    if [[ -n "$MAXARR" && "$N_CHUNKS" -ge "$MAXARR" ]]; then
        echo "ERROR: ${N_CHUNKS} chunks exceeds MaxArraySize=${MAXARR}."
        echo "Raise CHUNK_SIZE in config.sh and start a new tag."
        exit 1
    fi
    echo "Submitting chunks ${TODO} (of 0-$((N_CHUNKS-1)))"
    FETCH_ID=$(sbatch --parsable \
        --job-name="sx-fetch-${TAG}" \
        --account="$SLURM_ACCOUNT" --partition="$SLURM_PARTITION" \
        --time="$FETCH_TIME" --mem="$FETCH_MEM" \
        --cpus-per-task="$WORKERS_PER_TASK" \
        --array="${TODO}%${MAX_CONCURRENT}" \
        --output="${RUN_DIR}/logs/fetch_%a.out" \
        --error="${RUN_DIR}/logs/fetch_%a.err" \
        --export=ALL,RUN_DIR="$RUN_DIR" \
        pipeline/slurm/fetch_array.slurm)
    echo "Fetch array: ${FETCH_ID}"
    DEP="--dependency=afterany:${FETCH_ID}"
fi

MERGE_ID=$(sbatch --parsable ${DEP} \
    --job-name="sx-merge-${TAG}" \
    --account="$SLURM_ACCOUNT" --partition="$SLURM_PARTITION" \
    --time="$MERGE_TIME" --mem="$ANALYZE_MEM" \
    --output="${RUN_DIR}/logs/merge.out" \
    --export=ALL,RUN_DIR="$RUN_DIR" \
    pipeline/slurm/merge.slurm)
echo "Merge job:   ${MERGE_ID}"

if [[ "$ANALYZE" == 1 ]]; then
    NB=${N_BOOTSTRAP}; [[ -n "$LIMIT" ]] && NB=50
    ANALYZE_ID=$(sbatch --parsable --dependency=afterok:${MERGE_ID} \
        --job-name="sx-analyze-${TAG}" \
        --account="$SLURM_ACCOUNT" --partition="$SLURM_PARTITION" \
        --time="$ANALYZE_TIME" --mem="$ANALYZE_MEM" \
        --output="${RUN_DIR}/logs/analyze.out" \
        --export=ALL,RUN_DIR="$RUN_DIR",N_BOOTSTRAP="$NB" \
        pipeline/slurm/analyze.slurm)
    echo "Analyze job: ${ANALYZE_ID}"
fi

echo
echo "Watch:   squeue -u \$USER"
echo "Status:  python pipeline/check_run.py --run-dir ${RUN_DIR}"
echo "Results: ${RUN_DIR}/results.ipynb and ${RUN_DIR}/summary.json"
