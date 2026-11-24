# Plan de implementación incremental

**Fecha:** 2026-11-24  
**Regla:** Implementar solo tras aprobación de Fase 1. Incrementos pequeños y auditables.  
**Tests:** tras cada cambio de código → `docker compose exec api pytest` (o venv local).

---

## Incremento 0 — Planificación (actual)

- [x] Assessment funcional  
- [x] Assessment técnico  
- [x] Arquitectura / dominio / roadmap / backlog / épicas / stories  
- [ ] Notion structure live  
- [ ] Go/No-go stakeholder  

**No hay código de feature en este incremento.**

---

## Incremento 1 — RAG foundation (Fase 2a) ✅

**Objetivo:** Semantic retrieve usable + metadata mínima.

Tareas:

1. [x] Migración: columnas metadata en `document_chunks` (`0020_chunk_metadata`).  
2. [x] Mejorar extracción PDF → page map (best effort) (`page_map.py` + `ingestion`).  
3. [x] Actualizar `RagService.index_document` para persistir metadata.  
4. [x] `RagService.semantic_retrieve` usando `embed_query` + `chunks.similar`.  
5. [x] Tests unitarios (`test_page_map.py`, `test_rag.py`).  
6. [x] Hybrid: semantic + stratified (`rag_semantic_enabled`, `rag_semantic_mix_ratio`).

**DoD:** tests verdes (186); generación usa hybrid vía `contexts_for` + título del documento.

---

## Incremento 2 — Citation + Evidence persistence (Fase 3a)

1. `CitationEngine` (verify substring + scores).  
2. Tablas `question_evidence`, `answer_references`.  
3. En generación: crear evidence.  
4. En submit attempt: snapshot AnswerReference.  
5. Extender schemas `QuestionResult.evidence`.  
6. Tests.

**DoD:** API attempt incluye evidence JSON.

---

## Incremento 3 — Evidence UI (Fase 3b)

1. `EvidencePanel` en resultado de examen.  
2. i18n keys.  
3. Estados vacíos / página N/D.  

**DoD:** UX revisable en desktop/mobile.

---

## Incremento 4 — Document chat MVP (Fase 4)

1. Models conversation/message.  
2. `DocumentChatService` fail-closed.  
3. APIs + Celery si latencia alta.  
4. UI chat.  
5. Créditos/límites.  
6. AiDecisionEvent básico.

---

## Incremento 5 — Appeals MVP (Fase 5)

1. Models + state machine.  
2. Create/list/get/resolve APIs.  
3. Student CTA + teacher inbox.  
4. Attach student chunk evidence (impugnación).  
5. Notifications email.

---

## Incremento 6 — Threading (Fase 6)

1. Comments + attachments.  
2. Notifications on reply.  
3. Action log.

---

## Incremento 7 — Teacher AI (Fase 7)

1. `AppealAiService` + Celery task.  
2. Persist recommendation.  
3. UI card “sugerencia no vinculante”.  
4. Tests de ambigüedad con fixtures.

---

## Incremento 8 — Audit hardening (Fase 8–9)

1. Completar AiDecisionEvent en todos los paths.  
2. Audit UI / export.  
3. Retención, rate limits, load tests, cost guards.

---

## Orden de PRs sugerido

1. `feat(rag): chunk metadata + semantic retrieve`  
2. `feat(evidence): citation engine + persistence`  
3. `feat(web): evidence panel on attempt results`  
4. `feat(chat): grounded document chat MVP`  
5. `feat(appeals): case lifecycle + student/teacher UI`  
6. `feat(appeals): thread comments + notifications`  
7. `feat(appeals): teacher AI recommendation`  
8. `feat(audit): ai decision events + export`

Cada PR: migración + tests + sin romper APIs existentes.

---

## Checklist pre-código (gate)

| Gate | Estado |
|---|---|
| Functional assessment | ✅ |
| Technical assessment | ✅ |
| Risks documented | ✅ |
| Target architecture | ✅ |
| Domain + data model | ✅ |
| API sketch | ✅ |
| Roadmap + backlog + stories | ✅ |
| Notion project structure | ✅ |
| Explicit go to implement | ⏳ user |

**Hasta el go explícito del usuario, no se escribe código de producto.**
