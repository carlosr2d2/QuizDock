# Roadmap — Evaluación inteligente QuizDock

**Horizonte:** ~9 fases incrementales  
**Fecha:** 2026-11-24  
**Regla:** no hay implementación de producto hasta cerrar Fase 1.

---

## Vista por fases

| Fase | Objetivo | Dependencias | Estimación relativa |
|---|---|---|---|
| **1** Assessment técnico y funcional | Docs, Notion, ADRs borrador, buy-in | — | Completada (este entregable) |
| **2** Infraestructura RAG | Page-aware chunks, semantic retrieve, re-rank v0, reindex | F1 | M |
| **3** Sistema de Evidencias | QuestionEvidence, API, UI resultado | F2 | M |
| **4** Chat con Documento | Agent grounded + citas + UI | F2 (ideal F3) | L |
| **5** Sistema de Apelaciones | AppealCase + estados + bandeja | F3 | L |
| **6** Mensajería Profesor–Alumno | Hilos, adjuntos, notificaciones | F5 | M |
| **7** Asistente IA Profesor | Comparación evidencias + recomendación | F5–F6 | M |
| **8** Auditoría y Explainability | AiDecisionEvent, export, dashboards | F3+ | M |
| **9** Optimización y Hardening | perf, costos, abuse, QA, SLO | F2–F8 | M |

---

## Detalle

### Fase 1 — Assessment (actual)

Entregables: `/docs/*`, Notion épicas/historias/tareas/bugs/roadmap, riesgos, plan de implementación.  
**Exit criteria:** stakeholders alineados; backlog priorizado; sin código de features.

### Fase 2 — Infraestructura RAG

- Metadata en chunks (página/capítulo cuando sea posible).
- Cablear `embed_query` + `similar`.
- Hybrid retrieval para generación.
- Re-rank básico + métricas citation coverage.
- Job de reindex.

**Exit:** ≥ X% chunks con page metadata en corpus de prueba; semantic retrieve en tests.

### Fase 3 — Evidencias

- Tablas `question_evidence`, `answer_references`.
- Materializar evidencia en generación.
- Extender `AttemptRead` + EvidencePanel UI.
- Backfill best-effort.

**Exit:** estudiante ve fragmento + referencia en resultados.

### Fase 4 — Chat

- Conversaciones + mensajes + CitationEngine en respuestas.
- UI chat; créditos/límites.
- Refusal path testeado.

**Exit:** chat solo responde con citas o se niega.

### Fase 5 — Apelaciones

- Modelo + state machine + APIs + UI crear/seguir.
- Notificación a reviewers.
- Impugnación con selección de fragmento (F6 parcial puede ir aquí).

**Exit:** flujo pending → resolve feliz.

### Fase 6 — Mensajería

- Comentarios/adjuntos en hilo.
- Notificaciones mail/in-app.
- Historial completo en UI profesor/estudiante.

### Fase 7 — Asistente IA

- Job `appeals.ai_review`.
- UI recomendación no vinculante.
- Detección de ambigüedad / evidencia alternativa.

### Fase 8 — Auditoría

- `AiDecisionEvent` end-to-end en generation/chat/appeal.
- Vista auditor + export CSV/JSON.
- Retención y PII policy.

### Fase 9 — Hardening

- Load tests retrieval/chat.
- Cost guards, rate limits, abuse on appeals.
- Accessibility, i18n coverage, observability SLO.

---

## Dependencias críticas (grafo)

```
F1 → F2 → F3 → F5 → F6 → F7
         ↘ F4
         ↘ F8 (inicia en paralelo desde F3)
                    F9 ← all
```

---

## Hitos de negocio

| Hito | Valor |
|---|---|
| H1 Evidencia en resultados | Trust estudiante |
| H2 Chat grounded | Engagement / estudio |
| H3 Apelaciones B2B | Compliance sales |
| H4 Teacher AI + Audit | Diferenciación enterprise |
