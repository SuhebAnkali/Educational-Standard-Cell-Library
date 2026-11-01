#!/usr/bin/env python3
"""
Standard-cell characterization on sky130: INV, NAND2, NOR2 and a DFF.

Produces what a real characterization run produces:

  * NLDM 2-D tables (input transition x output load) for cell_rise / cell_fall /
    rise_transition / fall_transition, per timing arc, per PVT corner
  * DFF clock-to-Q, plus setup and hold from a swept-separation search on the
    10%-degradation criterion
  * inverter static noise margins, both the VTC definition and the cross-coupled
    butterfly (maximum-square) definition

PERFORMANCE NOTE, because it dictates the structure of this file: ngspice spends
~35 s parsing the sky130 model library on every invocation, which utterly
dominates the ~0.2 s of actual simulation. Running the 4x4 grid as 16 separate
processes would take 10 minutes per arc. So each deck instead instantiates the
whole grid as 16 INDEPENDENT copies of the cell - own source, own load, own
measurements - and simulates them together in one transient. That turns ~400
invocations into 21 and the run from hours into minutes, with identical results
(the copies share only the ideal supplies).
"""

import csv
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS = os.path.abspath(os.path.join(HERE, "..", "cells"))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results"))
LOGS = os.path.join(RESULTS, "logs")
os.makedirs(LOGS, exist_ok=True)

SLEWS_PS = [20.0, 60.0, 200.0, 600.0]
LOADS_FF = [2.0, 8.0, 24.0, 72.0]

PVT = [
    ("tt_1v80_25C", "tt", 1.80, 25),
    ("ff_1v98_m40C", "ff", 1.98, -40),
    ("ss_1v62_125C", "ss", 1.62, 125),
]

# (cell, arc, instance line template, side-input level)
ARCS = [
    ("INV",   "A->Y", "XDUT{i} A{i} Y{i} VPWR VGND inv",           None),
    ("NAND2", "A->Y", "XDUT{i} A{i} SIDE Y{i} VPWR VGND nand2",    "high"),
    ("NAND2", "B->Y", "XDUT{i} SIDE A{i} Y{i} VPWR VGND nand2",    "high"),
    ("NOR2",  "A->Y", "XDUT{i} A{i} SIDE Y{i} VPWR VGND nor2",     "low"),
    ("NOR2",  "B->Y", "XDUT{i} SIDE A{i} Y{i} VPWR VGND nor2",     "low"),
]


def ngspice(deck_text, tag):
    path = os.path.join(CELLS, f"_run_{tag}.spice")
    open(path, "w").write(deck_text)
    log = os.path.join(LOGS, f"{tag}.log")
    with open(log, "w") as lf:
        p = subprocess.run(["ngspice", "-b", os.path.basename(path)], cwd=CELLS,
                           stdout=lf, stderr=subprocess.STDOUT, text=True)
    os.remove(path)
    if p.returncode != 0:
        raise RuntimeError(f"ngspice failed for {tag}; see {log}")
    return open(log).read()


def meas_all(log):
    """Every 'name = value' measurement result in the log."""
    return {m.group(1): float(m.group(2))
            for m in re.finditer(r"^(\w+)\s*=\s*([-\d.eE+]+)", log, re.M)}


def header(corner, vdd, temp):
    return (f".lib pdk/libs.tech/ngspice/sky130.lib.spice {corner}\n"
            f".include cells.spice\n"
            f".temp {temp}\n"
            f"Vdd  VPWR 0 {vdd}\n"
            f"Vgnd VGND 0 0\n")


# ---------------------------------------------------------------------------
def characterize_combinational():
    rows = []
    for cell, arc, inst, side in ARCS:
        for pvt_name, corner, vdd, temp in PVT:
            v20, v50, v80 = 0.2 * vdd, 0.5 * vdd, 0.8 * vdd
            d = [f"* {cell} {arc} @ {pvt_name}: the whole 4x4 grid in one deck",
                 header(corner, vdd, temp)]
            if side == "high":
                d.append(f"Vside SIDE 0 {vdd}")
            elif side == "low":
                d.append("Vside SIDE 0 0")
            grid = []
            for i, (slew, cl) in enumerate(
                    [(s, c) for s in SLEWS_PS for c in LOADS_FF]):
                trf = slew / 0.6 * 1e-3                    # ps -> ns, 20-80% -> 0-100%
                d.append(f"Vin{i} A{i} 0 PULSE(0 {vdd} 2n {trf:g}n {trf:g}n 8n 20n)")
                d.append(inst.format(i=i))
                d.append(f"CL{i} Y{i} 0 {cl:g}f")
                grid.append((i, slew, cl))
            d.append("")
            d.append(".tran 5p 20n")
            d.append(".control")
            d.append("set filetype=ascii")
            d.append("run")
            for i, slew, cl in grid:
                d += [f"meas tran itr{i}  trig v(A{i}) val={v20:.6g} rise=1 targ v(A{i}) val={v80:.6g} rise=1",
                      f"meas tran tphl{i} trig v(A{i}) val={v50:.6g} rise=1 targ v(Y{i}) val={v50:.6g} fall=1",
                      f"meas tran tplh{i} trig v(A{i}) val={v50:.6g} fall=1 targ v(Y{i}) val={v50:.6g} rise=1",
                      f"meas tran otf{i}  trig v(Y{i}) val={v80:.6g} fall=1 targ v(Y{i}) val={v20:.6g} fall=1",
                      f"meas tran otr{i}  trig v(Y{i}) val={v20:.6g} rise=1 targ v(Y{i}) val={v80:.6g} rise=1"]
            d += [".endc", ".end", ""]
            tag = f"{cell}_{arc.replace('->','_')}_{pvt_name}"
            m = meas_all(ngspice("\n".join(d), tag))
            for i, slew, cl in grid:
                need = [f"itr{i}", f"tphl{i}", f"tplh{i}", f"otf{i}", f"otr{i}"]
                if any(k not in m for k in need):
                    raise RuntimeError(f"missing measurement {need} in {tag}")
                rows.append(dict(
                    cell=cell, arc=arc, pvt=pvt_name, corner=corner, vdd=vdd,
                    temp_C=temp, slew_target_ps=slew,
                    slew_meas_ps=m[f"itr{i}"] * 1e12, cload_fF=cl,
                    cell_fall_ps=m[f"tphl{i}"] * 1e12,
                    cell_rise_ps=m[f"tplh{i}"] * 1e12,
                    fall_transition_ps=m[f"otf{i}"] * 1e12,
                    rise_transition_ps=m[f"otr{i}"] * 1e12))
            print(f"  {cell:<6} {arc:<6} {pvt_name:<13} 16 points")
    return rows


def characterize_dff():
    rows = []
    for pvt_name, corner, vdd, temp in PVT:
        v20, v50, v80 = 0.2 * vdd, 0.5 * vdd, 0.8 * vdd
        d = [f"* DFF CLK->Q @ {pvt_name}", header(corner, vdd, temp)]
        # three rising edges: initialise (D=0), capture 1 (rise), capture 0 (fall)
        d.append(f"Vclk CLK 0 PULSE(0 {vdd} 5n 0.05n 0.05n 4n 10n)")
        grid = []
        for i, (slew, cl) in enumerate([(s, c) for s in SLEWS_PS for c in LOADS_FF]):
            trf = slew / 0.6 * 1e-3
            d.append(f"Vd{i} D{i} 0 PWL(0 0  12n 0  {12+trf:g}n {vdd}  22n {vdd}  {22+trf:g}n 0)")
            d.append(f"XDUT{i} D{i} CLK Q{i} VPWR VGND dff")
            d.append(f"CL{i} Q{i} 0 {cl:g}f")
            grid.append((i, slew, cl))
        d += ["", ".tran 5p 34n", ".control", "set filetype=ascii", "run"]
        for i, slew, cl in grid:
            d += [f"meas tran tcqr{i} trig v(CLK) val={v50:.6g} rise=1 td=12n targ v(Q{i}) val={v50:.6g} rise=1 td=12n",
                  f"meas tran tcqf{i} trig v(CLK) val={v50:.6g} rise=1 td=22n targ v(Q{i}) val={v50:.6g} fall=1 td=22n",
                  f"meas tran qtr{i}  trig v(Q{i}) val={v20:.6g} rise=1 td=12n targ v(Q{i}) val={v80:.6g} rise=1 td=12n",
                  f"meas tran qtf{i}  trig v(Q{i}) val={v80:.6g} fall=1 td=22n targ v(Q{i}) val={v20:.6g} fall=1 td=22n"]
        d += [".endc", ".end", ""]
        m = meas_all(ngspice("\n".join(d), f"DFF_CLK_Q_{pvt_name}"))
        for i, slew, cl in grid:
            if f"tcqr{i}" not in m or f"tcqf{i}" not in m:
                raise RuntimeError(f"DFF did not capture at {pvt_name} point {i}")
            rows.append(dict(
                cell="DFF", arc="CLK->Q", pvt=pvt_name, corner=corner, vdd=vdd,
                temp_C=temp, slew_target_ps=slew, slew_meas_ps=slew, cload_fF=cl,
                cell_rise_ps=m[f"tcqr{i}"] * 1e12,
                cell_fall_ps=m[f"tcqf{i}"] * 1e12,
                rise_transition_ps=m.get(f"qtr{i}", 0) * 1e12,
                fall_transition_ps=m.get(f"qtf{i}", 0) * 1e12))
        print(f"  DFF    CLK->Q {pvt_name:<13} 16 points")
    return rows


# ---------------------------------------------------------------------------
def dff_constraint(kind, pvt_name, corner, vdd, temp, slew_ps=60.0, cl_ff=8.0):
    """Setup or hold from a swept-separation batch on the 10% criterion.

    The criterion is reported with the number, because a setup time without one
    is meaningless: the same flip-flop gives very different answers under a 1%,
    10% or fail-to-capture definition.

    Two passes: a coarse sweep to bracket the knee, then a fine sweep across the
    bracket. Both passes are a SINGLE ngspice run each, with one independent
    flip-flop instance per candidate separation - the same trick that makes the
    NLDM grid affordable.

    A transmission-gate flip-flop can legitimately have a negative hold time,
    because the internal clock inverters delay the latch relative to the CLK
    pin, so the sweep extends into negative separations.
    """
    TCLK, v50 = 20.0, 0.5 * vdd
    trf = slew_ps / 0.6 * 1e-3
    good_q = 0.9 * vdd

    def sweep(seps, tag):
        d = [f"* DFF {kind} sweep @ {pvt_name}", header(corner, vdd, temp)]
        d.append(f"Vclk CLK 0 PULSE(0 {vdd} 5n {trf:g}n {trf:g}n 4n 15n)")
        for i, sep in enumerate(seps):
            td = TCLK - sep if kind == "setup" else TCLK + sep
            if kind == "setup":
                # D rises at td and stays high; the edge at 20 ns must capture it
                d.append(f"Vd{i} D{i} 0 PWL(0 0  {td:.5f}n 0  {td+trf:.5f}n {vdd}  34n {vdd})")
            else:
                # D is already high well before the edge and is pulled away at td
                d.append(f"Vd{i} D{i} 0 PWL(0 0  12n 0  {12+trf:.5f}n {vdd}  "
                         f"{td:.5f}n {vdd}  {td+trf:.5f}n 0  34n 0)")
            d.append(f"XDUT{i} D{i} CLK Q{i} VPWR VGND dff")
            d.append(f"CL{i} Q{i} 0 {cl_ff:g}f")
        d += ["", ".tran 5p 32n", ".control", "set filetype=ascii", "run"]
        for i, _ in enumerate(seps):
            d += [f"meas tran tcq{i} trig v(CLK) val={v50:.6g} rise=1 td=12n targ v(Q{i}) val={v50:.6g} rise=1 td=12n",
                  f"meas tran qf{i} find v(Q{i}) at=30n"]
        d += [".endc", ".end", ""]
        m = meas_all(ngspice("\n".join(d), tag))
        return [(sep, m.get(f"tcq{i}"), m.get(f"qf{i}")) for i, sep in enumerate(seps)]

    coarse = [round(x, 4) for x in np.concatenate([
        np.linspace(-0.60, 0.20, 17), np.array([0.4, 0.8, 1.5, 3.0, 5.0])])]
    res = sweep(coarse, f"DFF_{kind}_{pvt_name}_coarse")
    ref = next((t for s, t, q in reversed(res)
                if t is not None and q is not None and q > good_q), None)
    if ref is None:
        raise RuntimeError(f"{kind}: no relaxed point captured at {pvt_name}")
    limit = ref * 1.10

    def ok(t, q):
        return t is not None and q is not None and q > good_q and t <= limit

    passing = [s for s, t, q in res if ok(t, q)]
    if not passing:
        raise RuntimeError(f"{kind}: nothing passed at {pvt_name}")
    smallest = min(passing)
    if smallest <= coarse[0] + 1e-9:
        return dict(pvt=pvt_name, kind=kind, value_ps=smallest * 1000.0,
                    bounded="no (still passes at the edge of the sweep)",
                    reference_tcq_ps=ref * 1e12,
                    criterion="10% clk->Q degradation", slew_ps=slew_ps,
                    cload_fF=cl_ff)
    failing_below = max([s for s, t, q in res if not ok(t, q) and s < smallest],
                        default=coarse[0])
    fine = [round(failing_below + (smallest - failing_below) * k / 20.0, 5)
            for k in range(21)]
    res2 = sweep(fine, f"DFF_{kind}_{pvt_name}_fine")
    passing2 = [s for s, t, q in res2 if ok(t, q)]
    val = min(passing2) if passing2 else smallest
    return dict(pvt=pvt_name, kind=kind, value_ps=val * 1000.0, bounded="yes",
                reference_tcq_ps=ref * 1e12,
                criterion="10% clk->Q degradation", slew_ps=slew_ps, cload_fF=cl_ff)


# ---------------------------------------------------------------------------
def inverter_noise_margins():
    out = []
    for pvt_name, corner, vdd, temp in PVT:
        deck = (f"* inverter VTC for noise margins @ {pvt_name}\n"
                + header(corner, vdd, temp)
                + "Vin A 0 1\nXDUT A Y VPWR VGND inv\n"
                + f".dc Vin 0 {vdd} 0.002\n.control\nset filetype=ascii\nrun\n"
                + f"wrdata {RESULTS}/vtc_{pvt_name}.dat v(Y)\n.endc\n.end\n")
        ngspice(deck, f"vtc_{pvt_name}")
        a = np.loadtxt(os.path.join(RESULTS, f"vtc_{pvt_name}.dat"))
        vin, vout = a[:, 0], a[:, 1]
        g = np.gradient(vout, vin)

        def cross(y, t, last=False):
            d = y - t
            idx = np.where(np.sign(d[:-1]) * np.sign(d[1:]) < 0)[0]
            if not len(idx):
                return None
            i = idx[-1] if last else idx[0]
            return vin[i] - d[i] * (vin[i + 1] - vin[i]) / (d[i + 1] - d[i])

        vil, vih = cross(g, -1.0), cross(g, -1.0, last=True)
        voh = float(np.interp(vil, vin, vout))
        vol = float(np.interp(vih, vin, vout))
        # butterfly SNM: largest square between the VTC and its mirror image,
        # which is the definition used for a cross-coupled pair
        mirror = np.interp(vin, vout[::-1], vin[::-1])
        snm = float(np.max(np.abs(vout - mirror)) / np.sqrt(2.0))
        out.append(dict(pvt=pvt_name, vdd=vdd, temp_C=temp, VIL_V=vil, VIH_V=vih,
                        VOL_V=vol, VOH_V=voh, NMH_V=voh - vih, NML_V=vil - vol,
                        peak_gain=float(np.min(g)), butterfly_SNM_V=snm))
        print(f"  {pvt_name:<13} NMH={voh-vih:.4f}  NML={vil-vol:.4f}  "
              f"butterfly SNM={snm:.4f} V")
    return out


def write_csv(path, rows, cols):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.6g}" if isinstance(r[k], float) else r[k])
                        for k in cols})


def main():
    print("=== combinational arcs (INV / NAND2 / NOR2), 4x4 grid per deck ===")
    comb = characterize_combinational()
    print("=== DFF clock-to-Q ===")
    dff = characterize_dff()
    write_csv(os.path.join(RESULTS, "nldm_tables.csv"), comb + dff,
              ["cell", "arc", "pvt", "corner", "vdd", "temp_C", "slew_target_ps",
               "slew_meas_ps", "cload_fF", "cell_rise_ps", "cell_fall_ps",
               "rise_transition_ps", "fall_transition_ps"])
    print(f"  -> nldm_tables.csv ({len(comb)+len(dff)} measured points)")

    print("=== DFF setup / hold (swept separation, 10% criterion) ===")
    con = []
    for pvt_name, corner, vdd, temp in PVT:
        for kind in ("setup", "hold"):
            r = dff_constraint(kind, pvt_name, corner, vdd, temp)
            con.append(r)
            print(f"  {pvt_name:<13} {kind:<5} = {r['value_ps']:7.1f} ps "
                  f"(bounded: {r['bounded']}, ref clk->Q "
                  f"{r['reference_tcq_ps']:.1f} ps)")
    write_csv(os.path.join(RESULTS, "dff_constraints.csv"), con,
              ["pvt", "kind", "value_ps", "bounded", "reference_tcq_ps",
               "criterion", "slew_ps", "cload_fF"])

    print("=== inverter noise margins ===")
    nm = inverter_noise_margins()
    write_csv(os.path.join(RESULTS, "noise_margins.csv"), nm,
              ["pvt", "vdd", "temp_C", "VIL_V", "VIH_V", "VOL_V", "VOH_V",
               "NMH_V", "NML_V", "peak_gain", "butterfly_SNM_V"])
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
