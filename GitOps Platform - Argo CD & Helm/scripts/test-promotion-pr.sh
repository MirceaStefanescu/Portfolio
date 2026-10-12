#!/usr/bin/env bash
set -euo pipefail
source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
test_parent="$(cd -- "${TMPDIR:-/tmp}" && pwd -P)"
test_root="$(mktemp -d "$test_parent/portfolio-promotion.XXXXXXXX")"
cleanup() {
  case "$test_root" in "$test_parent"/portfolio-promotion.*) rm -rf -- "$test_root";; *) exit 1;; esac
}
trap cleanup EXIT
mkdir -p "$test_root/bin" "$test_root/work/GitOps Platform - Argo CD & Helm/scripts"
project="$test_root/work/GitOps Platform - Argo CD & Helm"
mkdir -p "$project/charts/platform-service/env"
cp "$source_root/scripts/promote.sh" "$source_root/scripts/open-promotion-pr.sh" "$project/scripts/"
printf 'environment: dev\nimage:\n  tag: "old"\nrollout:\n  strategy: canary\n' > "$project/charts/platform-service/env/dev.yaml"
cat > "$test_root/bin/gh" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" >> "$GH_LOG"
if [[ "${GH_FAIL:-0}" == 1 ]]; then exit 1; fi
printf 'https://example.invalid/pull/1\n'
MOCK
chmod +x "$test_root/bin/gh"
export PATH="$test_root/bin:$PATH"
export GH_LOG="$test_root/gh.log" GH_REPO='test/portfolio' DEFAULT_BRANCH=main PROMOTION_BRANCH=automation/promote-dev-1-1
git init --bare --initial-branch=main "$test_root/remote.git" >/dev/null
git -C "$test_root/work" init --initial-branch=main >/dev/null
git -C "$test_root/work" config core.autocrlf false
git -C "$test_root/work" add .
git -C "$test_root/work" -c user.name=Test -c user.email=test@example.invalid commit -qm baseline
git -C "$test_root/work" remote add origin "$test_root/remote.git"
git -C "$test_root/work" push -q --set-upstream origin main
baseline="$(git -C "$test_root/work" rev-parse HEAD)"
invoke() { bash "$project/scripts/open-promotion-pr.sh" "$@" > "$test_root/output" 2>&1; }
reject() {
  if invoke "$@"; then echo "Unexpected promotion success" >&2; exit 1; fi
  [[ "$(git --git-dir="$test_root/remote.git" rev-parse main)" == "$baseline" ]]
}
# No-op must create neither branch nor PR.
invoke dev old
[[ ! -e "$GH_LOG" ]]
[[ "$(git --git-dir="$test_root/remote.git" for-each-ref --format='%(refname)' refs/heads)" == refs/heads/main ]]
# Bad input and preexisting local changes must not be published.
reject dev 'bad; command'
[[ -z "$(git -C "$test_root/work" status --porcelain)" ]]
printf 'private local material\n' > "$test_root/work/unrelated.txt"
reject dev new
rm -- "$test_root/work/unrelated.txt"
git -C "$test_root/work" switch -qc unrelated
reject dev new
git -C "$test_root/work" switch -q main
# Real Git push to a local bare remote; only GitHub PR creation is mocked.
invoke dev v2 blueGreen
[[ "$(git --git-dir="$test_root/remote.git" rev-parse main)" == "$baseline" ]]
changed="$(git --git-dir="$test_root/remote.git" diff --name-only main "$PROMOTION_BRANCH")"
[[ "$changed" == 'GitOps Platform - Argo CD & Helm/charts/platform-service/env/dev.yaml' ]]
git --git-dir="$test_root/remote.git" show "$PROMOTION_BRANCH:$changed" | grep -qx '  tag: "v2"'
grep -qx -- '--draft' "$GH_LOG"
grep -qx -- 'test/portfolio' "$GH_LOG"
grep -qx -- "$PROMOTION_BRANCH" "$GH_LOG"
[[ "$(grep -c '^create$' "$GH_LOG")" == 1 ]]
# Existing remote branches are never silently overwritten or retried.
git -C "$test_root/work" switch -q main
reject dev v3
[[ "$(grep -c '^create$' "$GH_LOG")" == 1 ]]
# A failed PR request preserves the pushed branch and never pushes main.
export PROMOTION_BRANCH=automation/promote-dev-2-1 GH_FAIL=1
reject dev v3
git --git-dir="$test_root/remote.git" show-ref --verify "refs/heads/$PROMOTION_BRANCH" >/dev/null
grep -q 'Branch was pushed but PR creation failed or is uncertain' "$test_root/output"
[[ "$(grep -c '^create$' "$GH_LOG")" == 2 ]]
git -C "$test_root/work" switch -q main
reject dev v4
[[ "$(grep -c '^create$' "$GH_LOG")" == 2 ]]
echo "Promotion PR regression checks passed"
