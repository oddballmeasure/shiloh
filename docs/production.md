# Production Deployment

Deploy this application to `/opt/korean-study` on an Ubuntu/Debian-class VPS with Docker Engine and Docker Compose v2 installed. Use a non-root SSH deploy user with access to the Docker group.

## First deployment

1. Point the production domain's proxied Cloudflare `A` record at the VPS. Do not create an `AAAA` record unless the VPS has working IPv6.
2. Permit only SSH and HTTP in the host firewall. Do not publish MongoDB, FastAPI, or the frontend container port.
3. Copy `.env.production.example` to `.env.production`, fill every value, and run `chmod 600 .env.production`.
4. Configure Discord with `https://<DOMAIN>/api/auth/callback/discord` as its redirect URI.
5. Install Nginx and copy `ops/nginx/shiloh.conf` to `/etc/nginx/sites-available/shiloh`. Enable it with `ln -sfn /etc/nginx/sites-available/shiloh /etc/nginx/sites-enabled/shiloh`, then run `nginx -t` and `systemctl enable --now nginx`.
6. In Cloudflare, keep the record proxied and select `SSL/TLS encryption mode: Flexible`. Cloudflare terminates browser HTTPS and proxies to the Nginx HTTP origin.
7. Run `./ops/deploy-production.sh`.
8. Verify `https://<DOMAIN>`, Discord sign-in, an AI assignment, a PDF upload, and `docker compose --env-file .env.production -f docker-compose.prod.yml ps`.
9. Sign in with the first administrator, then run `docker compose --env-file .env.production -f docker-compose.prod.yml exec backend shiloh-admin grant-super-admin --discord-id <discord-id>`.

Cloudflare Flexible mode leaves the Cloudflare-to-origin hop unencrypted. Restrict direct origin access to Cloudflare IP ranges when practical, and move to Cloudflare Full (strict) with an origin certificate when the host firewall/network permits it.

## Release and rollback

Run backend and frontend validation before each deployment. Deploy immutable Git tags or image tags, record the active revision, and retain the previous image revision. To roll back application code, check out the prior release and rerun `./ops/deploy-production.sh`; do not delete the MongoDB volume.

## Data handling

MongoDB stores Discord identity/profile snapshots, flashcards, assignments, grading attempts, and GridFS PDF uploads. Publish a privacy notice identifying Discord and OpenAI as processors. Define a retention period for uploaded PDFs and inactive user data, service deletion requests by deleting the user's assignments and GridFS files, and limit production database access to operators who need it.
