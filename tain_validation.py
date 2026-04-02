"""
TAIN Validation: Standard EMA vs Time-Aware Inertial Normalization (α^Δt)
Paper: "Time-Aware Inertial Normalization for Irregularly-Sampled Tabular Streams"
Author: Tuhan Agay, Segmora AI, 2026

Tests TAIN on 3 real-world domains:
  1. Retail   — Rossmann Store Sales (daily, closed-day gaps)
  2. Sensor   — Beijing Air Quality (hourly, sensor outage gaps)
  3. Finance  — US Stocks (daily, weekend + holiday gaps)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple, Dict, List
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import warnings
warnings.filterwarnings('ignore')

BASE = Path(__file__).resolve().parent


# ═══════════════════════════════════════════════════════════════════
# CORE: EMA vs TAIN implementations
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EMAState:
    mu: float = 0.0
    var: float = 1.0

def standard_ema_update(state: EMAState, x_batch: float, alpha: float) -> EMAState:
    """Standard EMA: fixed α regardless of time gap."""
    mu_new = (1 - alpha) * x_batch + alpha * state.mu
    var_new = (1 - alpha) * (x_batch - mu_new)**2 + alpha * state.var
    return EMAState(mu=mu_new, var=var_new)

def tain_update(state: EMAState, x_batch: float, alpha: float, dt: float) -> EMAState:
    """TAIN: α^Δt — time-aware inertial normalization."""
    alpha_dt = alpha ** dt  # The core TAIN modification
    mu_new = (1 - alpha_dt) * x_batch + alpha_dt * state.mu
    var_new = (1 - alpha_dt) * (x_batch - mu_new)**2 + alpha_dt * state.var
    return EMAState(mu=mu_new, var=var_new)


def run_comparison(values: np.ndarray, dt_values: np.ndarray, alpha: float = 0.95) -> Dict:
    """
    Run Standard EMA vs TAIN on a time series with irregular Δt.

    Returns dict with tracking errors, jitter, and per-gap-size analysis.
    """
    n = len(values)
    assert len(dt_values) == n

    # Initialize
    ema_state = EMAState(mu=values[0], var=0.0)
    tain_state = EMAState(mu=values[0], var=0.0)

    ema_mus = [values[0]]
    tain_mus = [values[0]]

    for i in range(1, n):
        x = values[i]
        dt = dt_values[i]

        ema_state = standard_ema_update(ema_state, x, alpha)
        tain_state = tain_update(tain_state, x, alpha, dt)

        ema_mus.append(ema_state.mu)
        tain_mus.append(tain_state.mu)

    ema_mus = np.array(ema_mus)
    tain_mus = np.array(tain_mus)

    # Metrics
    # 1. Tracking RMSE (how well running mean tracks actual signal)
    ema_rmse = np.sqrt(np.mean((values - ema_mus)**2))
    tain_rmse = np.sqrt(np.mean((values - tain_mus)**2))

    # 2. Action Jitter (magnitude of running mean changes)
    ema_jitter = np.sqrt(np.mean(np.diff(ema_mus)**2))
    tain_jitter = np.sqrt(np.mean(np.diff(tain_mus)**2))

    # 3. Post-gap recovery analysis
    gap_analysis = analyze_gaps(values, dt_values, ema_mus, tain_mus)

    return {
        'ema_rmse': ema_rmse,
        'tain_rmse': tain_rmse,
        'rmse_improvement': (ema_rmse - tain_rmse) / ema_rmse * 100,
        'ema_jitter': ema_jitter,
        'tain_jitter': tain_jitter,
        'ema_mus': ema_mus,
        'tain_mus': tain_mus,
        'gap_analysis': gap_analysis,
    }


def analyze_gaps(values, dt_values, ema_mus, tain_mus, gap_threshold=1.5):
    """Analyze post-gap recovery: how quickly each method adapts after a long gap."""
    gap_indices = np.where(dt_values > gap_threshold)[0]
    if len(gap_indices) == 0:
        return {'n_gaps': 0}

    recovery_window = 5  # observations after gap
    ema_post_errors = []
    tain_post_errors = []
    gap_sizes = []

    for idx in gap_indices:
        end = min(idx + recovery_window, len(values))
        if end <= idx:
            continue
        window = slice(idx, end)
        ema_post_errors.append(np.mean(np.abs(values[window] - ema_mus[window])))
        tain_post_errors.append(np.mean(np.abs(values[window] - tain_mus[window])))
        gap_sizes.append(dt_values[idx])

    ema_post = np.mean(ema_post_errors)
    tain_post = np.mean(tain_post_errors)

    return {
        'n_gaps': len(gap_indices),
        'mean_gap_size': np.mean(gap_sizes),
        'ema_post_gap_mae': ema_post,
        'tain_post_gap_mae': tain_post,
        'post_gap_improvement': (ema_post - tain_post) / ema_post * 100,
    }


# ═══════════════════════════════════════════════════════════════════
# DOMAIN 1: RETAIL — Rossmann Store Sales
# ═══════════════════════════════════════════════════════════════════

def load_retail() -> List[Tuple[np.ndarray, np.ndarray, str]]:
    """Load Rossmann data: filter to open days only, compute Δt from date gaps."""
    print("\n" + "="*70)
    print("DOMAIN 1: RETAIL — Rossmann Store Sales")
    print("="*70)

    df = pd.read_csv(BASE / "retail" / "train.csv", low_memory=False)
    df['Date'] = pd.to_datetime(df['Date'])

    # Take top 20 stores by total sales for statistical power
    top_stores = df.groupby('Store')['Sales'].sum().nlargest(20).index

    series_list = []
    for store_id in top_stores:
        store = df[(df['Store'] == store_id) & (df['Open'] == 1) & (df['Sales'] > 0)].copy()
        store = store.sort_values('Date')

        if len(store) < 100:
            continue

        values = store['Sales'].values.astype(float)
        dt_days = store['Date'].diff().dt.days.fillna(1).values.astype(float)
        dt_days = np.maximum(dt_days, 1.0)  # minimum 1 day

        series_list.append((values, dt_days, f"Store_{store_id}"))

    n_gaps = sum(np.sum(dt > 1) for _, dt, _ in series_list)
    print(f"  Loaded {len(series_list)} stores, total gaps (Δt>1): {n_gaps}")
    return series_list


# ═══════════════════════════════════════════════════════════════════
# DOMAIN 2: SENSOR — Beijing Air Quality
# ═══════════════════════════════════════════════════════════════════

def load_sensor() -> List[Tuple[np.ndarray, np.ndarray, str]]:
    """Load Beijing Air Quality: drop NA rows, compute Δt from hour gaps."""
    print("\n" + "="*70)
    print("DOMAIN 2: SENSOR — Beijing Air Quality (12 stations)")
    print("="*70)

    sensor_dir = BASE / "sensor"
    series_list = []

    for csv_file in sorted(sensor_dir.glob("PRSA_Data_*.csv")):
        station = csv_file.stem.replace("PRSA_Data_", "").split("_")[0]
        df = pd.read_csv(csv_file)

        # Create datetime and focus on PM2.5 (most gaps)
        df['datetime'] = pd.to_datetime(df[['year','month','day','hour']])
        df = df[['datetime', 'PM2.5']].dropna().sort_values('datetime')

        if len(df) < 100:
            continue

        values = df['PM2.5'].values.astype(float)
        dt_hours = df['datetime'].diff().dt.total_seconds().fillna(3600).values / 3600.0
        dt_hours = np.maximum(dt_hours, 1.0)  # minimum 1 hour

        series_list.append((values, dt_hours, f"Station_{station}"))

    n_gaps = sum(np.sum(dt > 1) for _, dt, _ in series_list)
    print(f"  Loaded {len(series_list)} stations, total gaps (Δt>1h): {n_gaps}")
    return series_list


# ═══════════════════════════════════════════════════════════════════
# DOMAIN 3: FINANCE — US Stocks
# ═══════════════════════════════════════════════════════════════════

def load_finance() -> List[Tuple[np.ndarray, np.ndarray, str]]:
    """Load stock data: trading days only, Δt in calendar days (weekends=3, holidays=4+)."""
    print("\n" + "="*70)
    print("DOMAIN 3: FINANCE — US Stocks (weekend + holiday gaps)")
    print("="*70)

    df = pd.read_csv(BASE / "finance" / "stocks_all.csv", index_col=0, parse_dates=True)

    series_list = []
    for col in df.columns:
        s = df[col].dropna()
        if len(s) < 100:
            continue

        values = s.values.astype(float)
        dt_days = s.index.to_series().diff().dt.days.fillna(1).values.astype(float)
        dt_days = np.maximum(dt_days, 1.0)

        series_list.append((values, dt_days, col))

    n_gaps = sum(np.sum(dt > 1) for _, dt, _ in series_list)
    print(f"  Loaded {len(series_list)} stocks, total gaps (Δt>1d): {n_gaps}")
    return series_list


# ═══════════════════════════════════════════════════════════════════
# MULTI-ALPHA SENSITIVITY ANALYSIS
# ═══════════════════════════════════════════════════════════════════

def alpha_sensitivity(values, dt_values, alphas=[0.85, 0.90, 0.95, 0.99]):
    """Test TAIN vs EMA across multiple α values."""
    results = {}
    for alpha in alphas:
        r = run_comparison(values, dt_values, alpha=alpha)
        results[alpha] = r
    return results


# ═══════════════════════════════════════════════════════════════════
# VISUALIZATION
# ═══════════════════════════════════════════════════════════════════

def plot_domain_results(domain_name: str, all_results: Dict, series_list, alpha=0.95):
    """Plot comprehensive results for one domain."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f"TAIN Validation — {domain_name}", fontsize=16, fontweight='bold')

    # --- Panel 1: Example time series with EMA vs TAIN tracking ---
    ax = axes[0, 0]
    # Pick the series with the most improvement
    best_key = max(all_results.keys(), key=lambda k: all_results[k]['rmse_improvement'])
    best = all_results[best_key]
    vals, dts, name = [(v, d, n) for v, d, n in series_list if n == best_key][0]

    # Show last 200 observations for clarity
    n_show = min(200, len(vals))
    t = np.arange(n_show)
    ax.plot(t, vals[-n_show:], 'k-', alpha=0.3, linewidth=0.8, label='Signal')
    ax.plot(t, best['ema_mus'][-n_show:], 'r-', linewidth=1.5, label=f"Std EMA (RMSE={best['ema_rmse']:.1f})")
    ax.plot(t, best['tain_mus'][-n_show:], 'b-', linewidth=1.5, label=f"TAIN α^Δt (RMSE={best['tain_rmse']:.1f})")
    # Mark gaps
    gap_mask = dts[-n_show:] > 1.5
    for i in np.where(gap_mask)[0]:
        ax.axvline(i, color='orange', alpha=0.3, linewidth=0.5)
    ax.set_title(f"Best case: {best_key} (RMSE ↓{best['rmse_improvement']:.1f}%)")
    ax.legend(fontsize=9)
    ax.set_xlabel("Observation index")

    # --- Panel 2: RMSE improvement distribution ---
    ax = axes[0, 1]
    improvements = [r['rmse_improvement'] for r in all_results.values()]
    colors = ['green' if x > 0 else 'red' for x in improvements]
    bars = ax.bar(range(len(improvements)), improvements, color=colors, alpha=0.7)
    ax.axhline(0, color='black', linewidth=0.5)
    ax.axhline(np.mean(improvements), color='blue', linewidth=2, linestyle='--',
               label=f"Mean: {np.mean(improvements):.2f}%")
    ax.set_title("RMSE Improvement: TAIN over Std EMA (%)")
    ax.set_xlabel("Entity index")
    ax.set_ylabel("Improvement (%)")
    ax.legend()

    # --- Panel 3: Post-gap recovery improvement ---
    ax = axes[1, 0]
    post_improvements = []
    gap_counts = []
    for r in all_results.values():
        ga = r['gap_analysis']
        if ga['n_gaps'] > 0 and 'post_gap_improvement' in ga:
            post_improvements.append(ga['post_gap_improvement'])
            gap_counts.append(ga['n_gaps'])

    if post_improvements:
        ax.scatter(gap_counts, post_improvements, alpha=0.7, c='blue', edgecolor='black')
        ax.axhline(0, color='black', linewidth=0.5)
        ax.axhline(np.mean(post_improvements), color='red', linewidth=2, linestyle='--',
                   label=f"Mean: {np.mean(post_improvements):.2f}%")
        ax.set_xlabel("Number of gaps per entity")
        ax.set_ylabel("Post-gap MAE improvement (%)")
        ax.set_title("Post-Gap Recovery: TAIN advantage")
        ax.legend()
    else:
        ax.text(0.5, 0.5, "No significant gaps", transform=ax.transAxes, ha='center')

    # --- Panel 4: α^Δt weight decay curve (theoretical) ---
    ax = axes[1, 1]
    dt_range = np.linspace(0, 15, 200)
    for a in [0.85, 0.90, 0.95, 0.99]:
        weights = a ** dt_range
        ax.plot(dt_range, weights, linewidth=2, label=f"α={a}")
    ax.set_xlabel("Δt (time gap)")
    ax.set_ylabel("α^Δt (inertia weight)")
    ax.set_title("TAIN Weight Decay: α^Δt vs Δt")
    ax.legend()
    ax.axhline(0.5, color='gray', linewidth=0.5, linestyle=':')
    ax.set_ylim(0, 1.05)

    plt.tight_layout()
    plt.savefig(BASE / f"tain_results_{domain_name.lower().replace(' ','_')}.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  → Saved: tain_results_{domain_name.lower().replace(' ','_')}.png")


def plot_summary(all_domain_results: Dict):
    """Cross-domain summary comparison."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("TAIN Validation: Cross-Domain Summary", fontsize=16, fontweight='bold')

    domains = list(all_domain_results.keys())

    for i, domain in enumerate(domains):
        ax = axes[i]
        results = all_domain_results[domain]
        improvements = [r['rmse_improvement'] for r in results.values()]

        ax.hist(improvements, bins=15, color='steelblue', edgecolor='black', alpha=0.7)
        ax.axvline(np.mean(improvements), color='red', linewidth=2, linestyle='--',
                   label=f"Mean: {np.mean(improvements):.2f}%")
        ax.axvline(np.median(improvements), color='green', linewidth=2, linestyle=':',
                   label=f"Median: {np.median(improvements):.2f}%")
        ax.axvline(0, color='black', linewidth=1)
        ax.set_title(f"{domain}\n(n={len(improvements)} entities)")
        ax.set_xlabel("RMSE Improvement (%)")
        ax.set_ylabel("Count")
        ax.legend(fontsize=9)

    plt.tight_layout()
    plt.savefig(BASE / "tain_summary_cross_domain.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n  → Saved: tain_summary_cross_domain.png")


# ═══════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════

def run_domain(domain_name: str, series_list, alpha=0.95):
    """Run full TAIN validation for one domain."""
    results = {}
    for values, dt_values, name in series_list:
        r = run_comparison(values, dt_values, alpha=alpha)
        results[name] = r

    # Summary stats
    improvements = [r['rmse_improvement'] for r in results.values()]
    post_gap_imps = []
    for r in results.values():
        ga = r['gap_analysis']
        if ga['n_gaps'] > 0 and 'post_gap_improvement' in ga:
            post_gap_imps.append(ga['post_gap_improvement'])

    print(f"\n  ── Results (α={alpha}) ──")
    print(f"  Entities tested:     {len(results)}")
    print(f"  RMSE improvement:    {np.mean(improvements):.2f}% ± {np.std(improvements):.2f}%")
    print(f"  RMSE median:         {np.median(improvements):.2f}%")
    print(f"  Positive (TAIN>EMA): {sum(1 for x in improvements if x > 0)}/{len(improvements)}")
    if post_gap_imps:
        print(f"  Post-gap MAE impr:   {np.mean(post_gap_imps):.2f}% ± {np.std(post_gap_imps):.2f}%")

    # Plot
    plot_domain_results(domain_name, results, series_list, alpha)

    return results


def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  TAIN VALIDATION — Real Data, 3 Domains                    ║")
    print("║  Time-Aware Inertial Normalization (Agay, 2026)            ║")
    print("║  Test: Standard EMA vs TAIN (α^Δt)                        ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    all_domain_results = {}

    # Domain 1: Retail
    retail_series = load_retail()
    retail_results = run_domain("Retail (Rossmann)", retail_series)
    all_domain_results["Retail"] = retail_results

    # Domain 2: Sensor
    sensor_series = load_sensor()
    sensor_results = run_domain("Sensor (Beijing AQ)", sensor_series)
    all_domain_results["Sensor"] = sensor_results

    # Domain 3: Finance
    finance_series = load_finance()
    finance_results = run_domain("Finance (US Stocks)", finance_series)
    all_domain_results["Finance"] = finance_results

    # Cross-domain summary
    plot_summary(all_domain_results)

    # Final table
    print("\n" + "="*70)
    print("FINAL CROSS-DOMAIN SUMMARY")
    print("="*70)
    print(f"{'Domain':<25} {'N':>5} {'RMSE Impr.':>12} {'Post-Gap Impr.':>15} {'Win Rate':>10}")
    print("-"*70)

    for domain, results in all_domain_results.items():
        n = len(results)
        imps = [r['rmse_improvement'] for r in results.values()]
        pgaps = [r['gap_analysis']['post_gap_improvement']
                 for r in results.values()
                 if r['gap_analysis']['n_gaps'] > 0 and 'post_gap_improvement' in r['gap_analysis']]
        wins = sum(1 for x in imps if x > 0)

        rmse_str = f"{np.mean(imps):.2f}%"
        pgap_str = f"{np.mean(pgaps):.2f}%" if pgaps else "N/A"
        win_str = f"{wins}/{n}"

        print(f"{domain:<25} {n:>5} {rmse_str:>12} {pgap_str:>15} {win_str:>10}")

    print("-"*70)
    all_imps = []
    for results in all_domain_results.values():
        all_imps.extend([r['rmse_improvement'] for r in results.values()])
    print(f"{'OVERALL':<25} {len(all_imps):>5} {np.mean(all_imps):.2f}%")

    # Paper comparison
    print(f"\n  Synthetic baseline: 11.4% RMSE improvement")
    print(f"  Real-data result:   {np.mean(all_imps):.2f}% RMSE improvement (3 domains)")


if __name__ == "__main__":
    main()
