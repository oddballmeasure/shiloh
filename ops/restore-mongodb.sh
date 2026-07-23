#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--confirm" || -z "${2:-}" ]]; then
  echo "Usage: $0 --confirm <backup-file-name>" >&2
  exit 1
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-${project_dir}/.env.production}"
backup_file="$2"

set -a
source "${env_file}"
set +a

: "${MONGO_URL:?MONGO_URL is required}"
: "${BACKUP_AGE_IDENTITY_FILE:?BACKUP_AGE_IDENTITY_FILE is required}"
: "${BACKUP_RCLONE_REMOTE:?BACKUP_RCLONE_REMOTE is required}"
: "${BACKUP_DOCKER_NETWORK:?BACKUP_DOCKER_NETWORK is required}"

[[ -f "${BACKUP_AGE_IDENTITY_FILE}" ]] || { echo "Missing age identity file." >&2; exit 1; }

rclone cat "${BACKUP_RCLONE_REMOTE}/${backup_file}" \
  | age -d -i "${BACKUP_AGE_IDENTITY_FILE}" \
  | docker run --rm -i \
      --network "${BACKUP_DOCKER_NETWORK}" \
      -e MONGO_URL \
      "${MONGODB_TOOLS_IMAGE:-mongodb/mongodb-database-tools:100.11.0}" \
      sh -ec 'mongorestore --uri="$MONGO_URL" --archive --gzip --drop'
