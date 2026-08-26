# QuizDock

Plataforma SaaS híbrida (B2B / B2C) para convertir documentos técnicos en cuestionarios, exámenes y flashcards mediante IA y procesamiento asíncrono.

## Arquitectura

Monorepo desacoplado con Clean Architecture:

| App | Stack | Rol |
|---|---|---|
| `apps/web` | Next.js App Router, TypeScript, Tailwind CSS | UI (RSC + islas cliente) |
| `apps/api` | FastAPI, SQLAlchemy 2 async, Alembic, Celery | API `/api/v1`, dominio, workers |

Tenancy unificado: cada usuario recibe un workspace personal al registrarse. Las organizaciones de equipo reutilizan el mismo modelo (RBAC: `owner`, `admin`, `member`, `auditor`). El contexto de organización viaja en `X-Organization-Id`.

El trabajo pesado (parseo de PDFs, embeddings, generación con LLM) **nunca** se ejecuta en el request HTTP: se encola en Celery.

## Arranque con Docker

```bash
cp .env.example .env
docker compose up --build
```

- Web: [http://localhost:3000](http://localhost:3000)
- API / OpenAPI: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- Flower (Celery): [http://localhost:5555](http://localhost:5555)
- Mailpit (correo local): [http://localhost:8025](http://localhost:8025)
- PostgreSQL + pgvector: `localhost:5432`
- Redis: `localhost:6379`

La API aplica `alembic upgrade head` al arrancar.

## Reset de desarrollo

Borra todos los datos de negocio (usuarios, documentos, exámenes, créditos) y crea un usuario de prueba con 10.000 créditos:

```powershell
.\scripts\reset-dev.ps1
```

- Correo: `demo@example.com`
- Contraseña: `demo12345`

Opciones: `.\scripts\reset-dev.ps1 --email otro@test.local --password secret12 --credits 5000`


## Pruebas

Desde `apps/api` (venv activado):

```bash
pip install -r requirements-dev.txt
pytest
```

Con Docker:

```bash
docker compose exec api pip install -r requirements-dev.txt
docker compose exec api pytest
```

Cubren tipos de pregunta y puntuación, autenticación (registro/login/JWT), créditos (débito/reembolso), el flujo de generación de exámenes (permisos, cola, persistencia) e invitaciones por correo.

## Arranque local (desarrollo)

Infraestructura:

```bash
docker compose up db redis
```

API (desde `apps/api`, Python **3.11–3.13**; 3.14 aún no tiene wheels estables para asyncpg/pydantic):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000
```

Worker y Flower (opcional, mismo venv):

```bash
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app flower --port=5555
```

Web (desde `apps/web`):

```bash
cp .env.example .env.local
npm install
npm run dev
```

## Primer flujo

1. Abrir `/register` y crear una cuenta (50 créditos de bienvenida).
2. Subir un PDF, `.txt` o `.md` en **Documentos**. El worker extrae el texto.
3. Cuando el estado sea *listo*, generar un **examen** (8 créditos) o **flashcards** (12 créditos). El worker indexa el documento en fragmentos (RAG) y genera **un ítem por fragmento** relevante.
4. Hacer el cuestionario o repasar tarjetas (SM-2). Si la generación falla, los créditos se reembolsan.
5. En un workspace de equipo, **Equipo → Invitar** envía el correo. En local los mensajes aparecen en [Mailpit](http://localhost:8025).

Sin `LLM_API_KEY`, el worker usa embeddings locales (hash) y un generador heurístico. Con Gemini, pon en `.env` una clave de [Google AI Studio](https://aistudio.google.com/apikey) (`AQ.` o `AIza`) y:

```
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_MODEL=gemini-2.5-flash
LLM_EMBEDDING_MODEL=gemini-embedding-001
```

QuizDock llama a la API nativa de Gemini (`x-goog-api-key`); las claves `AQ.` no funcionan bien en el endpoint compatible con OpenAI. Tras cambiar la clave, recrea `api` y `worker`. Un documento ya *listo* se indexa al generar si aún no tiene fragmentos.

## Capas del backend

```text
apps/api/app/
  api/          # routers FastAPI (presentation)
  services/     # dominio: auth, créditos, documentos, scoring
  repositories/ # SQLAlchemy async, siempre filtrado por organization_id
  models/       # User, Organization, Membership, Document, DocumentChunk, Exam, Flashcard, CreditTransaction
  schemas/      # Pydantic v2
  tasks/        # Celery
  core/         # settings, DB, JWT, Celery
```

## Convenciones

Las reglas persistentes para el agente están en `.cursor/rules/`. Resumen:

- `'use client'` solo en UI interactiva.
- Routers delgados; la lógica vive en services.
- Toda query de tenant filtra por `organization_id` en el repositorio.
- Cambios de schema solo con Alembic.
