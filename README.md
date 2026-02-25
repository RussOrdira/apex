# Apex Predict

Apex Predict monorepo foundation implementing the 2026 plan for:
- FastAPI API (`apex_predict.api.main:app`)
- Worker service (`apex_predict.worker.main:app`)
- Postgres schema + migration starter (`infra/migrations/001_init.sql`)
- Flutter mobile skeleton (`mobile/`)

## Current implementation coverage

Implemented:
- `/v1` endpoints from the roadmap (core loop, leagues, AI advisory, moderation reports, admin scoring/rules)
- Session lifecycle model (`SCHEDULED`, `OPEN`, `LOCKED`, `SCORING`, `FINALIZED`)
- Points-based confidence allocation (`100` credits exact per submission)
- Idempotent scoring entry protection via unique constraints
- Provider abstraction (`OpenF1` primary + fallback adapter)
- Worker job endpoints plus automated scheduler loop for session-state, provider health, AI previews, and auto-finalize scoring
- Supabase JWT verification mode + production RLS migration set
- Session ingestion and scoring mapping for all current prediction categories (`POLE`, `WINNER`, `TOP5`, `DNF`, `FASTEST_LAP`, `SAFETY_CAR`, `MIDFIELD_CONSTRUCTOR`, `FIRST_PIT_STOP_TEAM`, `FIRST_SAFETY_CAR_LAP`)
- Leaderboard snapshot persistence (global + league) after scoring finalization
- Supabase Realtime publication migration for leaderboard snapshot streams
- Seed script for initial season/event/session/questions
- CI coverage for Semgrep, Ruff, and pytest (including `unit`, `security`, `penetration`, and `fuzz` markers)
- pytest integration + unit + security + penetration + fuzz suites, plus Locust profile

Not yet implemented (stubbed or planned next):
- Real push notifications (FCM/APNS integration)
- Rich AI model-backed insights/personalization (current implementation is deterministic advisory baseline)
- Store release automation and billing/paywall

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .[dev]
```

Run API:

```bash
uvicorn apex_predict.api.main:app --reload --port 8000
```

Run Worker:

```bash
uvicorn apex_predict.worker.main:app --reload --port 8010
```

Auto-finalize ended sessions (ingest outcomes + score + finalize):

```bash
curl -X POST http://localhost:8010/jobs/auto-finalize-sessions
```

Manual job triggers are optional when scheduler is enabled (`WORKER_SCHEDULER_ENABLED=true`).

Seed local demo data:

```bash
python scripts/seed_demo_data.py
```

Run tests:

```bash
pytest
# or
npm run test
```

Run targeted suites:

```bash
npm run test:unit
npm run test:security
npm run test:penetration
npm run test:fuzz
```

Locust load testing:

```bash
pip install .[load]
APEX_LOCUST_SESSION_ID=<session-id> \
APEX_LOCUST_QUESTION_ONE_ID=<question-id-1> \
APEX_LOCUST_QUESTION_TWO_ID=<question-id-2> \
locust -f tests/load/locustfile.py --host=http://localhost:8000
# or
npm run load:locust -- --host=http://localhost:8000
```

Run static checks:

```bash
ruff check .
# or
npm run check
```

## Docker compose

```bash
docker compose up --build
```

## Mobile skeleton

`mobile/` contains a Flutter-ready structure with API client and key screens. Install Flutter SDK locally, then run:

```bash
cd mobile
flutter pub get
flutter run
```

## Environment variables

- `DATABASE_URL` (default: `sqlite+aiosqlite:///./apex.db`)
- `AUTH_MODE` (`dev` or `supabase`)
- `SUPABASE_URL`
- `SUPABASE_JWT_ISSUER` (optional; defaults to `<SUPABASE_URL>/auth/v1`)
- `SUPABASE_JWT_AUDIENCE` (default `authenticated`)
- `SUPABASE_JWT_SECRET` (optional HS256 fallback)
- `JWKS_CACHE_TTL_SECONDS`
- `SUPABASE_S3_ENDPOINT` (for Supabase Storage S3 API, usually `https://<project-ref>.storage.supabase.co/storage/v1/s3`)
- `SUPABASE_S3_REGION` (your project region, for example `us-east-1`)
- `SUPABASE_S3_ACCESS_KEY_ID` (from Supabase Storage -> S3 Configuration -> Access keys)
- `SUPABASE_S3_SECRET_ACCESS_KEY` (from Supabase Storage -> S3 Configuration -> Access keys)
- `SUPABASE_S3_BUCKET` (for avatars/profile photos, default `profile-images`)
- `SUPABASE_S3_FORCE_PATH_STYLE` (default `true`)
- `SUPABASE_S3_PUBLIC_BASE_URL` (optional CDN/public base URL for serving uploaded files)
- `AUTO_CREATE_SCHEMA` (`true`/`false`)
- `OPENF1_BASE_URL`
- `FALLBACK_BASE_URL`
- `PROVIDER_TIMEOUT_SECONDS`
- `WORKER_SCHEDULER_ENABLED`
- `WORKER_STARTUP_DELAY_SECONDS`
- `WORKER_SESSION_STATE_INTERVAL_SECONDS`
- `WORKER_PROVIDER_HEALTH_INTERVAL_SECONDS`
- `WORKER_AI_PREVIEWS_INTERVAL_SECONDS`
- `WORKER_AUTO_FINALIZE_INTERVAL_SECONDS`
- `DEFAULT_CONFIDENCE_CREDITS`
- `ADMIN_API_KEY` (required for `/v1/admin/*`, default `dev-admin-key`)

### Supabase Storage S3 Notes

- Keep `SUPABASE_S3_SECRET_ACCESS_KEY` server-side only.
- Do not ship S3 secret/service-role credentials in Flutter/mobile builds.
- Recommended upload flow: mobile requests signed upload URL from API, API uploads or signs against Supabase S3.
