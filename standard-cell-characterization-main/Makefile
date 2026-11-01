# ============================================================================
# standard-cell-characterization
#   make char   run every ngspice measurement (slow: ~400 runs)
#   make lib    build the Liberty files from the measured CSVs
#   make plots  figures
#   make check  validate the generated .lib files structurally
#   make all
# ============================================================================
PDK_ROOT ?= $(HOME)/.volare/sky130A
.PHONY: all char lib plots check clean

all: char lib plots check
	@echo "=== all targets complete; see results/ ==="

char:
	python3 scripts/characterize.py 2>&1 | tee results/char_summary.log

lib:
	python3 scripts/write_lib.py 2>&1 | tee results/lib_summary.log

plots:
	python3 scripts/plot_char.py

check:
	python3 scripts/check_results.py

clean:
	rm -f cells/_run_*.spice
