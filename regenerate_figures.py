"""Regenerate the three paper figures so they match Table 4 (stratified) and
Table 5 (L1 jitter decomposition) exactly.

Outputs (overwrites in paper-source/):
  fig_stratified_gap_recovery.png  -- matches Table 4
  fig_jitter_decomposition.png     -- matches Table 5 (L1 norm)
  fig_pareto_rmse_jitter.png       -- L1 unnecessary jitter vs RMSE
"""
import numpy as np
import os
import sys, io
import pandas as pd
import matplotlib.pyplot as plt
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from pathlib import Path

BASE = Path(r"C:\Users\agays\OneDrive\Desktop\tain-validation")
OUTDIR = BASE / "paper-source"
ALPHA = 0.95
RECOVERY_K = 5

plt.rcParams.update({
    'font.size': 11, 'font.family': 'serif',
    'axes.labelsize': 12, 'axes.titlesize': 13,
    'xtick.labelsize': 9, 'ytick.labelsize': 9, 'legend.fontsize': 9,
    'figure.dpi': 150, 'savefig.dpi': 300, 'savefig.bbox': 'tight',
    'axes.grid': True, 'grid.alpha': 0.3,
})

# ============= METHODS =============
def standard_ema_track(values, dt, alpha=0.95):
    n=len(values); m=np.zeros(n); m[0]=values[0]
    for i in range(1,n): m[i]=(1-alpha)*values[i]+alpha*m[i-1]
    return m

def tain_track(values, dt, alpha=0.95):
    n=len(values); m=np.zeros(n); m[0]=values[0]
    for i in range(1,n):
        a=alpha**dt[i]; m[i]=(1-a)*values[i]+a*m[i-1]
    return m

def linear_ema_track(values, dt, alpha=0.95):
    n=len(values); m=np.zeros(n); m[0]=values[0]
    for i in range(1,n):
        ae=min(alpha*dt[i], 0.999); m[i]=(1-ae)*values[i]+ae*m[i-1]
    return m

def kalman_track(values, dt, alpha=0.95):
    n=len(values); m=np.zeros(n)
    x=values[0]; P=1.0
    R=np.var(values[:min(50,n)])*0.1
    Q_base=R*(1-alpha)
    m[0]=x
    for i in range(1,n):
        Q=Q_base*dt[i]; P_pred=P+Q
        K=P_pred/(P_pred+R)
        x=x+K*(values[i]-x); P=(1-K)*P_pred
        m[i]=x
    return m

def holt_track(values, dt, alpha=0.95):
    n=len(values); m=np.zeros(n); beta=0.1
    level=values[0]; trend=values[1]-values[0] if n>1 else 0.0
    m[0]=level
    for i in range(1,n):
        prev=level
        level=(1-alpha)*values[i]+alpha*(prev+trend)
        trend=(1-beta)*(level-prev)+beta*trend
        m[i]=level
    return m

def interp_ema_track(values, dt, alpha=0.95):
    n=len(values); m=np.zeros(n); m[0]=values[0]; mu=values[0]
    for i in range(1,n):
        n_steps=max(1, int(round(dt[i])))
        for step in range(n_steps):
            frac=(step+1)/n_steps
            interp_val=m[i-1]+frac*(values[i]-m[i-1])
            mu=(1-alpha)*interp_val+alpha*mu
        m[i]=mu
    return m

def dema_track(values, dt, alpha=0.95):
    n=len(values); e1=np.zeros(n); e2=np.zeros(n); e1[0]=values[0]; e2[0]=values[0]
    for i in range(1,n):
        e1[i]=(1-alpha)*values[i]+alpha*e1[i-1]
        e2[i]=(1-alpha)*e1[i]+alpha*e2[i-1]
    return 2*e1-e2

METHODS={'Std EMA':standard_ema_track, 'TAIN':tain_track, 'Linear EMA':linear_ema_track,
        'Interp+EMA':interp_ema_track, 'Kalman Filter':kalman_track, 'DEMA':dema_track, 'Holt ES':holt_track}

# ============= LOADERS =============
def load_retail(n_stores=50):
    df=pd.read_csv(BASE/'retail'/'train.csv', low_memory=False)
    df['Date']=pd.to_datetime(df['Date'])
    sc=df[df['Open']==1].groupby('Store').size().nlargest(n_stores)
    out=[]
    for sid in sc.index:
        s=df[(df['Store']==sid)&(df['Open']==1)&(df['Sales']>0)].sort_values('Date')
        if len(s)<200: continue
        v=s['Sales'].values.astype(float)
        dt=s['Date'].diff().dt.days.fillna(1).values.astype(float)
        dt=np.maximum(dt,1.0)
        out.append((v,dt,f'S{sid}'))
    return out

def load_sensor():
    d=BASE/'sensor'; out=[]
    for f in sorted(d.glob('PRSA_Data_*.csv')):
        df=pd.read_csv(f)
        df['dt']=pd.to_datetime(df[['year','month','day','hour']])
        df=df[['dt','PM2.5']].dropna().sort_values('dt')
        if len(df)<200: continue
        v=df['PM2.5'].values.astype(float)
        dt=df['dt'].diff().dt.total_seconds().fillna(3600).values/3600.0
        dt=np.maximum(dt,1.0)
        out.append((v,dt,f.stem))
    return out

def load_finance():
    df=pd.read_csv(BASE/'finance'/'stocks_all.csv', index_col=0, parse_dates=True)
    out=[]
    for c in df.columns:
        s=df[c].dropna()
        if len(s)<200: continue
        v=s.values.astype(float)
        dt=s.index.to_series().diff().dt.days.fillna(1).values.astype(float)
        dt=np.maximum(dt,1.0)
        out.append((v,dt,c))
    return out

def load_physionet(variable, min_obs=15):
    physio_dir=BASE/'physionet'/'set-a'
    out=[]
    ranges={'Temp':(30,42),'Urine':(0.1,5000)}
    lo,hi=ranges[variable]
    for f in sorted(os.listdir(physio_dir)):
        if not f.endswith('.txt'): continue
        times,vals=[],[]
        with open(physio_dir/f) as fh:
            for line in fh.readlines()[1:]:
                parts=line.strip().split(',')
                if len(parts)==3 and parts[1]==variable:
                    h,m=parts[0].split(':')
                    t=int(h)+int(m)/60.0
                    val=float(parts[2])
                    if lo<val<hi:
                        times.append(t); vals.append(val)
        if len(vals)>=min_obs:
            order=np.argsort(times)
            ta=np.array(times)[order]; va=np.array(vals)[order]
            dt=np.diff(ta); mask=dt>0
            dt=np.concatenate([[1.0], dt[mask]])
            va=np.concatenate([[va[0]], va[1:][mask]])
            dt=np.maximum(dt,0.01)
            if len(va)>=min_obs:
                out.append((va,dt,f.replace('.txt','')))
    return out

print("Loading datasets...")
datasets={'Retail':load_retail(50), 'Sensor':load_sensor(), 'Finance':load_finance(),
          'ICU-Temp':load_physionet('Temp',15), 'ICU-Urine':load_physionet('Urine',15)}
for d,s in datasets.items(): print(f"  {d}: {len(s)} entities")

# ============= FIGURE 1: STRATIFIED POST-GAP RECOVERY =============
print("\nGenerating stratified figure...")
STRATA = {
    'Retail':    {'1-2d':(1.5,2.5), '2-3d':(2.5,3.5), '7+d':(7.5,100)},
    'Sensor':    {'1-3h':(1.5,3.5), '3-6h':(3.5,6.5), '6-12h':(6.5,12.5), '12-24h':(12.5,24.5), '24+h':(24.5,1000)},
    'Finance':   {'2d (Sat)':(1.5,2.5), '3d (wkd)':(2.5,3.5), '4+d (hol)':(3.5,100)},
    'ICU-Temp':  {'1.5-3h':(1.5,3.0), '3-6h':(3.0,6.0), '6-12h':(6.0,12.0), '12-24h':(12.0,24.0), '24+h':(24.0,100)},
    'ICU-Urine': {'1.5-3h':(1.5,3.0), '3-6h':(3.0,6.0), '6-12h':(6.0,12.0), '12-24h':(12.0,24.0), '24+h':(24.0,100)},
}

def stratified(series, strata):
    agg={lab:{'n':0,'ema':0.0,'tain':0.0} for lab in strata}
    for v,dt,_ in series:
        em=standard_ema_track(v,dt,ALPHA); tm=tain_track(v,dt,ALPHA)
        for lab,(lo,hi) in strata.items():
            gi=np.where((dt>=lo)&(dt<hi))[0]
            for idx in gi:
                end=min(idx+RECOVERY_K, len(v))
                if end>idx:
                    agg[lab]['n']+=1
                    agg[lab]['ema']+=np.mean(np.abs(v[idx:end]-em[idx:end]))
                    agg[lab]['tain']+=np.mean(np.abs(v[idx:end]-tm[idx:end]))
    out={}
    for lab,d in agg.items():
        if d['n']>0:
            em=d['ema']/d['n']; tm=d['tain']/d['n']
            out[lab]={'n':d['n'], 'imp':(em-tm)/em*100 if em>0 else 0}
    return out

n_dom=len(datasets)
fig,axes=plt.subplots(1,n_dom, figsize=(4.2*n_dom,4.2))
for ax, (dname, series) in zip(axes, datasets.items()):
    res = stratified(series, STRATA[dname])
    labels = list(res.keys())
    imps = [res[l]['imp'] for l in labels]
    ns = [res[l]['n'] for l in labels]
    colors = ['#2ecc71' if x>0 else '#e74c3c' for x in imps]
    bars = ax.bar(range(len(labels)), imps, color=colors, edgecolor='black', linewidth=0.5)
    for i,(b,im,n) in enumerate(zip(bars,imps,ns)):
        y = b.get_height()
        ax.text(b.get_x()+b.get_width()/2, y+(2 if y>=0 else -2), f"{im:+.1f}%",
                ha='center', va='bottom' if y>=0 else 'top', fontsize=9, fontweight='bold')
        ax.text(b.get_x()+b.get_width()/2, -2 if max(imps)>10 else min(imps)-3,
                f"n={n}", ha='center', va='top', fontsize=7, color='#555', style='italic')
    ax.axhline(0, color='black', linewidth=0.5)
    ax.set_title(dname, fontweight='bold')
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha='right')
    ax.set_ylabel('Post-Gap MAE Improvement (%)')
    ax.set_ylim(min(min(imps)-10, -10), max(imps)+12)

fig.suptitle('Stratified Post-Gap Recovery: TAIN improvement over Standard EMA by gap size',
             fontsize=13, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(OUTDIR/'fig_stratified_gap_recovery.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"  saved: {OUTDIR/'fig_stratified_gap_recovery.png'}")

# ============= FIGURE 2: L1 JITTER DECOMPOSITION =============
print("\nGenerating jitter decomposition figure (L1)...")

def l1_decompose(values, mus):
    dmu=np.diff(mus); dx=np.diff(values)
    abs_dmu=np.abs(dmu); abs_dx=np.abs(dx)
    tot=np.mean(abs_dmu)
    un=np.mean(np.maximum(0, abs_dmu-abs_dx))
    sig=np.mean(np.minimum(abs_dmu, abs_dx))
    rms=np.sqrt(np.mean(dmu**2))
    s=np.sign(dmu); nz=s[s!=0]
    flip=np.sum(np.diff(nz)!=0)/(len(nz)-1) if len(nz)>1 else 0.0
    b=(dmu!=0)&(dx!=0)
    dag=np.mean(np.sign(dmu[b])==np.sign(dx[b])) if b.sum()>0 else 0.0
    return {'tot':tot,'sig':sig,'un':un,'rms':rms,'flip':flip,'dag':dag}

key_methods=['Std EMA','TAIN','Linear EMA','Interp+EMA','DEMA','Kalman Filter','Holt ES']
jitter_data={}
for dname, series in datasets.items():
    jitter_data[dname]={}
    for m in key_methods:
        agg={'tot':[],'sig':[],'un':[],'rms':[],'flip':[],'dag':[]}
        for v,dt,_ in series:
            mu=METHODS[m](v,dt,ALPHA)
            d=l1_decompose(v,mu)
            for k in agg: agg[k].append(d[k])
        jitter_data[dname][m]={k:np.mean(v) for k,v in agg.items()}

fig,axes=plt.subplots(2,n_dom, figsize=(4.2*n_dom, 9))
for col,(dname,methods_d) in enumerate(jitter_data.items()):
    ax=axes[0,col]
    sig_vals=[methods_d[m]['sig'] for m in key_methods]
    un_vals=[methods_d[m]['un'] for m in key_methods]
    x=np.arange(len(key_methods))
    ax.bar(x, sig_vals, 0.6, color='#2ecc71', edgecolor='black', linewidth=0.4, label='Signal $J^{L^1}$')
    ax.bar(x, un_vals, 0.6, bottom=sig_vals, color='#e74c3c', edgecolor='black', linewidth=0.4, label='Unnec $J^{L^1}$')
    for i,(s,u) in enumerate(zip(sig_vals, un_vals)):
        tot=s+u
        if tot>0:
            ax.text(i, tot+tot*0.02, f'{u/tot*100:.0f}%', ha='center', va='bottom', fontsize=8, fontweight='bold')
    ax.set_title(dname, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace(' ','\n') for m in key_methods], fontsize=7)
    ax.set_ylabel('$J^{L^1}$ (mean abs.\\ change)' if col==0 else '')
    if col==0: ax.legend(fontsize=8, loc='upper left')

    ax=axes[1,col]
    flips=[methods_d[m]['flip']*100 for m in key_methods]
    dags=[methods_d[m]['dag']*100 for m in key_methods]
    w=0.35
    ax.bar(x-w/2, flips, w, color='#e67e22', edgecolor='black', linewidth=0.4, label='Flip %')
    ax.bar(x+w/2, dags, w, color='#3498db', edgecolor='black', linewidth=0.4, label='DirAgr %')
    ax.set_title(dname, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace(' ','\n') for m in key_methods], fontsize=7)
    ax.set_ylabel('%' if col==0 else '')
    if col==0: ax.legend(fontsize=8, loc='upper left')

fig.suptitle('$L^1$ Jitter Decomposition (top) and Action Stability Metrics (bottom)',
             fontsize=13, fontweight='bold', y=1.00)
plt.tight_layout()
plt.savefig(OUTDIR/'fig_jitter_decomposition.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"  saved: {OUTDIR/'fig_jitter_decomposition.png'}")

# ============= FIGURE 3: PARETO RMSE vs UNNECESSARY JITTER (L1) =============
print("\nGenerating Pareto figure...")
# We need per-entity RMSE — recompute
def entity_rmse(series, method):
    out=[]
    for v,dt,_ in series:
        mu=METHODS[method](v,dt,ALPHA)
        out.append(np.sqrt(np.mean((v-mu)**2)))
    return np.mean(out)

fig,axes=plt.subplots(1,n_dom, figsize=(4.2*n_dom,4.2))
markers={'Std EMA':'o','TAIN':'*','Linear EMA':'s','Interp+EMA':'D','DEMA':'^','Kalman Filter':'v','Holt ES':'X'}
mcolors={'Std EMA':'#7f8c8d','TAIN':'#2c3e50','Linear EMA':'#16a085','Interp+EMA':'#27ae60',
        'DEMA':'#f39c12','Kalman Filter':'#c0392b','Holt ES':'#8e44ad'}
for ax,(dname,series) in zip(axes, datasets.items()):
    for m in key_methods:
        rmse=entity_rmse(series, m)
        unnec=jitter_data[dname][m]['un']
        sz=300 if m=='TAIN' else 100
        ax.scatter(rmse, unnec, s=sz, marker=markers[m], c=mcolors[m], edgecolor='black', linewidth=0.8,
                  label=m, zorder=3 if m=='TAIN' else 2)
    ax.set_xlabel('RMSE')
    ax.set_ylabel('Unnecessary $J^{L^1}$' if dname=='Retail' else '')
    ax.set_title(dname, fontweight='bold')
    ax.set_xscale('log'); ax.set_yscale('log')
    if dname=='Retail': ax.legend(fontsize=7, loc='upper left')
fig.suptitle('Pareto frontier: RMSE vs.\\ unnecessary jitter ($L^1$). Bottom-left is optimal.',
             fontsize=13, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(OUTDIR/'fig_pareto_rmse_jitter.png', dpi=300, bbox_inches='tight')
plt.close()
print(f"  saved: {OUTDIR/'fig_pareto_rmse_jitter.png'}")

print("\nAll three figures regenerated.")
