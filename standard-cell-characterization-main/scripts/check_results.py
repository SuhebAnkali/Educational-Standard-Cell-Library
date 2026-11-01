#!/usr/bin/env python3
"""
Validate the characterization results against the plan's pass criteria.

These are the checks that make the tables trustworthy: a .lib full of numbers is
worthless if the grid is incomplete, the delays are non-monotonic in load, or the
two input arcs of a NAND2 came out identical (which would mean the side input was
never actually held).
"""
import csv, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.abspath(os.path.join(HERE, "..", "results"))
rows = list(csv.DictReader(open(os.path.join(R, "nldm_tables.csv"))))
con = list(csv.DictReader(open(os.path.join(R, "dff_constraints.csv"))))
nm = list(csv.DictReader(open(os.path.join(R, "noise_margins.csv"))))
F = lambda r, k: float(r[k])

out, fails = [], 0


def check(name, ok, detail=""):
    global fails
    out.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        fails += 1


# 1. grid completeness
comb = [r for r in rows if r["cell"] != "DFF"]
dff = [r for r in rows if r["cell"] == "DFF"]
check("grid completeness: 240 combinational rows", len(comb) == 240, f"got {len(comb)}")
check("grid completeness: 48 DFF rows", len(dff) == 48, f"got {len(dff)}")

# 2. the achieved input transition tracks the target
worst = 0.0
for r in comb:
    t, m = F(r, "slew_target_ps"), F(r, "slew_meas_ps")
    worst = max(worst, abs(m - t) / t)
check("measured input transition within 10% of target", worst < 0.10,
      f"worst deviation {worst*100:.1f}%")

# 3. delay monotonic in load
bad = []
groups = defaultdict(list)
for r in rows:
    groups[(r["cell"], r["arc"], r["pvt"], r["slew_target_ps"])].append(r)
for k, g in groups.items():
    g = sorted(g, key=lambda r: F(r, "cload_fF"))
    for field in ("cell_rise_ps", "cell_fall_ps"):
        v = [F(r, field) for r in g]
        if any(b < a for a, b in zip(v, v[1:])):
            bad.append((k, field, v))
check("delay increases monotonically with load", not bad,
      f"{len(bad)} non-monotonic series" if bad else f"{len(groups)} series checked")

# 4. the two input arcs of NAND2 / NOR2 must actually differ
for cell in ("NAND2", "NOR2"):
    a = {(r["pvt"], r["slew_target_ps"], r["cload_fF"]): F(r, "cell_fall_ps")
         for r in comb if r["cell"] == cell and r["arc"] == "A->Y"}
    b = {(r["pvt"], r["slew_target_ps"], r["cload_fF"]): F(r, "cell_fall_ps")
         for r in comb if r["cell"] == cell and r["arc"] == "B->Y"}
    diffs = [abs(a[k] - b[k]) / a[k] for k in a if k in b]
    mx = max(diffs) * 100 if diffs else 0
    check(f"{cell}: A->Y and B->Y arcs are distinguishable", mx > 0.5,
          f"max difference {mx:.1f}% of cell_fall")

# 5. setup/hold present for every corner, with a criterion
pvts = sorted({r["pvt"] for r in rows})
for p in pvts:
    for kind in ("setup", "hold"):
        c = [x for x in con if x["pvt"] == p and x["kind"] == kind]
        check(f"DFF {kind} characterized at {p}",
              len(c) == 1 and c[0]["criterion"],
              (f"{float(c[0]['value_ps']):.1f} ps, bounded={c[0]['bounded']}"
               if c else "missing"))

# 6. noise margins positive
for r in nm:
    check(f"inverter noise margins positive at {r['pvt']}",
          F(r, "NMH_V") > 0 and F(r, "NML_V") > 0,
          f"NMH={F(r,'NMH_V'):.3f} NML={F(r,'NML_V'):.3f} "
          f"butterflySNM={F(r,'butterfly_SNM_V'):.3f}")

# 7. structural validation of every generated .lib
for p in sorted(os.listdir(R)):
    if not p.endswith(".lib"):
        continue
    txt = open(os.path.join(R, p)).read()
    braces = txt.count("{") - txt.count("}")
    idx1 = re.search(r'index_1 \("([^"]+)"\);', txt)
    idx2 = re.search(r'index_2 \("([^"]+)"\);', txt)
    n1 = len(idx1.group(1).split(",")) if idx1 else 0
    n2 = len(idx2.group(1).split(",")) if idx2 else 0
    # line-based rather than one big regex: a values() block ends with ');' on
    # the final row, which a single "every row looks the same" pattern misses
    tables, cur = [], None
    for ln in txt.split("\n"):
        st = ln.strip()
        if st.startswith("values ( \\"):
            cur = []
        elif cur is not None:
            q = re.findall(r'"([^"]+)"', st)
            if q:
                cur.append(q[0])
            if st.endswith(");"):
                tables.append(cur)
                cur = None
    okrows = all(len(t) == n1 for t in tables)
    okcols = all(all(len(r.split(",")) == n2 for r in t) for t in tables)
    check(f"{p}: braces balanced", braces == 0, f"delta {braces}")
    check(f"{p}: {len(tables)} tables have {n1} rows x {n2} columns",
          okrows and okcols and len(tables) > 0,
          f"rows_ok={okrows} cols_ok={okcols}")

text = "\n".join(out) + f"\n\n{len(out)-fails}/{len(out)} checks passed\n"
open(os.path.join(R, "check_summary.txt"), "w").write(text)
print(text)
sys.exit(1 if fails else 0)
