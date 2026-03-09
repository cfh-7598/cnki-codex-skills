#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-$HOME/.codex/skills}"

mkdir -p "$DEST"

rm -rf "$DEST/_shared"
cp -R "$ROOT/_shared" "$DEST/_shared"

for dir in "$ROOT"/cnki*-codex; do
  name="$(basename "$dir")"
  rm -rf "$DEST/$name"
  cp -R "$dir" "$DEST/$name"
done

python -m pip install -r "$ROOT/requirements.txt"

echo "Installed CNKI Codex skills into $DEST"
echo "Available skills:"
find "$DEST" -maxdepth 1 -type d \( -name 'cnki*-codex' -o -name '_shared' \) | sort
