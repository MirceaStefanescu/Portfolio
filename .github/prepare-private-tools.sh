#!/usr/bin/env bash
# Authenticated entry point only; implementation stays in the private repository.
set -euo pipefail

public_root="$(git -C "$(dirname -- "${BASH_SOURCE[0]}")/.." rev-parse --show-toplevel)"
revision="$(python3 - "$public_root" <<'PY'
import json
import re
import subprocess
import sys

root = sys.argv[1]
committed = subprocess.check_output(['git', '-C', root, 'show', 'HEAD:.github/private-automation.json'])
config = json.loads(committed)
if config.get('repository') != 'MirceaStefanescu/Portfolio-Automation':
    raise SystemExit('Unexpected private automation repository')
revision = config.get('revision', '')
if not re.fullmatch(r'[0-9a-fA-F]{40}', revision):
    raise SystemExit('Private automation revision must be a complete reviewed commit SHA')
print(revision.lower())
PY
)"
private_root="$public_root/.private-automation"
private_origin='git@github.com:MirceaStefanescu/Portfolio-Automation.git'
if [[ -L "$private_root" ]]; then
  echo 'Refusing to use a linked private checkout.' >&2
  exit 1
fi
if [[ ! -e "$private_root" ]]; then
  git init --quiet "$private_root"
  git -C "$private_root" remote add origin "$private_origin"
fi
[[ "$(git -C "$private_root" rev-parse --show-toplevel)" == "$private_root" ]] || { echo 'Invalid private checkout root.' >&2; exit 1; }
[[ "$(git -C "$private_root" remote get-url origin)" == "$private_origin" ]] || { echo 'Unexpected private checkout origin.' >&2; exit 1; }
[[ -z "$(git -C "$private_root" status --porcelain)" ]] || { echo 'Preserve private checkout edits before refreshing.' >&2; exit 1; }
git -C "$private_root" fetch --quiet --depth=1 origin "$revision"
git -C "$private_root" checkout --quiet --detach "$revision"
python3 "$private_root/scripts/prepare-public-workspace.py" \
  --public-root "$public_root" --private-root "$private_root" \
  --revision "$revision" --source-sha "$(git -C "$public_root" rev-parse HEAD)"
