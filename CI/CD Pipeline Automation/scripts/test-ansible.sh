#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
cleanup() { [[ -d "$work" && "$work" != / ]] && rm -rf -- "$work"; }
trap cleanup EXIT
mkdir -p "$work/bin"
cat > "$work/bin/kubectl" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$ANSIBLE_CALLS"
case "$*" in
  *'create namespace'*) printf 'apiVersion: v1\nkind: Namespace\nmetadata: {name: fixture}\n' ;;
  *'create configmap'*) printf 'apiVersion: v1\nkind: ConfigMap\nmetadata: {name: fixture}\n' ;;
  *'apply -f -'*) cat >/dev/null; printf 'resource unchanged\n' ;;
  *) exit 1 ;;
esac
STUB
chmod +x "$work/bin/kubectl"
export PATH="$work/bin:$PATH" ANSIBLE_CALLS="$work/calls"
export KUBECONFIG="$work/fixture-kubeconfig" KUBECONTEXT=fixture-only
ansible-playbook -i "$root/ansible/inventory/local.ini" "$root/ansible/playbooks/configure-app.yml" \
  -e "{\"deploy_dir\":\"$work/render with spaces\"}"
tr -d '\r' < "$work/render with spaces/app.env" | grep -qx 'RELEASE_COLOR=blue'
tr -d '\r' < "$work/render with spaces/app.env" | grep -qx 'ENVIRONMENT=dev'
grep -q -- '--context fixture-only' "$ANSIBLE_CALLS"
ansible-playbook -i "$root/ansible/inventory/local.ini" "$root/ansible/playbooks/configure-app.yml" \
  -e "{\"deploy_dir\":\"$work/render with spaces\",\"app_environment\":\"staging\",\"release_color\":\"green\",\"build_id\":\"checked\"}"
tr -d '\r' < "$work/render with spaces/app.env" | grep -qx 'RELEASE_COLOR=green'
tr -d '\r' < "$work/render with spaces/app.env" | grep -qx 'BUILD_ID=checked'
tr -d '\r' < "$work/render with spaces/app.env" | grep -qx 'ENVIRONMENT=staging'
echo 'Ansible defaults, overrides, paths and explicit context checks passed'
