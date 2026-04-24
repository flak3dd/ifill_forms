# Frontend Docker Build Fix TODO

## Approved Plan Steps:
- [x] Step 1: Edit frontend/Dockerfile (update Node version, apk deps, npm install)
- [x] Step 2: Test build with docker-compose build frontend --no-cache
- [x] Step 3: Complete task

---

# Comprehensive Fix Plan (Approved)

## Information Gathered

**Critical Bugs Found:**
1. **Frontend API proxy fails in Docker** — `next.config.js` rewrites `/api/*` to `http://localhost:8000`, but inside a Docker container `localhost` refers to the container itself, not the backend service. Confirmed with live test: `curl http://localhost:3000/api/jobs` returns `ECONNREFUSED 127.0.0.1:8000`.
2. **Duplicate profile endpoints in `backend/main.py`** — `main.py` defines basic `/api/profiles` CRUD endpoints AND includes `profiles_router` from `api/profiles.py`. FastAPI registers the `main.py` endpoints first, shadowing the enhanced router (versioning, workflow builder, field mapping, etc.).

**Docker Issues:**
3. **Frontend Dockerfile** uses deprecated `npm prune --production` (shows npm warning; should be `--omit=dev`).
4. **Frontend missing `.dockerignore`** — local `node_modules`, `.next`, and other artifacts pollute the Docker build context.
5. **Backend Dockerfile** exposes port `8030` but the app actually runs on `8000`.

**Code Quality:**
6. **`datetime.utcnow()`** is deprecated in Python 3.12+ and appears in 21 locations across the backend.

## Plan

| # | File | Change |
|---|------|--------|
| 1 | `frontend/next.config.js` | Make rewrite destination configurable via `BACKEND_URL` env var (fallback `http://localhost:8000`) so Docker can set `http://backend:8000` |
| 2 | `frontend/Dockerfile` | Add `ARG BACKEND_URL`; replace `npm prune --production` with `npm prune --omit=dev` |
| 3 | `docker-compose.yml` | Pass `BACKEND_URL=http://backend:8000` to frontend build args |
| 4 | `frontend/.dockerignore` | Create new file excluding `node_modules`, `.next`, `npm-debug.log`, local env files |
| 5 | `backend/main.py` | Remove duplicate `/api/profiles` endpoints (the enhanced router in `api/profiles.py` handles these) |
| 6 | `backend/Dockerfile` | Change `EXPOSE 8030` → `EXPOSE 8000` |
| 7 | `TODO.md` | Mark Step 3 complete and summarize fixes |

## Follow-up Steps
- Re-build and re-test both frontend and backend containers to verify API proxying works end-to-end.

---

## Progress Tracking
- [x] Fix 1: `frontend/next.config.js` — configurable backend URL
- [x] Fix 2: `frontend/Dockerfile` — build arg + npm prune fix
- [x] Fix 3: `docker-compose.yml` — pass BACKEND_URL build arg
- [x] Fix 4: `frontend/.dockerignore` — create file
- [x] Fix 5: `backend/main.py` — remove duplicate profile endpoints
- [x] Fix 6: `backend/Dockerfile` — fix exposed port
- [x] Fix 7: `backend/models.py` — fix `create_db_and_tables` missing engine import
- [x] Fix 8: `TODO.md` — update completion status

## Verification Results
- Frontend Docker build succeeds without npm warnings
- Backend health check responds: `{"status":"healthy"}`
- Frontend API proxy working: `/api/jobs` → `[]`, `/api/profiles` → `[]`
- Database tables initialize successfully

