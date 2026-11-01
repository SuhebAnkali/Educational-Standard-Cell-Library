#!/usr/bin/env python3
"""Plots from the measured characterization grid."""
import csv, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.abspath(os.path.join(HERE, "..", "results"))
rows = list(csv.DictReader(open(os.path.join(R, "nldm_tables.csv"))))
f = lambda r, k: float(r[k])

# ---- 1. delay vs load, one panel per cell, at tt ----
cells = ["INV", "NAND2", "NOR2", "DFF"]
fig, axes = plt.subplots(1, 4, figsize=(17, 4), sharey=False)
for ax, cell in zip(axes, cells):
    sel = [r for r in rows if r["cell"] == cell and r["pvt"] == "tt_1v80_25C"
           and r["arc"].startswith("A") or
           (r["cell"] == cell and r["pvt"] == "tt_1v80_25C" and cell == "DFF")]
    sel = [r for r in sel if r["cell"] == cell]
    for slew in sorted({f(r, "slew_target_ps") for r in sel}):
        s = sorted([r for r in sel if f(r, "slew_target_ps") == slew],
                   key=lambda r: f(r, "cload_fF"))
        ax.plot([f(r, "cload_fF") for r in s], [f(r, "cell_fall_ps") for r in s],
                "o-", label=f"{slew:g} ps in")
    ax.set(title=f"{cell}  cell_fall vs load (tt)", xlabel="CL (fF)",
           ylabel="delay (ps)")
    ax.grid(alpha=.3); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(R, "delay_vs_load.png"), dpi=130)

# ---- 2. the NLDM surface for the inverter ----
sel = [r for r in rows if r["cell"] == "INV" and r["pvt"] == "tt_1v80_25C"]
slews = sorted({f(r, "slew_target_ps") for r in sel})
loads = sorted({f(r, "cload_fF") for r in sel})
Z = np.zeros((len(slews), len(loads)))
for i, s in enumerate(slews):
    for j, c in enumerate(loads):
        Z[i, j] = next(f(r, "cell_fall_ps") for r in sel
                       if f(r, "slew_target_ps") == s and f(r, "cload_fF") == c)
fig, ax = plt.subplots(figsize=(6, 4.5))
im = ax.imshow(Z, origin="lower", aspect="auto", cmap="viridis")
ax.set_xticks(range(len(loads))); ax.set_xticklabels([f"{c:g}" for c in loads])
ax.set_yticks(range(len(slews))); ax.set_yticklabels([f"{s:g}" for s in slews])
ax.set(xlabel="output load (fF)", ylabel="input transition (ps)",
       title="INV cell_fall NLDM table (tt, ps)")
for i in range(len(slews)):
    for j in range(len(loads)):
        ax.text(j, i, f"{Z[i,j]:.0f}", ha="center", va="center",
                color="w", fontsize=8)
fig.colorbar(im, ax=ax, label="ps")
fig.tight_layout(); fig.savefig(os.path.join(R, "nldm_surface_inv.png"), dpi=130)

# ---- 3. PVT spread ----
fig, ax = plt.subplots(figsize=(7, 4.5))
width = 0.25
pvts = sorted({r["pvt"] for r in rows})
labels, xs = [], []
for k, cell in enumerate(["INV", "NAND2", "NOR2", "DFF"]):
    for m, pvt in enumerate(pvts):
        sel = [r for r in rows if r["cell"] == cell and r["pvt"] == pvt
               and f(r, "cload_fF") == 8.0 and f(r, "slew_target_ps") == 60.0]
        if not sel:
            continue
        v = np.mean([f(r, "cell_fall_ps") for r in sel])
        ax.bar(k + (m - 1) * width, v, width, color=f"C{m}",
               label=pvt if k == 0 else None)
    labels.append(cell); xs.append(k)
ax.set_xticks(xs); ax.set_xticklabels(labels)
ax.set(ylabel="cell_fall (ps)", title="PVT spread at 60 ps in / 8 fF out")
ax.grid(alpha=.3, axis="y"); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(R, "pvt_spread.png"), dpi=130)

# ---- 4. inverter VTC / butterfly ----
nm = list(csv.DictReader(open(os.path.join(R, "noise_margins.csv"))))
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
for r in nm:
    a = np.loadtxt(os.path.join(R, f"vtc_{r['pvt']}.dat"))
    vin, vout = a[:, 0], a[:, 1]
    ax[0].plot(vin, vout, label=r["pvt"])
    ax[1].plot(vin, vout, label=f"{r['pvt']} VTC")
    ax[1].plot(vout, vin, "--", lw=0.8)
ax[0].set(xlabel="Vin (V)", ylabel="Vout (V)", title="inverter VTC across PVT")
ax[0].grid(alpha=.3); ax[0].legend(fontsize=8)
ax[1].set(xlabel="V (V)", ylabel="V (V)",
          title="butterfly: VTC and its mirror (cross-coupled pair)")
ax[1].grid(alpha=.3); ax[1].legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(R, "vtc_butterfly.png"), dpi=130)
print("wrote 4 plots to", R)
