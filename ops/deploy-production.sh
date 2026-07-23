#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-${project_dir}/.env.production}"
compose=(docker compose --env-file "${env_file}" -f "${project_dir}/docker-compose.prod.yml")

[[ -f "${env_file}" ]] || { echo "Missing ${env_file}" >&2; exit 1; }
[[ "$(stat -c '%a' "${env_file}" 2>/dev/null || stat -f '%Lp' "${env_file}")" =~ ^(400|600)$ ]] || {
  echo "${env_file} must be readable only by its owner (chmod 600)." >&2
  exit 1
}

"${compose[@]}" config -q
"${compose[@]}" up -d --build --remove-orphans
"${compose[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready').read()"
"${compose[@]}" ps
