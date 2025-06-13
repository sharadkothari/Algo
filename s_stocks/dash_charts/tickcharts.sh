#!/bin/bash

# Activate environment if needed
source ~/Python/Algo/.venv/bin/activate

# Add project root to PYTHONPATH
export PYTHONPATH="$HOME/Python/Algo:$PYTHONPATH"

# Run your module
python "$HOME/Python/Algo/s_stocks/dash_charts/dash_charts.py"