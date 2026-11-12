#!/bin/sh
# Render each option to docs/design/theme-options/option-X.png with headless Chrome (1440x900, 1x).
HERE="$(cd "$(dirname "$0")/.." && (pwd -W 2>/dev/null || pwd))"
CHROME="${CHROME:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
for k in a b c; do
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --window-size=1440,900 --screenshot="$HERE/option-$k.png" "file:///$HERE/option-$k/index.html" 2>/dev/null
done
