# Arquitectura objetivo — Evaluación inteligente QuizDock

**Fecha:** 2026-11-24  
**Estado:** Propuesta (pre-implementación)  
**Principios:** Clean Architecture, DDD ligero, SOLID, backward compatible, tenancy por `organization_id`

---

## 1. Vista de contexto

```
┌─────────────┐     JWT + X-Organization-Id      ┌──────────────────┐
│  Next.js    │ ───────────────────────────────► │  FastAPI /api/v1 │
│  apps/web   │ ◄─────────── JSON / 202 ──────── │  apps/api        │
└─────────────┘                                  └────────┬─────────┘
                                                          │
                    ┌─────────────────────────────────────┼────────────────┐
                    │                                     │                │
                    ▼                                     ▼                ▼
             PostgreSQL+pgvector                      Redis/Celery      LLM APIs
             (OLTP + vectors)                         (async jobs)    (chat/embed)
```

---

## 2. Capas lógicas (IA + producto)

```
┌────────────────────────────────────────────────────────────┐
│ Application Layer                                          │
│  Assessment · Document Chat · Appeal Center                │
│  Review Center · Audit Center · Notifications              │
├────────────────────────────────────────────────────────────┤
│ Explainability Layer                                       │
│  CitationEngine · EvidenceViewer · Confidence · AiAudit    │
├────────────────────────────────────────────────────────────┤
│ Intelligence Layer                                         │
│  RAG · ReRank · ContextCompress · HallucinationGuard       │
├────────────────────────────────────────────────────────────┤
│ Retrieval Layer                                            │
│  Chunking · MetadataEnrich · Embeddings · VectorSearch     │
└────────────────────────────────────────────────────────────┘
```

Mapeo a código existente / nuevo:

| Capa | Ubicación |
|---|---|
| Presentation | `app/api/v1/*` routers (thin) |
| Application / Domain services | `app/services/` (nuevos: `evidence.py`, `document_chat.py`, `appeals.py`, `appeal_ai.py`, `citations.py`) |
| Repository | `app/repositories/` |
| Tasks | `app/tasks/` (nuevos jobs) |
| Models | `app/models/` |
| Frontend | `apps/web` RSC + client islands |

**Regla:** sin lógica de negocio en routers ni en componentes UI.

---

## 3. Flujos objetivo

### 3.1 Indexación (Retrieval)

```
PDF upload → Celery process → extract text (+ page map)
  → chunk_text (page/heading aware)
  → enrich metadata
  → embed_texts
  → replace DocumentChunk rows (tenant scoped)
  → audit document.indexed
```

### 3.2 Generación de pregunta con evidencia

```
contexts = semantic_retrieve OR stratified hybrid
  → LLM generate grounded question
  → CitationEngine.verify(quote ∈ chunk)
  → persist Question + QuestionEvidence (+ AiDecisionEvent)
```

### 3.3 Revisión de intento (estudiante)

```
submit_attempt → score
  → attach AnswerReference snapshot from QuestionEvidence
  → UI EvidencePanel
```

### 3.4 Document chat

```
message → embed_query → similar(k) → re-rank → compress
  → LLM with strict citation schema
  → verify citations → refuse if empty
  → store messages + AiDecisionEvent
```

### 3.5 Apelación + AI review (profesor)

```
student creates AppealCase + AppealEvidence
  → notify reviewers
  → optional POST ai-review (Celery)
  → AppealAiRecommendation (non-binding)
  → professor resolves → AppealResolution + audit
```

---

## 4. Componentes clave

### CitationEngine

- Input: claim/explanation, candidate chunks.
- Output: verified quotes, page/chapter, confidence, relevance.
- Verifica que el fragmento citado sea subcadena (normalizada) del chunk.
- Nunca inventa página.

### RagService (evolución)

- Mantener `index_document` / `ensure_indexed`.
- Añadir `semantic_retrieve(document_id, org_id, query, k)`.
- Hybrid: semantic top-N + diversity sampling (preservar cobertura de blueprint).
- Re-ranking pluggable (`NoopReranker` → `LlmReranker`).

### DocumentChatAgent

- Orquesta ContextManager + ConversationHistory + CitationEngine.
- System policy: answer only from evidence; cite; refuse.

### AppealStateMachine

Estados: `pending → in_review → needs_info → accepted|rejected → closed`.  
Transiciones validadas en servicio; acciones en `AppealActionLog`.

### AppealAiAssistant

- Solo recomienda; escribe `recommendation`, `confidence`, `rationale`, `alt_chunk_ids`.
- No cambia estado de resolución.

---

## 5. Contratos API (borrador)

Ver schemas futuros en `app/schemas/evidence.py`, `chat.py`, `appeals.py`.

```http
GET  /api/v1/exams/{exam_id}/attempts/{attempt_id}
# results[].evidence: { quote, page_start, page_end, chapter, section,
#   document_id, document_title, confidence, relevance, generated_at, model }

POST /api/v1/documents/{id}/chat/sessions
POST /api/v1/documents/{id}/chat/sessions/{sid}/messages
GET  /api/v1/appeals?status=&role=
POST /api/v1/appeals/{id}/ai-review   # 202
POST /api/v1/appeals/{id}/resolve
```

Versionado: solo `/api/v1`. Campos nuevos opcionales en responses existentes para backward compatibility.

---

## 6. Persistencia y migraciones

- Alembic aditivo a partir de `0019_*`.
- Índices: `(organization_id, document_id)`, HNSW embeddings, `(appeal.status, org)`.
- Snapshots: `AnswerReference` / evidence quote inmutables (no depender solo de chunk mutable).

---

## 7. Seguridad y tenancy

- Toda query filtra `organization_id` en **repository**.
- Chat y appeals respetan RBAC:
  - estudiante: propios intentos / propias apelaciones
  - admin/owner/auditor: bandeja org
  - member autor puede crear contenido; resolución de apelaciones: owner/admin (+ futuro rol `instructor`)
- No filtrar filas solo en router.
- Rate limit / créditos en chat y AI review.

---

## 8. Diagrama de dominio (bounded contexts)

```
[Documents & Retrieval] ──provides──► [Assessment & Evidence]
         │                                    │
         │                                    ├──► [Appeals & Messaging]
         │                                    │
         └──► [Document Chat]                 └──► [Teacher AI Review]
                          \                      /
                           └──► [AI Audit / Explainability]
```

Shared kernel: `Organization`, `User`, `Membership`, IDs UUID, timestamps.

---

## 9. Frontend architecture

Rutas nuevas (propuestas):

- Extender `exams/[id]` — EvidencePanel en resultados.
- `documents/[id]/chat` — chat grounded.
- `appeals` — lista estudiante.
- `appeals/[id]` — detalle / hilo.
- `team/appeals` — bandeja profesor.
- `team/appeals/[id]/review` — evidencia comparada + AI suggestion.

Componentes: `EvidencePanel`, `CitationCard`, `AppealWizard`, `AppealThread`, `AiRecommendationCard`, `ChunkHighlighter`.

i18n obligatorio (ES/EN) en `lib/i18n/messages.ts`.

---

## 10. ADRs a escribir en implementación (Fase 2+)

| ADR | Tema |
|---|---|
| ADR-E01 | Materializar QuestionEvidence vs join runtime |
| ADR-E02 | Page mapping strategy for PDFs |
| ADR-E03 | Hybrid retrieval for exam generation |
| ADR-E04 | Chat sync vs async responses |
| ADR-E05 | AiDecisionEvent table vs AuditEvent extension |
| ADR-E06 | Appeal reviewer roles |

---

## 11. Compatibilidad hacia atrás

- APIs existentes siguen funcionando; campos nuevos nullable.
- Preguntas sin evidencia: UI muestra estado “sin evidencia disponible”.
- `source_chunk_position` se conserva.
- Planes/créditos: nuevos consumos se suman sin romper catálogo actual.
