#!/bin/bash

EDGE_BIN="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

# Define URLs and corresponding profiles
URLS=(
  "https://kite.zerodha.com/"
  "https://kite.zerodha.com/"
  "https://kite.zerodha.com/"
  "https://trade.shoonya.com/#/"
  "https://trade.shoonya.com/#/"
  "https://neo.kotaksecurities.com/"
  "https://neo.kotaksecurities.com/"
)

PROFILES=(
  'profile 5'
  'profile 4'
  'profile 2'
  'profile 5'
  'profile 4'
  'profile 5'
  'profile 4'
)

# Loop through and open each URL in a separate profile
for i in "${!URLS[@]}"; do
  "$EDGE_BIN" --new-window --profile-directory="${PROFILES[$i]}" --app="${URLS[$i]}" &
  sleep 1
done

sleep 2
exit 0