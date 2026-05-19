# TAIN: Time-Aware Inertial Normalization

Code and paper source for:

> **Time-Aware Inertial Normalization for Irregularly-Sampled Tabular Streams**
> Tuhan Agay, Segmora AI, 2026
> [arXiv preprint (coming soon)]

## What is TAIN?

The running-statistics update inside normalization layers (BatchNorm-style EMA) applies a fixed coefficient `alpha` regardless of the time gap between observations. TAIN is a **time-aware update rule** for those running statistics: it replaces `alpha` with `alpha^(dt)`, where `dt` is the real elapsed time between consecutive observations.

```
# Standard EMA (time-blind)
mu_t = (1 - alpha) * x_batch + alpha * mu_{t-1}

# TAIN (time-aware)
mu_t = (1 - alpha^dt) * x_batch + alpha^dt * mu_{t-1}
```

This is the natural discretization of the Ornstein-Uhlenbeck process. A 30-day gap resets statistics toward current conditions; a 1-hour gap preserves accumulated inertia.

**Scope of this paper.** TAIN is validated as a running-statistics tracker across five real-world domain settings. Integration as a drop-in BatchNorm replacement in end-to-end tabular neural network training (TabNet, FT-Transformer, NODE) is future work.

## Results

Validated on five settings drawn from four real-world data sources (5,409 entities, 659,325 observations):

| Domain | Entities | RMSE Improvement | p-value | Win Rate |
|--------|----------|-----------------|---------|----------|
| Retail (Rossmann) | 50 | +1.05% | < 0.001 | 40/50 (80%) |
| Sensor (Beijing AQ, all 12 stations) | 12 | +0.62% | 0.0002 | 12/12 (100%) |
| Finance (US Equities, Mag-7 subset) | 5 | +17.32% | 0.031 | 5/5 (100%) |
| ICU-Temp (PhysioNet 2012) | 1,787 | +3.04% | < 0.001 | 1,088/1,787 (60.9%) |
| ICU-Urine (PhysioNet 2012) | 3,555 | +3.78% | < 0.001 | 2,539/3,555 (71.4%) |

ICU-Temp and ICU-Urine share the PhysioNet 2012 cohort and recording infrastructure; the two should not be regarded as fully independent corroborating domains.

Post-gap recovery increases with gap size in the largest stratum of four of five domains. The Sensor domain shows a clean monotonic relationship (7.6% to 67.6%) consistent with the Ornstein-Uhlenbeck discretization; the other domains exhibit within-domain non-monotonicities at intermediate strata. The negative ICU-Temp entity-level correlation (rho = -0.139) is verified to be a patient-acuity confound (mean gap correlates with SAPS-I at rho = -0.281 and SOFA at rho = -0.375; see `verify_icu_acuity_confound.py`).

## Repository Structure

```
tain-validation/
  tain_empirical_validation.ipynb       # Source of truth for all paper results (5 domains)
  tain_empirical_validation_executed.ipynb  # Executed copy with cached outputs
  tain_validation.py                    # Older 3-domain demo script (paper uses the notebook)
  regenerate_figures.py                 # Regenerates Table 4 and Table 5 figures
  verify_icu_acuity_confound.py         # Verifies ICU-Temp SAPS-I/SOFA correlations
  paper-source/
    segmora_arxiv.tex                   # LaTeX source
    segmora_arxiv.pdf                   # Compiled paper (20 pages)
    fig_*.png                           # Paper figures
  retail/ sensor/ finance/ physionet/   # Data folders (not tracked; see Data below)
  requirements.txt
```

## Data

Datasets are not included due to size. Download instructions:

1. **Retail**: [Rossmann Store Sales](https://www.kaggle.com/c/rossmann-store-sales) -> extract to `retail/`
2. **Sensor**: [Beijing Multi-Site Air Quality](https://archive.ics.uci.edu/dataset/501/) -> extract to `sensor/`
3. **Finance**: Run the notebook cell that downloads via `yfinance`, or place `stocks_all.csv` in `finance/`
4. **ICU-Temp**: [PhysioNet 2012 Challenge](https://physionet.org/content/challenge-2012/1.0.0/) -> extract `set-a/` and `Outcomes-a.txt` to `physionet/`
5. **ICU-Urine**: Same PhysioNet 2012 source as above (different variable, same `physionet/` folder)

## Usage

```bash
pip install -r requirements.txt

# Full validation (5 domains, all tables and figures from the paper)
jupyter notebook tain_empirical_validation.ipynb

# Reproduce the figures from cached results
python regenerate_figures.py

# Reproduce the ICU-Temp acuity-confound verification (SAPS-I, SOFA correlations)
python verify_icu_acuity_confound.py

# Optional: older 3-domain demo (Retail, Sensor, Finance only)
python tain_validation.py
```

## Citation

```bibtex
@article{agay2026tain,
  title={Time-Aware Inertial Normalization for Irregularly-Sampled Tabular Streams},
  author={Agay, Tuhan},
  journal={arXiv preprint},
  year={2026}
}
```

## License

MIT License. See [LICENSE](LICENSE) for details.
