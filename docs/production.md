# Production Deployment

Deploy this application to `/opt/korean-study` on an Ubuntu/Debian-class VPS with Docker Engine, Docker Compose v2, `age`, and `rclone` installed. Use a non-root SSH deploy user; the root account is needed only to install the backup timer and protect backup credentials.

## First deployment

1. Point the production domain's `A` and optional `AAAA` records at the VPS.
2. Permit only SSH, HTTP, and HTTPS in the host firewall. Do not publish MongoDB or FastAPI ports.
3. Copy `.env.production.example` to `.env.production`, fill every value, and run `chmod 600 .env.production`.
4. Configure Discord with `https://<DOMAIN>/api/auth/callback/discord` as its redirect URI.
5. Run `./ops/deploy-production.sh`. Caddy obtains and renews the TLS certificate automatically once DNS resolves.
6. Verify `https://<DOMAIN>`, Discord sign-in, an AI assignment, a PDF upload, and `docker compose --env-file .env.production -f docker-compose.prod.yml ps`.
7. Sign in with the first administrator, then run `docker compose --env-file .env.production -f docker-compose.prod.yml exec backend shiloh-admin grant-super-admin --discord-id <discord-id>`.

## Backups and restores

Configure an encrypted `rclone` remote and an `age` key pair. Put only the public `BACKUP_AGE_RECIPIENT` in `.env.production`; keep the private identity file readable by root only. The backup script encrypts a compressed MongoDB archive before uploading it, then deletes remote backups older than `BACKUP_RETENTION_DAYS`.

Install the daily backup timer after deploying to `/opt/korean-study`:

```bash
sudo cp ops/systemd/korean-study-backup.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now korean-study-backup.timer
sudo systemctl list-timers korean-study-backup.timer
```

Test restore quarterly in an isolated Docker project, never against the live stack:

```bash
ENV_FILE=/path/to/restore.env ./ops/restore-mongodb.sh --confirm korean-study-YYYYMMDDTHHMMSSZ.archive.gz.age
```

## Release and rollback

Run backend and frontend validation before each deployment. Deploy immutable Git tags or image tags, record the active revision, and retain the previous image revision. To roll back application code, check out the prior release and rerun `./ops/deploy-production.sh`; do not delete the MongoDB volume. Restore data only from a tested backup.

## Data handling

MongoDB stores Discord identity/profile snapshots, flashcards, assignments, grading attempts, and GridFS PDF uploads. Publish a privacy notice identifying Discord and OpenAI as processors. Define a retention period for uploaded PDFs and inactive user data, service deletion requests by deleting the user's assignments and GridFS files, and limit production database/backup access to operators who need it.
