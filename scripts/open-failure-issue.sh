#!/usr/bin/env bash
# Open or update the issue that tracks a failed packaging run.
# An open issue with the same title is updated in place.
#
# Environment:
#   GH_TOKEN or GITHUB_TOKEN, GITHUB_REPOSITORY
#   TAG, RUN_URL, REASON
#   LOG_FILE (optional path to a log excerpt)

set -euo pipefail

repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
tag="${TAG:-}"
run_url="${RUN_URL:-}"
reason="${REASON:-}"
log_file="${LOG_FILE:-}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "${tag//[[:space:]]/}" ]; then
  title="Linux packaging failed"
else
  title="Linux packaging failed for ${tag}"
fi

body_file="$(mktemp)"
trap 'rm -f "$body_file"' EXIT
issue_args=(--tag "$tag" --run-url "$run_url" --reason "$reason")
if [ -n "$log_file" ]; then
  issue_args+=(--log-file "$log_file")
fi
python3 "$script_dir/release_metadata.py" issue-body "${issue_args[@]}" >"$body_file"

existing="$(
  TITLE="$title" gh issue list --repo "$repo" --state open --limit 50 --json number,title \
    | TITLE="$title" python3 -c 'import json, os, sys
title = os.environ["TITLE"]
items = json.load(sys.stdin)
print(next((str(item["number"]) for item in items if item.get("title") == title), ""))'
)"

if [ -z "$existing" ]; then
  gh issue create --repo "$repo" --title "$title" --body-file "$body_file"
else
  gh issue comment --repo "$repo" "$existing" --body "Updated from ${run_url:-a later workflow run}."
  gh issue edit --repo "$repo" "$existing" --body-file "$body_file"
fi
