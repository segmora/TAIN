# TAIN: Time-Aware Inertial Normalization

Code and paper source for:

> **Time-Aware Inertial Normalization for Irregularly-Sampled Tabular Streams**
> Tuhan Agay, Segmora AI, 2026
> [arXiv preprint (coming soon)]

## What is TAIN?

Standard normalization layers (BatchNorm) use a fixed EMA coefficient `alpha` regardless of the time gap between observations. TAIN replaces this with `alpha^(dt)`, where `dt` is the real elapsed time between consecutive observations.

```
# Standard EMA (time-blind)
mu_t = (1 - alpha) * x_batch + alpha * mu_{t-1}

# TAIN (time-aware)
mu_t = (1 - alpha^dt) * x_batch + alpha^dt * mu_{t-1}
```

This is the natural discretization of the Ornstein-Uhlenbeck process. A 30-day gap resets statistics toward current conditions; a 1-hour gap preserves accumulated inertia.

## Results

Validated on 5 real-world datasets (5,409 entities, 659,325 observations):

| Domain | Entities | RMSE Improvement | p-value | Win Rate |
|--------|----------|-----------------|---------|----------|
| Retail (Rossmann) | 50 | +1.05% | < 0.001 | 40/50 |
| Sensor (Beijing AQ) | 12 | +0.62% | 0.0002 | 12/12 |
| Finance (US Equities) | 5 | +17.32% | 0.031 | 5/5 |
| ICU-Temp (PhysioNet) | 1,787 | +3.04% | < 0.001 | 1,088/1,787 |
| ICU-Urine (PhysioNet) | 3,555 | +3.78% | < 0.001 | 2,539/3,555 |

Post-gap recovery scales monotonically with gap size (7.6% to 67.6% in Sensor domain), directly confirming the Ornstein-Uhlenbeck theoretical prediction.

## Repository Structure

```
tain-validation/
  tain_validation.py                  # Core TAIN vs EMA comparison (3 domains)
  tain_empirical_validation.ipynb     # Full 5-domain validation notebook (source of truth)
  paper-source/
    segmora_arxiv.tex                 # LaTeX source
    fig_*.png                         # Paper figures
    generate_docx.py                  # DOCX generation script
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

# Quick validation (3 domains: Retail, Sensor, Finance)
python tain_validation.py

# Full validation (5 domains, all tables and figures from the paper)
jupyter notebook tain_empirical_validation.ipynb
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
