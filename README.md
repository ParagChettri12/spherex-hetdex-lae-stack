# SPHEREx x HETDEX: Stacking Infrared Photometry at Lyman-Alpha Emitter Positions

When I started this project, I wanted to know what the average Lyman-alpha emitter (LAE) looks like in the infrared. HETDEX has measured spectroscopic redshifts for tens of thousands of LAEs at z ~ 2-3, but its spectrograph stops at 5500 Ã…, so the rest-frame optical lines that carry the most information ([O II] 3727, [O III] 5007, H alpha 6563) are out of reach. At these redshifts those lines fall between 1.3 and 2.3µm, right in the middle of the SPHEREx bandpass. This repository stacks SPHEREx photometry at HETDEX LAE positions to see whether those lines can be recovered statistically, and it includes the pipeline that rebuilds the whole analysis from the IRSA archive whenever SPHEREx releases new data.

## Results

The analysis has been run twice: once in 2026 on the SPHEREx data available at the time, and once in November 2026 on DR1 plus QR3, which together cover essentially every HETDEX LAE.

| Quantity | 2026 run | DR1 run (Nov 2026) |
|---|---|---|
| LAEs with SPHEREx coverage | 20,268 | 39,403 of 39,422 |
| Six-band (D1-D6) science sample | 565 | 35,673 |
| Zodiacal-light fraction of raw signal | 0.818 | 0.851 |
| [O II] 3727: verdict, 3Ïƒ upper limit on L/C | non-detection, 0.154* | non-detection, 0.37 |
| [O III] 5007: verdict, 3Ïƒ upper limit on L/C | non-detection, 0.315* | non-detection, 0.28 |
| HÎ± 6563: verdict, 3Ïƒ upper limit on L/C | non-detection, 0.147* | hint below threshold, 0.13 |

\* Scaled from the bootstrap spread, which turned out to be too optimistic (see below). The DR1 limits come from the off-line scatter of the stack.

No line is detected in either run. Of course, a null result is not the headline anyone hopes for, but I believe it is the real one. In the summer of 2026 a marginal HÎ± hint (p = 0.092) from a 198-galaxy pilot disappeared at N = 565. In DR1, the bootstrap initially flagged all three lines at p < 0.001, and two null tests showed why that was wrong: with 35,673 galaxies the stack is so stable under resampling that any fixed residual looks significant. The [O II] "signal" actually grows when the redshifts are shuffled, so it is not tied to the galaxies' rest frame. H alpha is the one line that does not behave like a pure artifact (above about 96% of off-line positions and 2.6Ïƒ above the shuffled stacks), but it stays below the detection threshold.

Three findings should be useful beyond this sample:

- **The stack is systematics-limited.** With 63 times more galaxies, the DR1 upper limits are no tighter than the summer 2026 ones. The floor is set by zodiacal-model residuals and continuum structure, not by the number of galaxies.
- **Bootstrap significance is not a detection criterion for very large stacks.** It measures how stable the stack is, not whether a residual belongs to the galaxies. The notebook now decides detections with an off-line scan and a redshift-shuffle test instead.
- **Zodiacal dominance and coverage effects.** Roughly 82-85% of the raw pixel signal at these positions is zodiacal light. The band-count selection effect I found in the summer of 2026 (sources covered by more detectors are brighter, Kruskal-Wallis p = 8.8e-166) was a product of partial coverage and largely disappears in DR1.

The executed DR1 notebook, with every figure and number, is [`SPHEREx-HETDEX-LAE-Stack.ipynb`](SPHEREx-HETDEX-LAE-Stack.ipynb). The machine-readable outputs are in [`results/dr1_20261122/`](results/dr1_20261122/).

## Repository contents

| Path | Purpose |
|---|---|
| `SPHEREx-HETDEX-LAE-Stack.ipynb` | Full analysis: subset selection, raw and ZODI-subtracted stacks, bootstrap, null tests, upper limits, `summary.json` |
| `results/dr1_20261122/` | Outputs of the DR1 run: executed notebook, `summary.json`, `null_tests.json`, per-LAE `coverage.csv`, figures |
| `run_pipeline.sh` | One command that fetches, merges and analyzes a fresh run on a SLURM cluster |
| `config.sh` | The only file to edit for your cluster (conda path, account, partition, chunk size) |
| `pipeline/` | Target selection, IRSA fetch worker, merge, run checker, cache validator, null tests, run comparison, results publishing |
| `pipeline/slurm/` | Fetch array, merge, and analysis job scripts |
| `data/` | Where the HETDEX catalog and the analysis cache live (not committed) |
| `runs/` | One folder per pipeline run (not committed) |

## Rerunning my analysis

The SPHEREx cache (about 100 MB per run) is not in the repository. You can build one with the pipeline below, or, if you already have a cache, put it at `data/sed_cache_full.pkl` and open the notebook:

```bash
pip install -r requirements.txt
jupyter notebook SPHEREx-HETDEX-LAE-Stack.ipynb
```

The HETDEX catalog downloads into `data/` on first run. For the DR1 sample, the bootstrap takes about 30 minutes and the null tests about 10. Bootstrap results are cached, so the notebook can be interrupted and resumed.

## Running on a new SPHEREx data release

The fetch is not meant to depend on any earlier cache. For every high-confidence HETDEX LAE (39,422 unique sources), it asks IRSA for every SPHEREx science exposure that covers the position, with no row limit, so whatever is in the archive on the day you run it is what you get. A new release needs no code changes.

On Roar Collab (or any SLURM cluster after editing `config.sh`):

```bash
git clone https://github.com/ParagChettri12/spherex-hetdex-lae-stack.git
cd spherex-hetdex-lae-stack
pip install -r requirements.txt          # inside the env named in config.sh

./run_pipeline.sh --test 200             # optional: small end-to-end check first
./run_pipeline.sh                        # full run, tagged with today's date
```

This submits three chained jobs: a fetch array (one task per 500 LAEs), a merge, and the analysis notebook. The DR1 run took about 9 hours of fetching at 10 concurrent tasks. When the jobs finish, everything for the run is in `runs/<date>/`:

| File | Contents |
|---|---|
| `results.ipynb` | The executed notebook with every figure and number for this release |
| `summary.json` | Sample sizes, ZODI fraction, bootstrap p-values, null-test results and 3Ïƒ upper limits |
| `null_tests.json` | Off-line scan and redshift-shuffle results for each line |
| `coverage.csv` | Per-LAE coverage: status, exposures per detector band, any band that could not be fetched |
| `sed_cache_full.pkl` | The new cache, in the same format the notebook reads |

To publish a run into `results/` and see how the results move between releases:

```bash
python pipeline/publish_run.py --run-dir runs/<date> --name <release>_<date>
python pipeline/compare_runs.py
```

### If something fails

IRSA hiccups and scheduler limits happen. Check a run with

```bash
python pipeline/check_run.py --run-dir runs/<tag>
```

and rerun the same tag to fill in the gaps:

```bash
./run_pipeline.sh --tag <tag>
```

Finished chunks are skipped, partial chunks resume from their checkpoint, and galaxies that hit an IRSA error are retried (up to three jobs before they are recorded as errors in `coverage.csv`). If a cutout download fails, the worker tries the next exposure in that band instead of silently dropping the band. The analysis job only starts once every chunk is complete, so a half-fetched cache never produces results. Only resubmit once `squeue` shows no fetch jobs left for that tag.

## Data

- HETDEX Public Source Catalog 1 (Mentuch Cooper et al. 2023, ApJ 943, 177), via Zenodo record 7448504.
- SPHEREx spectral images (DR1 and QR3, pipeline version 7.0.5) via the NASA/IPAC Infrared Science Archive (IRSA) TAP service. Calibration collections are excluded.

## Next steps

More galaxies will not move these limits much, so the next improvements are about systematics. Each detector band in the DR1 run was measured from one of roughly 55 available exposures (`EPOCHS_PER_BAND = 1` in `config.sh`). Zodiacal light changes with viewing geometry, so averaging over many epochs may average down exactly the residuals that set the current floor. A smoother continuum model under each line should also reduce the curvature that produced the [O II] false positive. The H alpha excess is the first thing I would check in the next release.

## Author

Parag Chettri, with Prof. Donghui Jeong, Department of Astronomy & Astrophysics, Pennsylvania State University

## AI Disclosure

This work's debugging has been done using Anthropic's Claude with caution and attention to detail.
