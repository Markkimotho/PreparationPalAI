#!/usr/bin/env bash
# Render the link-preview image (frontend/public/social-preview.png, 1200 x 630) from card.html.
# Uses headless Brave or Chrome, whichever is installed. Re-run after changing the landing design.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
OUT="$ROOT/frontend/public/social-preview.png"
for candidate in "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" "$(command -v chromium || true)"; do
  [ -n "$candidate" ] && [ -x "$candidate" ] && BROWSER="$candidate" && break
done
: "${BROWSER:?install Brave or Chrome to render the preview}"
TMP="$(mktemp -d)"
# A 60-second limit: headless Chromium can hang without a display (e.g. inside some sandboxes).
perl -e 'alarm 60; exec @ARGV' "$BROWSER" --headless=new --disable-gpu --hide-scrollbars --no-first-run --force-device-scale-factor=1 \
  --allow-file-access-from-files --user-data-dir="$TMP/profile" --window-size=1200,630 --screenshot="$TMP/card.png" \
  "file://$HERE/card.html" >"$TMP/log.txt" 2>&1 || true
[ -s "$TMP/card.png" ] || { echo "headless render failed (see README.md for the in-browser fallback)" >&2; exit 1; }
SIZE="$(sips -g pixelWidth -g pixelHeight "$TMP/card.png" | awk '/pixel/ {print $2}' | paste -sd x -)"
[ "$SIZE" = "1200x630" ] || { echo "unexpected size $SIZE" >&2; exit 1; }
mv "$TMP/card.png" "$OUT"
rm -rf "$TMP"
echo "wrote $OUT ($SIZE)"
