# Assessment técnico — Evaluación inteligente (RAG, evidencia, apelaciones)

**Producto:** QuizDock (`apps/api` + `apps/web`)  
**Fecha:** 2026-11-24  
**Estado:** Assessment completo — **sin implementación de código**

---

## 1. Stack y arquitectura actual

| Capa | Tecnología |
|---|---|
| Web | Next.js App Router, TypeScript, Tailwind, shadcn/ui |
| API | FastAPI, Pydantic v2, JWT, `/api/v1` |
| Persistencia | PostgreSQL, SQLAlchemy 2 async, Alembic |
| Vectores | **pgvector** (`document_chunks.embedding`, HNSW cosine) |
| Jobs | Redis + Celery (`documents.process`, `assessments.generate_*`) |
| LLM | Gemini / OpenAI-compatible (`llm_*` settings) |
| Embeddings | Gemini `batchEmbedContents` / OpenAI embeddings; fallback hashed |

Capas ya alineadas a Clean Architecture: routers → services → repositories → models. **Mantener.**

---

## 2. Inventario de lo reutilizable

### Fortalezas (reutilizar)

| Componente | Path | Reuso |
|---|---|---|
| `DocumentChunk` + pgvector | `app/models/chunk.py` | Base de Retrieval Layer |
| `ChunkRepository.similar` | `app/repositories/chunks.py` | Semantic search (hoy **no cableado**) |
| `embed_texts` / `embed_query` | `app/services/embeddings.py` | Embeddings + query embed |
| `chunk_text` | `app/services/chunking.py` | Chunking por párrafos + filtro TOC |
| `RagService.index_document` | `app/services/rag.py` | Indexación al procesar |
| `Question.source_chunk_position` | `app/models/exam.py` | Semilla de evidencia |
| `Question.explanation` | idem | Justificación IA actual |
| `AuditEvent` + service | `app/models/audit.py` | Extender acciones / o crear `AiAuditEvent` |
| `GenerationJob` + Celery | tasks | Jobs largos (chat batch, appeal analysis) |
| RBAC + `organization_id` | deps / memberships | Tenancy obligatorio en entidades nuevas |
| UI resultado de intento | `exams/[id]/page.tsx` | Extender con EvidenceViewer |
| Mail / SMTP | `app/services/mail.py` | Notificaciones de apelación |

### Deuda técnica relevante

1. **Retrieval no semántico en generación.** `RagService.retrieve_contexts` hace muestreo estratificado aleatorio; **no** llama a `ChunkRepository.similar` ni `embed_query`. `rag_candidate_k` está en config y no se usa.
2. **Chunks sin metadata de página/capítulo/sección.** Solo `position`, `content`, `embedding`. `Document.page_count` existe, pero el texto extraído no se alinea a páginas en el modelo de chunks.
3. **Evidencia no se materializa.** `source_chunk_position` se guarda en generación; no hay entidad `QuestionEvidence` / `AnswerReference`; `QuestionResult` no expone chunk ni scores.
4. **Embeddings dual-path.** Sin API key se usa hashing; calidad de similitud y re-ranking cae. Hay que fallar cerrado o marcar `embedding_quality=heuristic` en audit.
5. **Audit no es explainability.** Solo eventos de org/contenido; no prompts, modelos, relevance/confidence.
6. **Sin módulos** de chat, appeals, messaging, AI review assistant.
7. **PDF parse** (preview/process) no garantiza offsets de página por chunk — riesgo #1 para citas.

---

## 3. Gap analysis vs arquitectura IA objetivo

| Capa objetivo | Hoy | Gap |
|---|---|---|
| Chunking | Párrafos + overlap | Falta chunking page-aware / heading-aware |
| Metadata enrichment | Casi nulo | page_start/end, chapter, section, char offsets |
| Embeddings | Sí | Calidad / versionado de modelo / reindex |
| Vector DB | pgvector | OK a corto plazo; monitorear escala |
| Semantic search | Repo `similar` sin uso | Cablear + filtros tenant |
| Re-ranking | No | Cross-encoder o LLM re-rank ligero |
| Context compression | No | Para chat multi-turn |
| Citation verification | Parcial (`grounded_question`) | CitationEngine + span verification |
| Hallucination prevention | Heurísticas en generación | Política fail-closed en chat/apelaciones |
| Assessment evidence | explanation only | QuestionEvidence + API + UI |
| Document chat | No | Agent + ConversationManager |
| Appeal center | No | Dominio completo |
| Review center (teacher AI) | No | Servicio + job async |
| Audit center | Org audit only | AiDecisionLog |

---

## 4. Modelo de datos propuesto (resumen)

Ver detalle en `domain-model.md`. Entidades nuevas sugeridas:

**Retrieval / Evidence**

- Extender `DocumentChunk`: `page_start`, `page_end`, `chapter`, `section`, `char_start`, `char_end`, `token_count`, `embedding_model`.
- `QuestionEvidence` (1..n por question): chunk_id, quote, confidence, relevance, generated_at, model, prompt_hash.
- `AnswerReference` (opcional, snapshot inmutable ligado a attempt result).

**Chat**

- `DocumentConversation`, `DocumentChatMessage` (role, content, citations JSONB).

**Appeals**

- `AppealCase`, `AppealComment`, `AppealEvidence`, `AppealResolution`, `AppealActionLog`.

**AI audit**

- `AiDecisionEvent` (o extensión tipada de audit): document_id, chunk_ids, prompt, model, scores, outcome, actor.

Compatibilidad: no romper tablas existentes; migraciones Alembic aditivas; `source_chunk_position` se mantiene como denormalización hasta backfill.

---

## 5. APIs propuestas (`/api/v1`)

### Evidencia

- `GET /exams/{exam_id}/questions/{question_id}/evidence`
- Extender `AttemptRead.results[]` con `evidence: EvidenceRead | null`

### Chat

- `POST /documents/{document_id}/chat/sessions` → 201
- `POST /documents/{document_id}/chat/sessions/{id}/messages` → 202 + job o sync corto
- `GET .../messages`

### Apelaciones

- `POST /attempts/{attempt_id}/questions/{question_id}/appeals`
- `GET /appeals` (estudiante: mías; profesor: bandeja)
- `GET /appeals/{id}`
- `POST /appeals/{id}/comments`
- `POST /appeals/{id}/evidence`
- `PATCH /appeals/{id}/status` (roles autoritarios)
- `POST /appeals/{id}/resolve`
- `POST /appeals/{id}/ai-review` → 202 + recomendación

Todas scoped por `organization_id` + RBAC.

---

## 6. Riesgos técnicos

| ID | Riesgo | Severidad | Mitigación |
|---|---|---|---|
| T1 | Página exacta imposible sin parse page-aware | Alta | Mejorar extractor; degradar UX; no inventar |
| T2 | Coste LLM (chat + appeal AI + re-rank) | Alta | Créditos, límites, caching embeddings, Celery |
| T3 | Alucinaciones en chat | Crítica | Grounding obligatorio + citation check + refusal |
| T4 | Reindex masivo al cambiar embedding model | Media | `embedding_model` en chunk + job de reindex |
| T5 | Contención advisory locks en index | Media | Ya hay lock; extender a reindex |
| T6 | Crecimiento de `AiDecisionEvent` | Media | Retención, partición, payload size limits |
| T7 | Race en estados de apelación | Media | State machine en servicio + tests |
| T8 | Tenancy leak en semantic search | Crítica | Filtro org+document siempre en repository |
| T9 | Frontend complexity en evidence/appeal | Media | Componentes aislados + i18n |
| T10 | Dual embedding quality (hash vs API) | Media | Flag en evidencia + métricas |

---

## 7. Oportunidades técnicas

- Activar `similar` + `embed_query` mejora calidad de generación **antes** de UI de evidencia.
- pgvector evita nuevo vendor a corto plazo.
- `AuditEvent.payload` JSONB puede prototipar AI audit; luego promover a tabla tipada.
- Jobs Celery existentes son el patrón correcto para AI review y chat pesado.
- Tests fakes (`tests/fakes.py`) facilitan unit tests sin LLM real.

---

## 8. Observabilidad requerida

- Métricas: retrieval latency, hit rate, citation coverage %, appeal volume, AI review acceptance rate.
- Logs estructurados: `request_id`, `organization_id`, `model`, `chunk_ids`.
- Tracing opcional en Celery tasks de IA.
- Dashboard interno (fase 8–9): % preguntas con evidencia válida.

---

## 9. Decisiones preliminares (a formalizar en ADRs)

1. **pgvector** permanece como vector store (Fase 2–7); evaluar Qdrant/Pinecone solo si escala lo exige.
2. **Evidencia materializada** en tabla propia (no solo leer chunk en runtime) para auditabilidad inmutable.
3. **Chat** fail-closed sin citas.
4. **IA nunca resuelve apelaciones**; solo recomienda.
5. **Migraciones aditivas**; backfill de evidencia para preguntas existentes best-effort.

---

## 10. Veredicto técnico

La base (chunks, embeddings, pgvector, Celery, tenancy, explanation + source_chunk_position) **habilita** la iniciativa, pero el retrieval actual **no es RAG semántico de producción** y falta toda la capa de explainability/appeals.

**Orden de implementación técnico correcto:** enriquecimiento de chunks → semantic retrieve + citation → evidencia en API/UI → chat → appeals → messaging → teacher AI → audit hardening.

**Bloqueo de código:** vigente hasta cerrar arquitectura, dominio, roadmap y Notion (`implementation-plan.md`).
