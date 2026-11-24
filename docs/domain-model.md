# Modelo de dominio y datos — Evaluación inteligente

**Fecha:** 2026-11-24  
**Convenciones:** UUID PK, `created_at`/`updated_at`, siempre `organization_id` en entidades tenant.

---

## 1. Agregados y bounded contexts

### Documents & Retrieval

- **Document** (existente)
- **DocumentChunk** (existente, enriquecido)

### Assessment & Evidence

- **Exam**, **Question**, **ExamAttempt** (existentes)
- **QuestionEvidence** (nuevo)
- **AnswerReference** (nuevo; snapshot por intento)

### Document Chat

- **DocumentConversation**
- **DocumentChatMessage**

### Appeals & Messaging

- **AppealCase** (aggregate root)
- **AppealComment**
- **AppealEvidence**
- **AppealResolution**
- **AppealActionLog**

### Explainability

- **AiDecisionEvent**

---

## 2. Entidades — detalle

### 2.1 DocumentChunk (evolución)

| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| document_id | UUID | FK |
| organization_id | UUID | tenant |
| position | int | orden estable |
| content | text | |
| embedding | vector(1536) | |
| page_start | int? | nuevo |
| page_end | int? | nuevo |
| chapter | str? | nuevo |
| section | str? | nuevo |
| char_start | int? | offset en extracted_text |
| char_end | int? | |
| embedding_model | str? | trazabilidad |
| content_hash | str? | integridad |

### 2.2 QuestionEvidence

Evidencia canónica que justifica la respuesta correcta de una pregunta.

| Campo | Tipo |
|---|---|
| id | UUID |
| organization_id | UUID |
| question_id | UUID |
| document_id | UUID |
| chunk_id | UUID? |
| quote | text |
| page_start / page_end | int? |
| chapter / section | str? |
| confidence | float 0–1 |
| relevance | float 0–1 |
| model | str |
| prompt_hash | str? |
| generated_at | timestamptz |
| source | enum: `generation` \| `backfill` \| `manual` |

Relación: Question 1 — 0..n QuestionEvidence (v1: 1 primaria).

### 2.3 AnswerReference

Snapshot inmutable mostrado en el resultado del intento (sobrevive a reindex).

| Campo | Tipo |
|---|---|
| id | UUID |
| organization_id | UUID |
| attempt_id | UUID |
| question_id | UUID |
| evidence_id | UUID? |
| quote | text |
| page_start / page_end | int? |
| chapter / section | str? |
| document_id | UUID |
| document_title | str |
| confidence | float |
| generated_at | timestamptz |

### 2.4 DocumentConversation / DocumentChatMessage

| Conversation | |
|---|---|
| id, organization_id, document_id, user_id, exam_id?, title?, created_at |

| Message | |
|---|---|
| id, conversation_id, organization_id, role (`user`\|`assistant`\|`system`) |
| content | text |
| citations | JSONB `[{chunk_id, quote, page_start, page_end, chapter, confidence}]` |
| refusal | bool |
| model | str? |
| ai_decision_id | UUID? |

### 2.5 AppealCase

| Campo | Tipo |
|---|---|
| id | UUID |
| organization_id | UUID |
| attempt_id | UUID |
| question_id | UUID |
| exam_id | UUID |
| student_user_id | UUID |
| status | enum (ver abajo) |
| student_argument | text |
| selected_index / selected_indices | JSONB |
| correct_index / correct_indices | JSONB |
| system_evidence_snapshot | JSONB |
| created_at / updated_at | |

**Estados:** `pending`, `in_review`, `needs_info`, `accepted`, `rejected`, `closed`.

### 2.6 AppealComment

| Campo | |
|---|---|
| id, appeal_id, organization_id, author_user_id, body, created_at |
| attachment_keys | JSONB? (storage keys) |

### 2.7 AppealEvidence

Evidencia aportada por estudiante (o profesor) — tipicamente chunk seleccionado.

| Campo | |
|---|---|
| id, appeal_id, organization_id, submitted_by_user_id |
| chunk_id?, quote, page_start?, page_end?, chapter?, section? |
| argument | text? |
| source | `student` \| `system` \| `teacher` |

### 2.8 AppealResolution

| Campo | |
|---|---|
| id, appeal_id, organization_id, resolver_user_id |
| decision | `accepted` \| `rejected` \| `needs_info` |
| rationale | text |
| score_adjustment | float? (opcional v2) |
| ai_recommendation_id | UUID? |
| resolved_at | |

### 2.9 AppealActionLog

Auditoría de acciones humanas sobre el caso (además de AiDecisionEvent).

| Campo | |
|---|---|
| id, appeal_id, organization_id, actor_user_id, action, payload JSONB, created_at |

### 2.10 AiDecisionEvent

| Campo | |
|---|---|
| id, organization_id, actor_user_id? |
| feature | `generation` \| `evidence` \| `chat` \| `appeal_review` |
| document_id?, exam_id?, question_id?, appeal_id?, conversation_id? |
| model, prompt (or prompt_hash + storage ref), response_summary |
| chunk_ids UUID[] / JSONB |
| confidence, relevance |
| outcome | str |
| created_at |

---

## 3. Diagramas ER (simplificado)

```
Document 1──* DocumentChunk
Exam 1──* Question 1──0..* QuestionEvidence *──1 DocumentChunk
ExamAttempt 1──* AnswerReference *──0..1 QuestionEvidence

Document 1──* DocumentConversation 1──* DocumentChatMessage

ExamAttempt + Question ──► AppealCase
AppealCase 1──* AppealComment
AppealCase 1──* AppealEvidence
AppealCase 1──0..1 AppealResolution
AppealCase 1──* AppealActionLog
```

---

## 4. Reglas de invariantes (DDD)

1. `QuestionEvidence.quote` debe pertenecer al `chunk.content` (normalizado) si `chunk_id` no es null.
2. `AppealCase` solo se crea sobre intento propio completado y pregunta incorrecta (configurable).
3. Transiciones de estado inválidas se rechazan.
4. `AppealResolution` solo por roles autorizados; IA no escribe resolution decision final.
5. Mensajes assistant del chat con `refusal=false` deben tener `citations.length >= 1`.
6. Todas las entidades tenant filtran por `organization_id` consistente con document/exam.

---

## 5. Servicios de dominio (nombres)

| Servicio | Responsabilidad |
|---|---|
| `RagService` | index + retrieve hybrid |
| `CitationEngine` | verify quotes + scores |
| `EvidenceService` | create/read evidence + snapshots |
| `DocumentChatService` | sessions + grounded replies |
| `AppealService` | cases, comments, state machine |
| `AppealAiService` | non-binding recommendations |
| `AiAuditService` | persist AiDecisionEvent |
| `NotificationService` | mail/in-app hooks |

---

## 6. Enums compartidos (propuesta)

```text
AppealStatus: pending | in_review | needs_info | accepted | rejected | closed
EvidenceSource: generation | backfill | manual | student | system | teacher
AiFeature: generation | evidence | chat | appeal_review
ChatRole: user | assistant | system
```
