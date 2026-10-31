#!/usr/bin/env bash
# Overlay this repo's Linux packaging onto a git checkout of
# NousResearch/hermes-agent. Patches apply with `git apply --3way` and the
# script exits on the first patch that does not apply. New Flatpak, Snap, and
# helper files are copied in only after every patch applies.
#
# Usage: scripts/apply-packaging.sh /path/to/hermes-agent

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -ne 1 ]; then
  echo "usage: $0 /path/to/hermes-agent" >&2
  exit 1
fi
target="$(cd "$1" && pwd)"

if [ "$target" = "$root" ]; then
  echo "refusing to apply packaging onto the packaging repository itself" >&2
  exit 1
fi
if ! git -C "$target" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "not a git checkout: $target" >&2
  exit 1
fi

shopt -s nullglob
patches=("$root"/patches/*.patch)
shopt -u nullglob
if [ "${#patches[@]}" -eq 0 ]; then
  echo "no patches found in $root/patches" >&2
  exit 1
fi

for patch in "${patches[@]}"; do
  echo "Applying $(basename "$patch") with git apply --3way"
  git -C "$target" apply --3way --verbose "$patch"
done

cp -a "$root/packaging/." "$target/"
echo "Packaging overlay applied to $target"
