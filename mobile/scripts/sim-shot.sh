#!/usr/bin/env bash
# Open a deep link in the booted iOS simulator and save a screenshot once the screen settles.
#   scripts/sim-shot.sh <path-after-scheme> <out.png> [settle-seconds]
#   scripts/sim-shot.sh "sign-in?slide=2" /tmp/shots/slide3.png
# Works with the development build (Metro running) or a release build; needs no tapping.
set -euo pipefail
path="$1"; out="$2"; settle="${3:-2.5}"
xcrun simctl openurl booted "tayarishe://${path}"
sleep "$settle"
mkdir -p "$(dirname "$out")"
xcrun simctl io booted screenshot "$out" >/dev/null 2>&1
sips -Z 900 "$out" >/dev/null
echo "$out"
