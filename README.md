# Shiloh Korean Study

Full-stack Korean learning application with:

- `FastAPI` backend in `src/shiloh`
- `Next.js` frontend in `frontend/`
- `MongoDB` persistence
- `Discord OAuth` via Auth.js/NextAuth
- AI-backed assignment generation and grading through the OpenAI Responses API using structured JSON output.

## Features

- Discord sign-in and backend JWT sync
- Learner dashboard and profile stats
- User profile with email, Discord ID, and latest Discord profile snapshot
- Flashcard sets with:
  - set-scoped tags
  - `hard` / `medium` / `easy` difficulty
  - weighted study ordering
  - automatic set completion when all cards are easy
  - automatic reopening when non-easy cards return
- Assignments with:
  - manual authoring
  - AI generation from source text
  - AI generation from uploaded PDFs with stored source files
  - AI-backed answer verification
  - stored attempt history
- Admin views for users, flashcard sets, assignments, and submitted PDFs
- Host-side CLI for `super_admin` bootstrap on existing users

## Local Development

### Backend

```bash
uv sync --group dev
uv run pytest
uv run uvicorn shiloh.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend expects:

- `AUTH_SECRET`
- `AUTH_DISCORD_ID`
- `AUTH_DISCORD_SECRET`
- `BACKEND_URL`
- `BACKEND_INTERNAL_AUTH_SECRET`

Discord must be configured with the OAuth redirect URI:

- `http://localhost:3000/api/auth/callback/discord`

## Docker

1. Copy `.env.example` to `.env` and fill in the Discord/OpenAI secrets.
2. Run:

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- MongoDB: `mongodb://localhost:27017`

## Production

Use the separate Caddy-backed production stack rather than the local-development
`docker-compose.yml`. The complete host setup, Discord callback configuration,
and rollback procedure are in
[docs/production.md](docs/production.md).

## Super Admin Bootstrap

Users must sign in once before they can be promoted. After that, grant `super_admin` from the Docker host:

```bash
docker compose exec backend shiloh-admin grant-super-admin --discord-id <discord-id>
```

Inspect users:

```bash
docker compose exec backend shiloh-admin list-users
docker compose exec backend shiloh-admin show-user --discord-id <discord-id>
```

## API Surface

Learner endpoints:

- `GET/POST /api/flashcard-sets`
- `PATCH/DELETE /api/flashcard-sets/{id}`
- `GET/POST /api/flashcard-sets/{id}/flashcards`
- `PATCH/DELETE /api/flashcards/{id}`
- `POST /api/flashcard-sets/{id}/study-session`
- `POST /api/flashcards/{id}/review`
- `GET /api/profile`
- `GET/POST /api/assignments`
- `GET/PATCH/DELETE /api/assignments/{id}`
- `POST /api/assignments/{id}/submit`

Admin endpoints:

- `GET /api/admin/users`
- `GET /api/admin/users/{id}`
- `POST /api/admin/users/{id}/deactivate`
- `POST /api/admin/users/{id}/reactivate`
- `GET /api/admin/flashcard-sets`
- `DELETE /api/admin/flashcard-sets/{id}`
- `GET /api/admin/assignments`
- `DELETE /api/admin/assignments/{id}`
