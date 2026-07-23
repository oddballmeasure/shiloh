#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${ENV_FILE:-${project_dir}/.env.production}"
[[ -f "${env_file}" ]] || { echo "Missing ${env_file}" >&2; exit 1; }

set -a
# The environment file is host-controlled and must not be writable by untrusted users.
source "${env_file}"
set +a

: "${MONGO_URL:?MONGO_URL is required}"
: "${BACKUP_AGE_RECIPIENT:?BACKUP_AGE_RECIPIENT is required}"
: "${BACKUP_RCLONE_REMOTE:?BACKUP_RCLONE_REMOTE is required}"
: "${BACKUP_DOCKER_NETWORK:?BACKUP_DOCKER_NETWORK is required}"

for command in docker age rclone; do
  command -v "${command}" >/dev/null || { echo "Missing required command: ${command}" >&2; exit 1; }
done

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_name="korean-study-${timestamp}.archive.gz.age"
temporary_file="$(mktemp)"
trap 'rm -f "${temporary_file}"' EXIT

docker run --rm \
  --network "${BACKUP_DOCKER_NETWORK}" \
  -e MONGO_URL \
  "${MONGODB_TOOLS_IMAGE:-mongodb/mongodb-database-tools:100.11.0}" \
  sh -ec 'mongodump --uri="$MONGO_URL" --archive --gzip' \
  | age -r "${BACKUP_AGE_RECIPIENT}" > "${temporary_file}"

rclone copyto "${temporary_file}" "${BACKUP_RCLONE_REMOTE}/${backup_name}"
rclone delete "${BACKUP_RCLONE_REMOTE}" --min-age "${BACKUP_RETENTION_DAYS:-30}d"
echo "Uploaded encrypted backup: ${BACKUP_RCLONE_REMOTE}/${backup_name}"
