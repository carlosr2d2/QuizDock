# Backlog priorizado — Evaluación inteligente

Ordenado por valor + dependencias técnicas. Story points totales ~ **~130 SP** (orden de magnitud).

---

## Sprint 0 — Cierre de planificación (Fase 1)

| Tipo | Ítem | Pri | Estado |
|---|---|---|---|
| Doc | Assessment funcional / técnico | P0 | Done (docs) |
| Doc | Arquitectura + dominio + roadmap | P0 | Done (docs) |
| Doc | Épicas + user stories + plan | P0 | Done (docs) |
| PM | Notion DBs + seed | P0 | In progress |
| ADR | Borradores ADR-E01…E06 | P1 | Pending |

---

## Now (Fase 2 — RAG)

1. US-RAG-02 — page/chapter metadata en chunks  
2. US-RAG-01 — semantic retrieve cableado  
3. Hybrid retrieval en generación (mantener diversity)  
4. Reindex job + embedding_model en chunks  
5. US-RAG-03 — rerank v0  
6. Métricas citation coverage (logs)

---

## Next (Fase 3 — Evidencias)

1. US-E1-03 materializar QuestionEvidence  
2. US-E1-04 AnswerReference snapshot  
3. US-E1-01 / US-E1-02 EvidencePanel UI  
4. US-E1-05 degradación página  
5. US-E1-06 evidencia para profesor  
6. Backfill best-effort

---

## Later (Fases 4–8)

**F4 Chat:** US-E2-01…05  
**F5 Appeals:** US-E3-01…06  
**F6 Messaging:** US-E4-01…03  
**F7 Teacher AI:** US-E5-01…03  
**F8 Audit:** US-E6-01…03  

---

## Icebox

- Ajuste automático de score al aceptar apelación (v2).  
- Chat multimodal (figuras PDF).  
- Vector store externo.  
- Rol `instructor` separado de admin.  
- Impugnación en preguntas correctas (rare).  

---

## Definition of Ready

- Historia con AC testables  
- Dependencias técnicas claras  
- Tenancy/RBAC anotados  
- Estimación SP  
- Diseño API/UI mínimo  

## Definition of Done

- Migración Alembic si schema  
- Tests API unitarios en verde (`pytest`)  
- i18n si UI  
- Observabilidad básica (log/event)  
- Sin lógica en router/UI  
- Docs ADR si decisión arquitectónica nueva  
