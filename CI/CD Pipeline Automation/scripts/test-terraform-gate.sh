#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/project/scripts" "$tmp/project/terraform/environments/local-kind" "$tmp/bin"
cp "$root/scripts/terraform-gate.sh" "$tmp/project/scripts/"
cat > "$tmp/bin/terraform" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CALLS"
case "$2" in
  plan) for arg in "$@"; do [[ "$arg" != -out=* ]] || printf 'saved' > "${arg#-out=}"; done ;;
  show) printf '{"format_version":"1.2","resource_changes":[]}\n' ;;
  apply) [[ "$3" == -input=false && -f "$4" ]] || exit 9 ;;
esac
SH
cat > "$tmp/bin/python" <<'SH'
#!/usr/bin/env bash
[[ "$*" == *'--plan'* ]] || exit 9
exit "${POLICY_RESULT:-0}"
SH
chmod +x "$tmp/bin/"*
export PATH="$tmp/bin:$PATH" CALLS="$tmp/calls"
POLICY_RESULT=1 bash "$tmp/project/scripts/terraform-gate.sh" plan-apply && exit 1
! grep -q ' apply ' "$CALLS"
: > "$CALLS"
POLICY_RESULT=0 bash "$tmp/project/scripts/terraform-gate.sh" plan-apply
grep -q ' apply -input=false .*release.tfplan' "$CALLS"
! grep ' apply ' "$CALLS" | grep -q -- '-var='
TF_ENV='../escape' bash "$tmp/project/scripts/terraform-gate.sh" plan && exit 1
echo "Terraform gate: policy rejection, exact saved plan and path validation PASS"
