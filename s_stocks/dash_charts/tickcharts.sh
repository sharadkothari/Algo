#!/bin/bash

# Activate environment if needed
source ~/Python/Algo/.venv/bin/activate

# Add project root to PYTHONPATH
export PYTHONPATH="/Users/sharadk/Python/Algo:$PYTHONPATH"

# Run your module
python /Users/sharadk/Python/Algo/s_stocks/dash_charts/dash_charts.py