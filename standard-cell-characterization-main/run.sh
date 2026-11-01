#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v ngspice >/dev/null || { echo "MISSING: ngspice"; exit 1; }
PDK_ROOT="${PDK_ROOT:-$HOME/.volare/sky130A}"
[ -d "$PDK_ROOT" ] || { echo "MISSING sky130A PDK at $PDK_ROOT"
                        echo "  pip install volare && volare enable --pdk sky130 c6d73a35f524070e85faff4a6a9eef49553ebc2b"; exit 1; }
ln -sfn "$PDK_ROOT" cells/pdk
VENV="${VENV:-$PWD/.venv}"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"; "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r requirements.txt
fi
export PATH="$VENV/bin:$PATH"
mkdir -p results
make char
make lib
make plots
make check
echo; echo "=== summary ==="
cat results/check_summary.txt
