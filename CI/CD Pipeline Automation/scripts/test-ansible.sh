#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
exec "${ANSIBLE_TEST_PYTHON:-python3}" "$root/tests/integration/ansible-playbook.py" "$@"
