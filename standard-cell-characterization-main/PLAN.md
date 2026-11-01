# PLAN — Project 5: `standard-cell-characterization`

Characterize a small cell library — **INV, NAND2, NOR2 and a master-slave DFF** —
on the sky130 PDK with ngspice, and emit the result as a **Liberty (.lib) file**
that a synthesis or STA tool could actually read.

---

## 1. Scope

### In scope
- Four cells, sized by logical-effort reasoning rather than copied:
  INV (2:1), NAND2 (NMOS doubled for the series stack), NOR2 (PMOS doubled),
  and a transmission-gate DFF with tristate feedback.
- **NLDM 2-D tables**: `input_net_transition` × `total_output_net_capacitance`
  → `cell_rise`, `cell_fall`, `rise_transition`, `fall_transition`.
  Grid: 4 input transitions (20, 60, 200, 600 ps) × 4 loads (2, 8, 24, 72 fF).
- **Both input arcs** for NAND2 and NOR2 (A→Y and B→Y). They are not the same:
  the transistor nearer the rail in a series stack switches faster, and a table
  that reports one number for both hides that.
- **3 PVT corners** — not just process: `tt/1.80 V/25 °C`, `ff/1.98 V/−40 °C`,
  `ss/1.62 V/125 °C`.
- **DFF setup and hold** found by bisection on the 10 %-clock-to-Q-degradation
  criterion, with the criterion reported alongside the number.
- **Static noise margin for the inverter**, in both senses: NMH/NML from the VTC
  unity-gain points, and the **butterfly (maximum-square) SNM** of a
  cross-coupled pair.
- A syntactically complete `.lib` per corner, generated from the measurements.

### Out of scope
- Power/leakage tables (`internal_power`, `leakage_power` groups).
- Multi-input simultaneous switching, `when`-conditional arcs.
- Statistical/LVF (`ocv_sigma_*`) characterization.
- Layout of the cells (Project 4 covers the physical flow).

---

## 2. Block diagram of the flow

```
  cells/cells.spice          ┌───────────────────────────────────────────┐
   INV NAND2 NOR2 DFF   ───► │ scripts/characterize.py                   │
                             │   for arc in 5 combinational arcs:        │
  cells/tb_comb.spice   ───► │     for pvt in 3:                         │ ──► ngspice
  cells/tb_dff.spice         │       for slew in 4:                      │      (~400 runs)
  cells/tb_dff_setup.spice   │         for load in 4:  measure           │
  cells/tb_dff_hold.spice    │   DFF setup/hold: bisection               │
                             │   INV: DC sweep -> noise margins          │
                             └────────────────┬──────────────────────────┘
                                              │
                     ┌────────────────────────┼────────────────────────┐
                     ▼                        ▼                        ▼
            nldm_tables.csv          dff_constraints.csv       noise_margins.csv
                     │                        │                        │
                     └────────► scripts/write_lib.py ◄─────────────────┘
                                              │
                                              ▼
                              results/sky130_char_<pvt>.lib   (one per corner)
```

---

## 3. Method notes that matter

- **Input transitions are specified as measured 20–80 % values.** A linear PULSE
  ramp of duration *T* has a 20–80 % transition of 0.6 *T*, so the deck is driven
  with `TRF = slew/0.6` and the achieved transition is measured back and stored
  next to the target. If the two disagree, the table index is wrong.
- **The DFF needs an initialising clock edge.** The operating point leaves the
  slave latch in an arbitrary state, so the first edge captures D = 0 to force
  Q low; the measured edges are the second and third. Without it the rising
  clk→Q measurement silently returns nothing on some corners and not others.
- **Setup/hold are meaningless without their criterion**, so the criterion
  (10 % clk→Q degradation), the input transition and the load are recorded in
  the CSV next to every value.
- A transmission-gate flip-flop can have a **negative** hold time, because the
  internal clock inverters delay the latch relative to the CLK pin. The search
  therefore brackets into negative separations and reports "unbounded" rather
  than clipping at zero if the edge of the bracket still passes.

---

## 4. Pass / fail criteria (exact)

1. Every point in the grid produces a numeric measurement; a missing `.meas`
   result is an error, not a blank cell. `results/nldm_tables.csv` must contain
   **5 combinational arcs × 3 PVT × 4 slews × 4 loads = 240 rows** plus
   **3 × 4 × 4 = 48** DFF rows.
2. Measured input transition must track the target within 10 % for every row.
3. Delay must increase monotonically with load at fixed input transition, for
   every arc and corner. A non-monotonic row means a broken measurement.
4. NAND2 and NOR2 must show a **measurable A→Y vs B→Y difference**; if the two
   arcs come out identical the side-input handling is wrong.
5. Setup and hold must be found for all 3 corners, each with its criterion and
   its bracketing status recorded.
6. Inverter noise margins must be positive at all 3 corners, and the butterfly
   SNM reported.
7. `results/sky130_char_<pvt>.lib` must parse as Liberty: balanced braces, every
   `values()` row length equal to `index_2` length, every table row count equal
   to `index_1` length. Checked programmatically, not by eye.

---

## 5. Risks

| Risk | Mitigation |
|---|---|
| `.meas` silently failing (`.param` invisible inside `.control`) | thresholds substituted as numbers; a `None` result raises rather than writing a blank |
| DFF failing to capture at aggressive separations, aborting the bisection | the search treats "no capture" as a failed point, which is the correct answer, and the reference run is validated first |
| ~400 ngspice runs is slow | each run measures both edges at once; the grid is 4×4 rather than a fine sweep |
