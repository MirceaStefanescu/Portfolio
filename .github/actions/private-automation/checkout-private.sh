#!/usr/bin/env bash
# Public authentication adapter only; private Git output must never reach run logs.
set +x
set -euo pipefail
umask 077

auth_dir=''
checkout_dir=''

cleanup() {
  local result=$?
  local cleanup_failed=0
  trap - EXIT HUP INT TERM
  unset PORTFOLIO_AUTOMATION_SSH_KEY GIT_SSH_COMMAND
  if [[ -n "$auth_dir" ]]; then
    rm -rf -- "$auth_dir" >/dev/null 2>&1 || cleanup_failed=1
  fi
  if [[ -n "$checkout_dir" ]]; then
    rm -rf -- "$checkout_dir" >/dev/null 2>&1 || cleanup_failed=1
  fi
  if (( cleanup_failed )); then
    printf '%s\n' 'Private automation temporary-file cleanup failed.' >&2
    result=1
  fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

[[ "${GITHUB_REPOSITORY:-}" == 'MirceaStefanescu/Portfolio' ]] || fail 'Unexpected public repository for private automation.'
[[ "${GITHUB_ACTOR:-}" == 'MirceaStefanescu' || "${GITHUB_ACTOR:-}" == 'dependabot[bot]' ]] || fail 'Private automation source access was not approved.'
[[ "${AUTOMATION_REVISION:-}" =~ ^[0-9a-f]{40}$ ]] || fail 'Private automation requires a verified full commit SHA.'
[[ -n "${PORTFOLIO_AUTOMATION_SSH_KEY:-}" ]] || fail 'The read-only private automation deploy key is unavailable.'
[[ -d "${GITHUB_WORKSPACE:-}" && -d "${RUNNER_TEMP:-}" ]] || fail 'The hosted-runner workspace is unavailable.'
destination="$GITHUB_WORKSPACE/.private-automation"
[[ ! -e "$destination" && ! -L "$destination" ]] || fail 'Private checkout requires an absent .private-automation destination; existing data was preserved.'

# Do not inherit tracing, credential helpers, SSH agents or Git directory overrides.
for variable in "${!GIT_@}" "${!SSH_@}"; do
  if [[ -n "$variable" ]]; then
    unset "$variable"
  fi
done
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_COUNT=0 GIT_TERMINAL_PROMPT=0 GIT_SSH_VARIANT=ssh

auth_dir="$(mktemp -d "$RUNNER_TEMP/portfolio-private-auth.XXXXXX" 2>/dev/null)" || fail 'Could not prepare temporary private authentication.'
checkout_dir="$(mktemp -d "$GITHUB_WORKSPACE/.private-automation-checkout.XXXXXX" 2>/dev/null)" || fail 'Could not prepare the private checkout destination.'
printf '%s\n' "$PORTFOLIO_AUTOMATION_SSH_KEY" > "$auth_dir/key"
unset PORTFOLIO_AUTOMATION_SSH_KEY

# Fixed GitHub Ed25519 host key, independently documented by GitHub:
# https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
# SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU
printf '%s\n' 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' > "$auth_dir/known_hosts"
printf -v GIT_SSH_COMMAND '%q ' ssh -F /dev/null -i "$auth_dir/key" \
  -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$auth_dir/known_hosts" \
  -o GlobalKnownHostsFile=/dev/null -o HostKeyAlgorithms=ssh-ed25519 \
  -o UpdateHostKeys=no -o CheckHostIP=no -o IdentitiesOnly=yes -o IdentityAgent=none \
  -o BatchMode=yes -o ForwardAgent=no -o ClearAllForwardings=yes \
  -o LogLevel=ERROR -o ConnectTimeout=20 -o ConnectionAttempts=2
export GIT_SSH_COMMAND

quiet_git() {
  git -c advice.detachedHead=false -c core.hooksPath=/dev/null "$@" >/dev/null 2>&1
}
quiet_git init --quiet --template= "$checkout_dir" || fail 'Could not initialize the private checkout.'
quiet_git -C "$checkout_dir" remote add origin git@github.com:MirceaStefanescu/Portfolio-Automation.git || fail 'Could not configure the private repository identity.'
quiet_git -C "$checkout_dir" fetch --quiet --no-tags --depth=1 origin "$AUTOMATION_REVISION" || fail 'Could not fetch the pinned private revision; verify read-only deploy-key access.'

# Authentication is no longer needed once the immutable objects are present.
unset GIT_SSH_COMMAND
rm -rf -- "$auth_dir" >/dev/null 2>&1 || fail 'Could not remove temporary private authentication.'
auth_dir=''
quiet_git -C "$checkout_dir" cat-file -e "$AUTOMATION_REVISION^{commit}" || fail 'The private revision is not a commit.'
quiet_git -C "$checkout_dir" checkout --quiet --detach --no-overwrite-ignore "$AUTOMATION_REVISION" || fail 'Could not materialize the pinned private revision.'
actual_revision="$(git -C "$checkout_dir" rev-parse --verify HEAD 2>/dev/null)" || fail 'Could not verify the private checkout identity.'
[[ "$actual_revision" == "$AUTOMATION_REVISION" ]] || fail 'The private checkout did not match its approved revision.'
[[ ! -e "$destination" && ! -L "$destination" ]] || fail 'Private checkout destination appeared during preparation; existing data was preserved.'
mv -T --no-clobber -- "$checkout_dir" "$destination" >/dev/null 2>&1 || fail 'Could not install the verified private checkout.'
[[ ! -e "$checkout_dir" && -d "$destination" && ! -L "$destination" ]] || fail 'Private checkout destination was occupied; existing data was preserved.'
checkout_dir=''
printf '%s\n' 'Pinned private automation checkout verified; temporary credentials removed.'
