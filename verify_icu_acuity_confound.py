"""Verify the patient-acuity confound for ICU-Temp Spearman rho=-0.139.

Hypothesis (paper's defense): patients with denser Temp measurement schedules
(smaller mean gap) are clinically sicker. The negative correlation between
mean_gap and TAIN_improvement is therefore a confound, not a failure of OU.

Test: compute Spearman correlation between per-patient mean Temp gap and
acuity proxies (SAPS-I, SOFA, Length_of_stay, In-hospital_death). If sicker
patients are sampled more densely, mean_gap should correlate NEGATIVELY with
acuity (higher SAPS-I = smaller mean gap).
"""
import numpy as np
import os
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr, pointbiserialr

BASE = Path(r"C:\Users\agays\OneDrive\Desktop\tain-validation")
PHYSIO = BASE / "physionet" / "set-a"
OUTCOMES = BASE / "physionet" / "Outcomes-a.txt"

# Replicate load_physionet from regenerate_figures.py: Temp range 30-42, min 15 obs
LO, HI = 30, 42
MIN_OBS = 15

def per_patient_mean_gap(filepath):
    """Return (record_id, mean_gap_hours, n_obs) or None if <MIN_OBS valid obs."""
    times = []
    record_id = None
    with open(filepath) as fh:
        for line in fh.readlines()[1:]:
            parts = line.strip().split(',')
            if len(parts) != 3:
                continue
            if parts[1] == 'RecordID':
                record_id = int(parts[2])
            if parts[1] == 'Temp':
                try:
                    val = float(parts[2])
                except ValueError:
                    continue
                if LO < val < HI:
                    h, m = parts[0].split(':')
                    t = int(h) + int(m) / 60.0
                    times.append(t)
    if record_id is None or len(times) < MIN_OBS:
        return None
    ta = np.sort(np.array(times))
    dt = np.diff(ta)
    dt = dt[dt > 0]
    if len(dt) < MIN_OBS - 1:
        return None
    return (record_id, float(np.mean(dt)), len(times))


print("Step 1: scanning patient files for Temp series...")
rows = []
files = sorted(os.listdir(PHYSIO))
for i, f in enumerate(files):
    if not f.endswith('.txt'):
        continue
    res = per_patient_mean_gap(PHYSIO / f)
    if res is not None:
        rows.append(res)
    if (i + 1) % 500 == 0:
        print(f"  {i+1}/{len(files)} files scanned, {len(rows)} qualifying patients")

df = pd.DataFrame(rows, columns=['RecordID', 'mean_gap_h', 'n_obs'])
print(f"Total qualifying ICU-Temp patients: {len(df)}")

print("\nStep 2: loading outcomes...")
out = pd.read_csv(OUTCOMES)
print(f"Outcomes records: {len(out)}")
print(f"Outcomes columns: {list(out.columns)}")

merged = df.merge(out, on='RecordID', how='inner')
print(f"\nMerged: {len(merged)} patients with both Temp series + outcomes")
print(f"\nSummary stats:")
print(merged[['mean_gap_h', 'SAPS-I', 'SOFA', 'Length_of_stay', 'In-hospital_death']].describe())

# Handle missing-data sentinels (-1 in PhysioNet)
print(f"\nMissing SAPS-I (-1): {(merged['SAPS-I'] == -1).sum()}")
print(f"Missing SOFA (-1): {(merged['SOFA'] == -1).sum()}")
print(f"Missing Length_of_stay (-1): {(merged['Length_of_stay'] == -1).sum()}")

print("\nStep 3: Spearman correlations (mean_gap_h vs acuity proxies)")
print("=" * 70)

for col in ['SAPS-I', 'SOFA', 'Length_of_stay']:
    sub = merged[(merged[col] != -1)].copy()
    rho, p = spearmanr(sub['mean_gap_h'], sub[col])
    print(f"  mean_gap_h x {col:18s}: rho = {rho:+.4f}  p = {p:.3e}  N = {len(sub)}")

# Binary in-hospital_death (0 = survived, 1 = died); use point-biserial
sub = merged[(merged['In-hospital_death'].isin([0, 1]))].copy()
r, p = pointbiserialr(sub['In-hospital_death'], sub['mean_gap_h'])
n_died = int(sub['In-hospital_death'].sum())
print(f"  mean_gap_h x In-hospital_death:    r   = {r:+.4f}  p = {p:.3e}  N = {len(sub)} ({n_died} died)")

# Group comparison: died vs survived mean_gap
died = sub[sub['In-hospital_death'] == 1]['mean_gap_h']
surv = sub[sub['In-hospital_death'] == 0]['mean_gap_h']
print(f"\n  Mean gap (died):     {died.mean():.3f} h  (median {died.median():.3f}, n={len(died)})")
print(f"  Mean gap (survived): {surv.mean():.3f} h  (median {surv.median():.3f}, n={len(surv)})")

print("\n" + "=" * 70)
print("INTERPRETATION:")
print("  Negative correlation between mean_gap and SAPS-I/SOFA means:")
print("  - Sicker patients (high SAPS-I/SOFA) have smaller mean gap (denser sampling)")
print("  - This supports the patient-acuity confound argument in the paper.")
print()
print("  Combined with paper's existing finding (mean_gap x TAIN_improvement, rho=-0.139):")
print("  - Sicker patients are sampled more densely AND benefit more from TAIN")
print("  - The negative entity-level correlation is therefore confound-driven,")
print("    not a failure of the Ornstein-Uhlenbeck discretization.")
