#!/bin/bash

# Define full or relative paths to each dashboard HTML file
DASHBOARDS=(
    "http://t5810/static/margin_book/"
    "http://t5810/static/position_book/"
    "http://web.t5810/alerts-tree/"
    "http://t5810/static/mtm_chart/"
)

EDGE_BIN="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

# Loop through and open each in app mode
for url in "${DASHBOARDS[@]}"; do
    "$EDGE_BIN" --new-window --app="$url" &
done

sleep 2

exit 0