#!/usr/bin/env bash
set -euo pipefail

portfolio_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

projects=(
"Automated Infrastructure & Deployment Platform|Automated Infrastructure & Deployment Platform|make dev|Portal: http://localhost:8080"
"Cloud-Native E-Commerce Platform|Cloud-Native E-Commerce Platform|make dev|Product service: http://localhost:8010"
"DevSecOps Pipeline with SBOM & SLSA|DevSecOps Pipeline with SBOM & SLSA|make dev|Optional: cp .env.example .env"
"Event-Driven E-Commerce Platform|Event-Driven E-Commerce Platform|make dev|Order API: http://localhost:18081"
"Full Stack E-commerce Application with Angular and Spring Boot|Full Stack E-commerce Application with Angular and Spring Boot|docker compose up --build|Frontend: http://localhost:4200"
"Habit Tracker & Routine Coach SaaS|Habit Tracker & Routine Coach SaaS|make dev|Frontend: http://localhost:5173"
"GitOps Platform - Argo CD & Helm|GitOps Platform - Argo CD & Helm|make dev|Requires kind, kubectl, helm"
"Kubernetes FinOps & Cost Optimization|Kubernetes FinOps & Cost Optimization|make dev|Optional: cp .env.example .env"
"Observability - New Relic & Prometheus|Observability - New Relic & Prometheus|make dev|Optional: cp .env.example .env"
"Predictive Analytics Pipeline on Kubernetes|Predictive Analytics Pipeline on Kubernetes|make dev|API: http://localhost:8082"
"Real-Time Chat & Collaboration Platform|Real-Time Chat & Collaboration Platform|make dev|Frontend: http://localhost:4201"
"Secure RAG Service & Knowledge API|Secure RAG Service & Knowledge API|make dev|Optional: make demo"
"Prompt Quality & Safety|Prompt Quality & Safety|make dev|Runs quick prompt safety evals"
"Secure Secrets Management & Observability Toolkit|Secure Secrets Management & Observability Toolkit|make dev|Vault: http://localhost:8200"
"CI/CD Pipeline Automation|CI/CD Pipeline Automation|make dev|Path: CI/CD Pipeline Automation"
"LLMOps Evaluation Harness|LLMOps Evaluation Harness|make dev|Optional: cp .env.example .env"
)

names=()
paths=()
commands=()
notes=()

while IFS='|' read -r name path cmd note; do
  names+=("$name")
  paths+=("$path")
  commands+=("$cmd")
  notes+=("$note")
done < <(printf '%s\n' "${projects[@]}")

print_help() {
  cat <<'HELP'
Usage: ./portfolio-launcher.sh [--list] [--show <name|index>] [--run <name|index>] [--presets] [--preset <name>]

Options:
  --list              List projects
  --show <name|index> Show run command and notes
  --run <name|index>  Run the project command (with confirmation)
  --presets           List available stack presets
  --preset <name>     Show projects and run commands for a preset
HELP
}

list_projects() {
  for i in "${!names[@]}"; do
    printf '%2d) %s\n' "$((i + 1))" "${names[$i]}"
  done
}

preset_names() {
  cat <<'PRESETS'
fullstack  - Cloud and UI-heavy apps
data       - Streaming analytics and pipelines
devops     - Delivery, GitOps, infra automation
security   - Security-first systems and tooling
PRESETS
}

preset_indexes() {
  case "$1" in
    fullstack) echo "2 4 5 6 11" ;;
    data) echo "10" ;;
    devops) echo "1 7 8 9 14" ;;
    security) echo "3 12 13" ;;
    *) return 1 ;;
  esac
}

show_preset() {
  local preset="$1"
  local idxs
  if ! idxs=$(preset_indexes "$preset"); then
    printf 'Unknown preset: %s\n' "$preset" >&2
    exit 1
  fi

  printf 'Preset: %s\n' "$preset"
  for idx in $idxs; do
    local zero_index=$((idx - 1))
    printf '%2d) %s\n' "$idx" "${names[$zero_index]}"
    printf '    Run: %s\n' "${commands[$zero_index]}"
  done
}

resolve_index() {
  local input="$1"
  if [[ "$input" =~ ^0*([1-9][0-9]*)$ ]]; then
    local number="${BASH_REMATCH[1]}"
    for i in "${!names[@]}"; do
      if [[ "$number" == "$((i + 1))" ]]; then
        printf '%s' "$i"
        return 0
      fi
    done
    return 1
  fi

  local input_lc="${input,,}"
  for i in "${!names[@]}"; do
    if [[ "${names[$i],,}" == "$input_lc" ]]; then
      printf '%s' "$i"
      return 0
    fi
  done

  return 1
}

show_project() {
  local idx="$1"
  printf 'Project: %s\n' "${names[$idx]}"
  printf 'Path: %s\n' "$portfolio_root/${paths[$idx]}"
  printf 'Run: %s\n' "${commands[$idx]}"
  printf 'Notes: %s\n' "${notes[$idx]}"
}

run_project() {
  local idx="$1"
  local dir="$portfolio_root/${paths[$idx]}"
  local cmd="${commands[$idx]}"

  if [[ ! -d "$dir" ]]; then
    printf 'Missing directory: %s\n' "$dir" >&2
    return 1
  fi

  show_project "$idx"
  read -r -p "Run this command now? [y/N] " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    (cd "$dir" && bash -lc "$cmd")
  fi
}

if (( $# == 0 )); then
  echo "Portfolio launcher"
  list_projects
  echo
  read -r -p "Choose a project number to show details (or press Enter to exit): " choice
  if [[ -z "$choice" ]]; then
    exit 0
  fi
  if idx=$(resolve_index "$choice"); then
    show_project "$idx"
  else
    printf 'Unknown selection: %s\n' "$choice" >&2
    exit 1
  fi
  exit 0
fi

case "${1:-}" in
  --help|-h)
    print_help
    ;;
  --list)
    list_projects
    ;;
  --show)
    if [[ -z "${2:-}" ]]; then
      printf 'Missing project name or index for --show\n' >&2
      exit 1
    fi
    if idx=$(resolve_index "$2"); then
      show_project "$idx"
    else
      printf 'Unknown project: %s\n' "$2" >&2
      exit 1
    fi
    ;;
  --run)
    if [[ -z "${2:-}" ]]; then
      printf 'Missing project name or index for --run\n' >&2
      exit 1
    fi
    if idx=$(resolve_index "$2"); then
      run_project "$idx"
    else
      printf 'Unknown project: %s\n' "$2" >&2
      exit 1
    fi
    ;;
  --presets)
    preset_names
    ;;
  --preset)
    if [[ -z "${2:-}" ]]; then
      printf 'Missing preset name for --preset\n' >&2
      exit 1
    fi
    show_preset "$2"
    ;;
  *)
    print_help
    exit 1
    ;;
esac
