# standard-cell-characterization

Characterization of a small cell library — **INV, NAND2, NOR2 and a
transmission-gate DFF** — on the sky130 PDK with ngspice, emitted as a
**Liberty (.lib) file** per PVT corner that a synthesis or STA tool can read.

Every number in [`results/`](results/) is a measurement. `make check` validates
them against the plan's criteria and prints a pass/fail line for each.

---

## 1. Result summary

| | |
|---|---|
| Measured points | **288** (5 combinational arcs + DFF) × 3 PVT × 4 slews × 4 loads |
| Validation | **21/21 checks passed** (`results/check_summary.txt`) |
| Liberty output | 3 files, **24 NLDM tables each**, all 4×4, braces balanced |
| DFF constraints | setup 12.5 / 15.0 / 25.0 ps, hold −12.5 / −10.0 / 0.0 ps across ff/tt/ss |
| Inverter margins | NMH/NML positive at all corners; butterfly SNM 0.593 – 0.753 V |

```bash
./run.sh
```

---

## 2. What was characterized, and how

| Cell | Sizing (µm) | Reasoning |
|---|---|---|
| INV | WN 0.65 / WP 1.30 | 2:1 for roughly balanced edges |
| NAND2 | WN 1.30 / WP 1.30 | NMOS in series → doubled; PMOS in parallel → unchanged |
| NOR2 | WN 0.65 / WP 2.60 | NMOS in parallel → unchanged; PMOS in series → doubled |
| DFF | master-slave, TG-based | tristate-gated feedback, so there is never a drive fight to size around |

**Grid:** input transitions 20 / 60 / 200 / 600 ps (measured 20–80 %) × loads
2 / 8 / 24 / 72 fF, at three **PVT** corners — process *and* voltage *and*
temperature, not just process:

| corner | process | VDD | temp |
|---|---|---|---|
| `ff_1v98_m40C` | ff | 1.98 V | −40 °C |
| `tt_1v80_25C` | tt | 1.80 V | 25 °C |
| `ss_1v62_125C` | ss | 1.62 V | 125 °C |

### The NLDM table, for real

`INV` `cell_fall`, tt corner, picoseconds (`results/nldm_tables.csv`,
`nldm_surface_inv.png`):

| in ↓ / load → | 2 fF | 8 fF | 24 fF | 72 fF |
|---|---|---|---|---|
| **20 ps** | 18.1 | 35.8 | 81.4 | 217.5 |
| **60 ps** | 27.5 | 50.5 | 96.2 | 232.4 |
| **200 ps** | 39.9 | 83.0 | 147.8 | 284.8 |
| **600 ps** | 46.5 | 120.5 | 234.9 | 432.6 |

This is why NLDM is 2-D and not a single "delay per fF" number: at 2 fF, going
from a 20 ps to a 600 ps input slows the cell by **2.6×**, while at 72 fF the same
change costs only 2.0× — input slew and output load are not separable.

---

## 3. Three results worth pointing at

### The two input arcs of a NAND2 and a NOR2 are *not* the same

`cell_fall` at tt, 60 ps in (ps):

| | 2 fF | 8 fF | 24 fF | 72 fF |
|---|---|---|---|---|
| NAND2 A→Y | 26.5 | 46.2 | 83.8 | 194.9 |
| NAND2 B→Y | 30.5 | 47.9 | 85.6 | 196.7 |
| NOR2 A→Y | **45.9** | 64.6 | 111.3 | 248.2 |
| NOR2 B→Y | **32.7** | 54.4 | 101.2 | 238.2 |

The NOR2 arcs differ by **up to 129 %** of `cell_fall`, the NAND2 by up to 68 %.
The reason is stack position: the transistor next to the rail sees an already-
discharged internal node, the one next to the output has to pull the internal
node too. A library that publishes one arc for both inputs throws that away —
so `make check` **fails the run if the two arcs come out identical**, which would
mean the side input was never actually held at its non-controlling level.

Note also that the difference **shrinks as the load grows** (129 % → 4 % for
NOR2 from 2 fF to 72 fF): at heavy loads the external capacitance dominates the
internal node, so the arcs converge. That is the kind of thing a 2-D table shows
and a single-point spec cannot.

### PVT spread is 3× and the flip-flop is the worst of it

`cell_fall` at 60 ps in / 8 fF out (ps):

| cell | ff/1.98 V/−40 °C | tt/1.80 V/25 °C | ss/1.62 V/125 °C | spread |
|---|---|---|---|---|
| INV | 33.8 | 50.5 | 81.1 | 2.4× |
| NAND2 | 30.3 | 46.2 | 71.0 | 2.3× |
| NOR2 | 44.6 | 64.6 | 112.6 | 2.5× |
| **DFF** | 117.9 | 190.5 | **357.9** | **3.0×** |

The DFF spreads more than the gates because its clk→Q path is a chain of six
stages, and each one degrades — corner effects compound along a path.

### The DFF has a negative hold time, and that is correct

`results/dff_constraints.csv`:

| corner | setup (ps) | hold (ps) | reference clk→Q (ps) |
|---|---|---|---|
| ff/1.98 V/−40 °C | 12.5 | **−12.5** | 114.6 |
| tt/1.80 V/25 °C | 15.0 | **−10.0** | 186.0 |
| ss/1.62 V/125 °C | 25.0 | 0.0 | 334.6 |

A negative hold time means D may change *slightly before* the clock edge reaches
the latch and still be captured — because the CLK pin drives two internal
inverters before it reaches the master's transmission gate, so the latch closes
after the pin edge. The search therefore sweeps into negative separations and
reports whether the result was **bounded**; clipping at zero would have
manufactured a wrong number.

**Every constraint is reported with its criterion** (10 % clk→Q degradation), its
input transition and its load, because a setup time without those is not a
number anyone can use — the same flip-flop yields very different answers under a
1 %, 10 % or fail-to-capture definition.

### Inverter noise margins — two definitions

| corner | VIL | VIH | NMH | NML | peak gain | butterfly SNM |
|---|---|---|---|---|---|---|
| tt/1.80 V/25 °C | 0.733 | 0.966 | 0.784 | 0.667 | −13.7 | **0.651 V** |
| ff/1.98 V/−40 °C | — | — | 0.912 | 0.607 | — | **0.753 V** |
| ss/1.62 V/125 °C | — | — | 0.612 | 0.702 | — | **0.593 V** |

NMH/NML come from the VTC unity-gain points. The **butterfly SNM** is the
largest square that fits between the VTC and its mirror image — the definition
that applies to a cross-coupled pair (an SRAM cell or a latch), which is the
context where "static noise margin" is usually meant.

---

## 4. The Liberty output

`results/sky130_char_<pvt>.lib`, generated by `scripts/write_lib.py` straight
from the CSV:

```liberty
  cell (NOR2) {
    pin (Y) {
      direction : output;
      function : "!(A + B)";
      timing () {
        related_pin  : "A";
        timing_sense : negative_unate;
        cell_rise (delay_template_4x4) {
          values ( \
            "0.02172, 0.04565, 0.10808, 0.29409", \
            ...
```

`make check` validates each file structurally rather than by eye: braces
balanced, every table present, every row count equal to `index_1`, every column
count equal to `index_2`. **24 tables per file, all 4×4, all three files clean.**

---

## 5. The thing that made this run at all

The first version launched one ngspice process per grid point. It measured at
**36 s per point** — because ngspice spends ~35 s parsing the sky130 model
library on every invocation, dwarfing the ~0.2 s of actual simulation. 400 points
would have been three hours.

Each deck now instantiates the **whole 4×4 grid as 16 independent copies** of the
cell — own source, own load, own `.meas` statements — and simulates them together
in one transient. 400 invocations became 21, the run went from hours to minutes,
and the numbers are identical (the copies share only the ideal supplies; the
first restructured point reproduced 50.46 ps against the per-point run's 50.5 ps).

Two other traps that cost time and are worth writing down:

- **`.param` is invisible inside `.control`.** Writing `val='0.5*VDD'` in a
  `meas` statement fails *silently per measurement* while the simulation itself
  runs fine — you get a clean-looking log and no results. The thresholds are
  substituted as literal numbers instead.
- **The DFF needs an initialising clock edge.** The operating point leaves the
  slave latch in an arbitrary state, so Q can already be high when the "rising"
  edge arrives and `tcq_r` returns nothing. Each deck now uses three edges —
  capture 0, capture 1 (measured), capture 0 (measured) — and every measurement
  is time-windowed with `td=` so it cannot latch onto the initialising edge.

---

## 6. Layout & how to run

```
standard-cell-characterization/
├── PLAN.md  README.md  Makefile  run.sh  requirements.txt
├── cells/
│   ├── cells.spice          INV, NAND2, NOR2, transmission gate, DFF
│   └── tb_*.spice           reference decks (the batched grids are built in Python)
├── scripts/
│   ├── characterize.py      every measurement + the setup/hold search
│   ├── write_lib.py         Liberty generation
│   ├── plot_char.py         figures
│   └── check_results.py     validates the results against the plan's criteria
└── results/
    ├── nldm_tables.csv      288 measured points
    ├── dff_constraints.csv  setup/hold with criterion, load and slew
    ├── noise_margins.csv    VTC margins + butterfly SNM
    ├── sky130_char_*.lib    3 Liberty files
    ├── check_summary.txt    21/21
    └── *.png
```

```bash
./run.sh                # everything
make char               # the ngspice grid (~15 min)
make lib ; make plots ; make check
```

---

## 7. What this demonstrates

- **Characterization as it is actually done**: 2-D NLDM tables indexed by input
  transition and output load, per arc, per PVT — and the Liberty file that makes
  them usable downstream, validated structurally rather than assumed correct.
- **Reading the data, not just producing it**: the NAND2/NOR2 arc asymmetry and
  its convergence at high load, the compounding of corner effects along the
  flip-flop's six-stage clk→Q path, and a negative hold time explained by the
  internal clock inverters rather than clipped away.
- **Measurement discipline**: constraints reported with the criterion that
  defines them, achieved input slew measured back and checked against the target,
  monotonicity in load checked across all 72 series, and a run structure chosen
  after measuring where the time actually went.
