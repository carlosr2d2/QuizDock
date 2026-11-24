# Historias de usuario — Evaluación inteligente

**Formato:** Como… quiero… para…  
**Prioridad:** P0/P1/P2 · **SP:** Fibonacci estimado

---

## Epic E1 — Evidencia documental

| ID | Historia | Criterios de aceptación | Épica | Pri | SP |
|---|---|---|---|---|---|
| US-E1-01 | Como estudiante, quiero ver el fragmento del documento que justifica la respuesta correcta tras mi intento, para entender el error. | Dado un intento completado con evidencia; cuando abro el resultado; entonces veo quote, documento, página (o “N/D”), capítulo/sección si hay, confianza %, fecha. | E1 | P0 | 5 |
| US-E1-02 | Como estudiante, quiero ver mi respuesta vs la correcta junto a la justificación IA y la evidencia, en un solo bloque. | Panel unificado bajo cada pregunta del resultado; i18n ES/EN. | E1 | P0 | 3 |
| US-E1-03 | Como sistema, quiero persistir QuestionEvidence al generar preguntas, para no depender solo del chunk mutable. | Generación crea evidence con chunk_id, quote verificado, scores, model, generated_at. | E1 | P0 | 8 |
| US-E1-04 | Como auditor, quiero que AnswerReference sea un snapshot del intento, para auditar lo que vio el alumno. | Submit attempt copia snapshot; reindex no altera snapshots previos. | E1 | P0 | 5 |
| US-E1-05 | Como estudiante, si no hay página disponible, quiero un mensaje honesto, no un número inventado. | page null → copy “Página no disponible”; no alucinar. | E1 | P0 | 2 |
| US-E1-06 | Como profesor, quiero ver la misma evidencia al revisar el intento de un alumno. | AttemptRead con evidence visible a roles autorizados. | E1 | P1 | 3 |

---

## Epic E2 — Chat documental

| ID | Historia | Criterios de aceptación | Épica | Pri | SP |
|---|---|---|---|---|---|
| US-E2-01 | Como estudiante, quiero preguntar al documento del examen (“explícame este concepto”) y recibir respuesta con citas. | Respuesta incluye ≥1 citation con fragmento y referencia; o refusal. | E2 | P0 | 8 |
| US-E2-02 | Como estudiante, quiero preguntar por qué mi respuesta fue incorrecta con contexto del intento. | Chat acepta exam_id/question_id opcional; usa evidence + chunks. | E2 | P0 | 5 |
| US-E2-03 | Como estudiante, quiero que el chat diga cuando el documento no contiene la respuesta. | refusal=true + mensaje claro; sin inventar. | E2 | P0 | 3 |
| US-E2-04 | Como estudiante, quiero historial de la conversación con el documento. | List messages ordenados; persistidos por org/user/doc. | E2 | P1 | 3 |
| US-E2-05 | Como org admin, quiero que el chat consuma créditos / límites. | Débito o rate limit configurado; 402/429 claros. | E2 | P1 | 5 |

---

## Epic E3 — Apelaciones

| ID | Historia | Criterios de aceptación | Épica | Pri | SP |
|---|---|---|---|---|---|
| US-E3-01 | Como estudiante, quiero iniciar una apelación desde una pregunta incorrecta con comentario. | CTA “No estoy de acuerdo”; crea AppealCase pending con snapshots. | E3 | P0 | 5 |
| US-E3-02 | Como estudiante, quiero adjuntar un fragmento distinto del documento como evidencia. | Selector/highlighter → AppealEvidence source=student. | E3 | P0 | 8 |
| US-E3-03 | Como estudiante, quiero ver el estado de mis apelaciones. | Lista con estados; detalle con historial. | E3 | P0 | 3 |
| US-E3-04 | Como profesor, quiero una bandeja de apelaciones filtrable. | Filtro por status; solo org actual. | E3 | P0 | 5 |
| US-E3-05 | Como profesor, quiero cambiar estado (in_review, needs_info) y emitir resolución. | State machine validada; resolution + notify. | E3 | P0 | 8 |
| US-E3-06 | Como sistema, quiero notificar al profesor al crear apelación. | Email o evento; no bloquea HTTP. | E3 | P1 | 3 |

---

## Epic E4 — Comunicación

| ID | Historia | Criterios de aceptación | Épica | Pri | SP |
|---|---|---|---|---|---|
| US-E4-01 | Como estudiante/profesor, quiero comentar en el hilo de la apelación. | Comentarios ordenados; autor visible; RBAC. | E4 | P0 | 5 |
| US-E4-02 | Como usuario, quiero adjuntar archivos al comentario. | Upload storage_key; tipos permitidos; tamaño max. | E4 | P1 | 5 |
| US-E4-03 | Como usuario, quiero notificación cuando hay nuevo comentario. | Mail/async; preferencias básicas. | E4 | P1 | 3 |

---

## Epic E5 — Asistente IA profesor

| ID | Historia | Criterios de aceptación | Épica | Pri | SP |
|---|---|---|---|---|---|
| US-E5-01 | Como profesor, quiero una recomendación IA (aceptar/rechazar/needs_info) con confianza y justificación. | Job async; UI muestra suggestion; no aplica resolución sola. | E5 | P0 | 8 |
| US-E5-02 | Como profesor, quiero ver evidencia del sistema vs del estudiante lado a lado. | UI split compare + chunks. | E5 | P0 | 5 |
| US-E5-03 | Como profesor, quiero que la IA detecte ambigüedad / múltiples lecturas válidas. | Rationale menciona ambigüedad cuando aplique; test con fixture. | E5 | P1 | 5 |

---

## Epic E6 — Auditoría

| ID | Historia | Criterios de aceptación | Épica | Pri | SP |
|---|---|---|---|---|---|
| US-E6-01 | Como auditor, quiero ver eventos de decisión IA con modelo, chunks, scores y outcome. | List/filter AiDecisionEvent por org; payload completo. | E6 | P0 | 8 |
| US-E6-02 | Como auditor, quiero exportar el log de una apelación / intento. | Export JSON; incluye evidence + actions. | E6 | P1 | 5 |
| US-E6-03 | Como sistema, quiero registrar prompt hash / modelo en generación, chat y appeal review. | Evento creado en cada feature path. | E6 | P0 | 5 |

---

## Infra transversal (Fase 2)

| ID | Historia | Criterios | Épica | Pri | SP |
|---|---|---|---|---|---|
| US-RAG-01 | Como sistema, quiero recuperar chunks por similitud semántica al generar y chatear. | `similar` + `embed_query` usados; tests. | E1/E2 | P0 | 5 |
| US-RAG-02 | Como sistema, quiero metadata de página/capítulo en chunks cuando el PDF lo permita. | Campos poblados en process; degradación documentada. | E1 | P0 | 8 |
| US-RAG-03 | Como sistema, quiero re-rankear candidatos antes de citar. | Interfaz Reranker; al menos Noop + scoring cosine. | E2 | P1 | 5 |
