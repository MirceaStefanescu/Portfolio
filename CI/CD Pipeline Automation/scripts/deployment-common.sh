#!/usr/bin/env bash
set -euo pipefail

validate_identity_inputs() {
  local app="$1"
  local ns="$2"
  local load_kind="$3"

  # APP_NAME: lowercase DNS label (RFC 1123 / service-compatible):
  # starts with [a-z], ends with [a-z0-9], contains [a-z0-9-], max length 63
  if [[ ${#app} -gt 63 ]] || [[ ! "$app" =~ ^[a-z]([a-z0-9-]*[a-z0-9])?$ ]]; then
    echo "Invalid APP_NAME: '$app'. Must be a lowercase DNS label (start with letter, alphanumeric/hyphen, max 63 chars)." >&2
    exit 1
  fi

  # NAMESPACE: lowercase DNS label:
  # starts with [a-z0-9], ends with [a-z0-9], contains [a-z0-9-], max length 63, no slash/quote/space
  if [[ ${#ns} -gt 63 ]] || [[ ! "$ns" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; then
    echo "Invalid NAMESPACE: '$ns'. Must be a lowercase DNS label (max 63 chars, no slash/quote/space)." >&2
    exit 1
  fi

  # LOAD_KIND_IMAGE: literal true or false
  case "$load_kind" in
    true|false) ;;
    *)
      echo "Invalid LOAD_KIND_IMAGE: '$load_kind'. Expected 'true' or 'false'." >&2
      exit 1
      ;;
  esac
}

render_namespace() {
  local manifest="$1"
  local ns="$2"

  local patch="[{\"op\":\"replace\",\"path\":\"/metadata/name\",\"value\":\"${ns}\"}]"
  kubectl patch --local -f "$manifest" --type=json -p "$patch" -o json
}

render_configmap() {
  local manifest="$1"
  local app="$2"
  local ns="$3"

  local cm_name="${app}-env"
  local patch="[{\"op\":\"replace\",\"path\":\"/metadata/name\",\"value\":\"${cm_name}\"},{\"op\":\"replace\",\"path\":\"/metadata/namespace\",\"value\":\"${ns}\"}]"
  kubectl patch --local -f "$manifest" --type=json -p "$patch" -o json
}

render_deployment() {
  local manifest="$1"
  local app="$2"
  local ns="$3"
  local variant="$4"
  local img="$5"

  local deploy_name="${app}-${variant}"
  local cm_name="${app}-env"

  local patch="[{\"op\":\"replace\",\"path\":\"/metadata/name\",\"value\":\"${deploy_name}\"},{\"op\":\"replace\",\"path\":\"/metadata/namespace\",\"value\":\"${ns}\"},{\"op\":\"replace\",\"path\":\"/metadata/labels/app\",\"value\":\"${app}\"},{\"op\":\"replace\",\"path\":\"/spec/selector/matchLabels/app\",\"value\":\"${app}\"},{\"op\":\"replace\",\"path\":\"/spec/template/metadata/labels/app\",\"value\":\"${app}\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/envFrom/0/configMapRef/name\",\"value\":\"${cm_name}\"}]"

  local rendered
  rendered="$(kubectl patch --local -f "$manifest" --type=json -p "$patch" -o json)" || return $?

  if [[ -n "$img" ]]; then
    rendered="$(kubectl set image --local -f - app="${img}" -o json <<< "$rendered")" || return $?
  fi

  printf '%s' "$rendered"
}

render_service() {
  local manifest="$1"
  local app="$2"
  local ns="$3"
  local selector_key="$4"
  local selector_val="$5"

  local patch="[{\"op\":\"replace\",\"path\":\"/metadata/name\",\"value\":\"${app}\"},{\"op\":\"replace\",\"path\":\"/metadata/namespace\",\"value\":\"${ns}\"},{\"op\":\"replace\",\"path\":\"/spec/selector\",\"value\":{\"app\":\"${app}\",\"${selector_key}\":\"${selector_val}\"}}]"
  kubectl patch --local -f "$manifest" --type=json -p "$patch" -o json
}
