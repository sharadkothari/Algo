#!/bin/bash

echo -ne "\033]1;tickchart\007"
echo -ne "\033]2;tickchart\007"

# Activate environment if needed
source ~/Python/Algo/.venv/bin/activate

# Add project root to PYTHONPATH
export PYTHONPATH="$HOME/Python/Algo:$PYTHONPATH"

# Run your module
python "$HOME/Python/Algo/s_stocks/dash_charts/dash_charts.py"