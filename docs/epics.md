# Épicas — Evaluación inteligente QuizDock

| ID | Nombre | Prioridad | Estado | Dependencias | Responsable sugerido | Fecha objetivo |
|---|---|---|---|---|---|---|
| E1 | Sistema de Evidencia Documental | P0 | Ready | E0-RAG (Fase 2) | Tech Lead + AI Eng | Fase 3 |
| E2 | Chat con Documentos | P0 | Ready | Fase 2 RAG | AI Eng + Frontend | Fase 4 |
| E3 | Apelaciones Académicas | P0 | Ready | E1 | Backend + PM | Fase 5 |
| E4 | Comunicación Profesor–Alumno | P1 | Ready | E3 | Backend + UX | Fase 6 |
| E5 | Asistente IA para Profesores | P1 | Ready | E3, E1 | AI Eng | Fase 7 |
| E6 | Auditoría y Explainability | P0 | Ready | E1 (+ paralelo) | Backend + Auditoría | Fase 8 |

---

## E1 — Sistema de Evidencia Documental

**Descripción:** Materializar y mostrar la evidencia documental que justifica cada respuesta correcta: fragmento, página, capítulo, documento, confianza, fecha y fuente.

**Outcome:** El estudiante entiende *por qué* y *desde dónde* se evalúa.

**Alcance:** CitationEngine, QuestionEvidence, AnswerReference, EvidencePanel, APIs de lectura, generación con evidencia.

**Fuera de alcance:** Chat, apelaciones.

---

## E2 — Chat con Documentos

**Descripción:** Agente conversacional grounded solo en el documento origen, con citas obligatorias y refusals.

**Outcome:** Estudio activo post-examen sin alucinaciones.

---

## E3 — Apelaciones Académicas

**Descripción:** Flujo formal para cuestionar una calificación incorrecta, con estados, evidencia y resolución humana.

**Outcome:** Confianza académica y canal de disputa auditable.

---

## E4 — Comunicación Profesor–Alumno

**Descripción:** Hilo de comentarios/adjuntos ligado a cada apelación, con notificaciones e historial.

**Outcome:** Colaboración asíncrona hasta resolución.

---

## E5 — Asistente IA para Profesores

**Descripción:** Análisis no vinculante de apelaciones con recomendación, confianza y justificación basada en evidencia comparada.

**Outcome:** Reducir tiempo de revisión docente sin ceder autoridad.

---

## E6 — Auditoría y Explainability

**Descripción:** Registro completo de decisiones IA (documento, chunk, prompt/modelo, scores, outcome) + vistas de auditoría.

**Outcome:** Cumplimiento B2B y debugging de calidad.
