#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-}"
IMAGE_TAG="${2:-}"
STRATEGY="${3:-}"

if (( $# < 2 || $# > 3 )); then
  echo "Usage: promote.sh <dev|staging|prod> <image_tag> [canary|blueGreen]" >&2
  exit 1
fi
case "$ENVIRONMENT" in
  dev|staging|prod) ;;
  *) echo "Unknown environment: $ENVIRONMENT" >&2; exit 1 ;;
esac
if [[ ! "$IMAGE_TAG" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}$ ]]; then
  echo "Invalid image tag" >&2
  exit 1
fi
case "$STRATEGY" in
  ""|canary|blueGreen) ;;
  *) echo "Unknown rollout strategy: $STRATEGY" >&2; exit 1 ;;
esac

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
VALUES_FILE="$project_root/charts/platform-service/env/${ENVIRONMENT}.yaml"
if [[ ! -f "$VALUES_FILE" ]]; then
  echo "Missing environment values: $ENVIRONMENT" >&2
  exit 1
fi

# Keep user values outside the Perl program and validate before replacing the file.
export IMAGE_TAG STRATEGY
perl -0777 -i -pe '
  my $tags = () = /^[ \t]*tag:.*$/mg;
  my $strategies = () = /^[ \t]*strategy:.*$/mg;
  die "Expected exactly one image tag\n" unless $tags == 1;
  die "Expected exactly one rollout strategy\n" if length($ENV{STRATEGY}) && $strategies != 1;
  s/^([ \t]*tag:).*$/$1 "$ENV{IMAGE_TAG}"/m;
  s/^([ \t]*strategy:).*$/$1 $ENV{STRATEGY}/m if length($ENV{STRATEGY});
' "$VALUES_FILE"

printf "Updated %s with tag %s" "$ENVIRONMENT" "$IMAGE_TAG"
if [[ -n "$STRATEGY" ]]; then
  printf " and strategy %s" "$STRATEGY"
fi
printf "\n"
