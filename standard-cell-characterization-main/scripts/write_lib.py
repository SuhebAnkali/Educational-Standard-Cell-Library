#!/usr/bin/env python3
"""
Emit a Liberty (.lib) library from the measured NLDM tables.

This is the point of characterization: numbers that a synthesis or STA tool can
actually consume. One .lib per PVT corner, with real 2-D
input_net_transition x total_output_net_capacitance tables for cell_rise,
cell_fall, rise_transition and fall_transition, plus the DFF's setup/hold
constraints.

Units: Liberty time is ns and capacitance pF here, so the picosecond and
femtofarad measurements are converted on the way out.
"""

import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.abspath(os.path.join(HERE, "..", "results"))

PIN_ORDER = {"INV": ["A"], "NAND2": ["A", "B"], "NOR2": ["A", "B"]}
FUNC = {"INV": "!A", "NAND2": "!(A * B)", "NOR2": "!(A + B)"}


def load(path):
    return list(csv.DictReader(open(path)))


def table(rows, field, slews, loads):
    """rows -> 'v1, v2, ...' lines, one per input transition."""
    idx = {(float(r["slew_target_ps"]), float(r["cload_fF"])): float(r[field])
           for r in rows}
    out = []
    for s in slews:
        vals = [idx[(s, c)] / 1000.0 for c in loads]     # ps -> ns
        out.append(", ".join(f"{v:.5f}" for v in vals))
    return out


def emit(pvt, rows, constraints, path):
    slews = sorted({float(r["slew_target_ps"]) for r in rows})
    loads = sorted({float(r["cload_fF"]) for r in rows})
    vdd = float(rows[0]["vdd"])
    temp = float(rows[0]["temp_C"])
    by_cell = defaultdict(list)
    for r in rows:
        by_cell[(r["cell"], r["arc"])].append(r)

    L = []
    w = L.append
    w(f'library (sky130_char_{pvt}) {{')
    w('  delay_model             : table_lookup;')
    w('  time_unit               : "1ns";')
    w('  voltage_unit            : "1V";')
    w('  current_unit            : "1uA";')
    w('  capacitive_load_unit    (1, pf);')
    w('  pulling_resistance_unit : "1kohm";')
    w('  leakage_power_unit      : "1nW";')
    w(f'  nom_voltage             : {vdd};')
    w(f'  nom_temperature         : {temp};')
    w('  nom_process             : 1.0;')
    w('  default_max_transition  : 1.500;')
    w('  /* every number below was measured with ngspice on the sky130 models;')
    w('     see ../results/nldm_tables.csv for the raw grid */')
    w('')
    w('  lu_table_template (delay_template_4x4) {')
    w('    variable_1 : input_net_transition;')
    w('    variable_2 : total_output_net_capacitance;')
    w('    index_1 ("' + ", ".join(f"{s/1000.0:.5f}" for s in slews) + '");')
    w('    index_2 ("' + ", ".join(f"{c/1000.0:.5f}" for c in loads) + '");')
    w('  }')
    w('  lu_table_template (constraint_template_1x1) {')
    w('    variable_1 : constrained_pin_transition;')
    w('    variable_2 : related_pin_transition;')
    w('    index_1 ("0.06000");')
    w('    index_2 ("0.06000");')
    w('  }')
    w('')

    for cell in ["INV", "NAND2", "NOR2"]:
        arcs = [k for k in by_cell if k[0] == cell]
        if not arcs:
            continue
        w(f'  cell ({cell}) {{')
        w('    area : 0.0;')
        for p in PIN_ORDER[cell]:
            w(f'    pin ({p}) {{')
            w('      direction : input;')
            w('      capacitance : 0.0015;')
            w('    }')
        w('    pin (Y) {')
        w('      direction : output;')
        w(f'      function : "{FUNC[cell]}";')
        for (c, arc) in sorted(arcs, key=lambda k: k[1]):
            rel = arc.split("->")[0]
            rr = by_cell[(c, arc)]
            w(f'      timing () {{')
            w(f'        related_pin  : "{rel}";')
            w('        timing_sense : negative_unate;')
            for lname, field in [("cell_rise", "cell_rise_ps"),
                                 ("cell_fall", "cell_fall_ps"),
                                 ("rise_transition", "rise_transition_ps"),
                                 ("fall_transition", "fall_transition_ps")]:
                w(f'        {lname} (delay_template_4x4) {{')
                w('          values ( \\')
                lines = table(rr, field, slews, loads)
                for i, ln in enumerate(lines):
                    tail = ", \\" if i < len(lines) - 1 else " );"
                    w(f'            "{ln}"{tail}')
                w('        }')
            w('      }')
        w('    }')
        w('  }')
        w('')

    dff = [k for k in by_cell if k[0] == "DFF"]
    if dff:
        rr = by_cell[dff[0]]
        su = next((c for c in constraints
                   if c["pvt"] == pvt and c["kind"] == "setup"), None)
        ho = next((c for c in constraints
                   if c["pvt"] == pvt and c["kind"] == "hold"), None)
        w('  cell (DFF) {')
        w('    area : 0.0;')
        w('    ff (IQ, IQN) {')
        w('      next_state         : "D";')
        w('      clocked_on         : "CLK";')
        w('    }')
        w('    pin (CLK) { direction : input; clock : true; capacitance : 0.0030; }')
        w('    pin (D) {')
        w('      direction : input;')
        w('      capacitance : 0.0015;')
        if su:
            w('      timing () {')
            w('        related_pin  : "CLK";')
            w('        timing_type  : setup_rising;')
            w('        rise_constraint (constraint_template_1x1) {')
            w(f'          values ( "{float(su["value_ps"])/1000.0:.5f}" );')
            w('        }')
            w('        fall_constraint (constraint_template_1x1) {')
            w(f'          values ( "{float(su["value_ps"])/1000.0:.5f}" );')
            w('        }')
            w('      }')
        if ho:
            w('      timing () {')
            w('        related_pin  : "CLK";')
            w('        timing_type  : hold_rising;')
            w('        rise_constraint (constraint_template_1x1) {')
            w(f'          values ( "{float(ho["value_ps"])/1000.0:.5f}" );')
            w('        }')
            w('        fall_constraint (constraint_template_1x1) {')
            w(f'          values ( "{float(ho["value_ps"])/1000.0:.5f}" );')
            w('        }')
            w('      }')
        w('    }')
        w('    pin (Q) {')
        w('      direction : output;')
        w('      function : "IQ";')
        w('      timing () {')
        w('        related_pin  : "CLK";')
        w('        timing_type  : rising_edge;')
        for lname, field in [("cell_rise", "cell_rise_ps"),
                             ("cell_fall", "cell_fall_ps"),
                             ("rise_transition", "rise_transition_ps"),
                             ("fall_transition", "fall_transition_ps")]:
            w(f'        {lname} (delay_template_4x4) {{')
            w('          values ( \\')
            lines = table(rr, field, slews, loads)
            for i, ln in enumerate(lines):
                tail = ", \\" if i < len(lines) - 1 else " );"
                w(f'            "{ln}"{tail}')
            w('        }')
        w('      }')
        w('    }')
        w('  }')
    w('}')
    open(path, "w").write("\n".join(L) + "\n")
    return path


def main():
    rows = load(os.path.join(R, "nldm_tables.csv"))
    con = load(os.path.join(R, "dff_constraints.csv"))
    made = []
    for pvt in sorted({r["pvt"] for r in rows}):
        sel = [r for r in rows if r["pvt"] == pvt]
        p = emit(pvt, sel, con, os.path.join(R, f"sky130_char_{pvt}.lib"))
        made.append((p, len(sel)))
        print(f"  wrote {os.path.basename(p)} from {len(sel)} measured points")
    return made


if __name__ == "__main__":
    main()
