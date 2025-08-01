#!/bin/bash

# Rename the tab
echo -ne "\033]1;btoken\007"
echo -ne "\033]2;btoken\007"

# Activate environment
source ~/Python/Algo/.venv/bin/activate

# Add project root to PYTHONPATH
export PYTHONPATH="$HOME/Python/Algo:$PYTHONPATH"

# Run your module
python "$HOME/Python/Algo/s_brokers/browser_token/browser_token.py"