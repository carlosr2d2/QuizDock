# QuizDock — agent notes

Hybrid B2B/B2C SaaS: ingest technical documents and generate exams, quizzes, and flashcards with LLMs.

## Layout

- `apps/web` — Next.js App Router (RSC default, Tailwind, shadcn/ui)
- `apps/api` — FastAPI, SQLAlchemy 2 async, Alembic, Celery
- Product and architecture rules live in `.cursor/rules/`

## Tenancy

Personal workspaces and organizations share one tenancy model. Scope every query by `organization_id`. Roles: `owner`, `admin`, `member`, `auditor`.

## Do not

- Put business logic in FastAPI routers or React components
- Run PDF/LLM work inside an HTTP request — enqueue Celery
- Skip Alembic for schema changes
- Mix B2C and B2B as separate codebases
- Skip unit tests after a code change — run `docker compose exec api pytest`
