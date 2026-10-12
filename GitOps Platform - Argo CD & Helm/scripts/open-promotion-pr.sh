#!/usr/bin/env bash
set -euo pipefail
: "${GH_REPO:?Set GH_REPO to owner/repository}"
: "${DEFAULT_BRANCH:?Set DEFAULT_BRANCH}"
: "${PROMOTION_BRANCH:?Set a unique PROMOTION_BRANCH}"
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
repository_root="$(git -C "$project_root" rev-parse --show-toplevel)"
cd -- "$repository_root"

if (( $# < 2 || $# > 3 )); then
  echo "Usage: open-promotion-pr.sh <dev|staging|prod> <image_tag> [canary|blueGreen]" >&2
  exit 1
fi
environment="$1"
tag="$2"
strategy="${3:-}"
case "$environment" in dev|staging|prod) ;; *) echo "Invalid environment" >&2; exit 1;; esac
if [[ ! "$PROMOTION_BRANCH" =~ ^automation/promote-$environment-[0-9]+-[0-9]+$ ]]; then
  echo "Invalid promotion branch" >&2
  exit 1
fi
git check-ref-format --branch "$DEFAULT_BRANCH" >/dev/null
git check-ref-format --branch "$PROMOTION_BRANCH" >/dev/null
if [[ "$PROMOTION_BRANCH" == "$DEFAULT_BRANCH" || "$(git branch --show-current)" != "$DEFAULT_BRANCH" ]]; then
  echo "Promotion must start from the default branch and target a new branch" >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing to include existing workspace changes" >&2
  exit 1
fi
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse "refs/remotes/origin/$DEFAULT_BRANCH")" ]]; then
  echo "Default branch differs from the checked-out origin snapshot" >&2
  exit 1
fi
existing_status=0
git ls-remote --exit-code --heads origin "refs/heads/$PROMOTION_BRANCH" >/dev/null || existing_status=$?
case "$existing_status" in
  0) echo "Promotion branch already exists; inspect it instead of retrying" >&2; exit 1;;
  2) ;;
  *) echo "Cannot verify the remote branch" >&2; exit "$existing_status";;
esac
bash "$project_root/scripts/promote.sh" "$environment" "$tag" "$strategy"
values="GitOps Platform - Argo CD & Helm/charts/platform-service/env/$environment.yaml"
if git diff --quiet -- "$values"; then
  echo "The requested values are already present; no PR needed."
  exit 0
fi
if [[ "$(git diff --name-only)" != "$values" ]]; then
  echo "Unexpected file changed; no commit or push performed" >&2
  exit 1
fi
git switch -c "$PROMOTION_BRANCH"
git add -- "$values"
git -c user.name='github-actions[bot]' -c user.email='github-actions[bot]@users.noreply.github.com' commit -m "promote: $environment -> $tag" -- "$values"
git push --set-upstream origin "$PROMOTION_BRANCH"

body_file="$(mktemp)"
trap 'rm -f -- "$body_file"' EXIT
printf 'Proposes image tag %s for %s.\n\nReview the environment values, approve workflow execution if GitHub requests it, and require Portfolio status to pass before merging. This workflow does not approve or merge the PR.\n' "$tag" "$environment" > "$body_file"
if ! gh pr create --repo "$GH_REPO" --base "$DEFAULT_BRANCH" --head "$PROMOTION_BRANCH" --draft --title "promote: $environment -> $tag" --body-file "$body_file"; then
  echo "Branch was pushed but PR creation failed or is uncertain. Inspect the existing branch/PR; do not rerun blindly." >&2
  exit 1
fi
