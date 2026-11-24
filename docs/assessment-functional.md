# Assessment funcional — Evaluación inteligente, explicable y auditable

**Producto:** QuizDock  
**Fecha:** 2026-11-24  
**Alcance:** Funcionalidades 1–7 (evidencia, chat documental, apelaciones, mensajería, asistente IA profesor, impugnación por evidencia, auditoría)  
**Estado:** Assessment completo — **sin implementación de código**

---

## 1. Resumen ejecutivo

QuizDock ya genera exámenes y flashcards a partir de documentos, califica intentos y muestra una explicación textual. **No** ofrece evidencia documental verificable (página/capítulo/fragmento), chat grounded con el documento, apelaciones académicas, hilos profesor–estudiante, recomendaciones IA para resolución, ni auditoría de decisiones de modelo.

El salto de producto es pasar de “evaluación generada por IA” a **evaluación defendible**: cada respuesta correcta debe poder justificarse con cita verificable; cada desacuerdo debe poder argumentarse con evidencia alternativa; cada decisión de sistema debe ser reconstruible.

---

## 2. Personas y jobs-to-be-done

| Persona | Job principal | Dolor actual |
|---|---|---|
| Estudiante (B2C / miembro B2B) | Entender por qué falló y estudiar el fragmento real | Solo ve explicación libre; no ve página ni cita |
| Estudiante | Cuestionar una calificación injusta | No hay canal formal de apelación |
| Profesor / admin | Resolver disputas con criterio y evidencia | No hay bandeja, comparación de evidencias ni ayuda IA |
| Auditor / compliance B2B | Demostrar trazabilidad académica | Audit log actual solo cubre acciones de equipo/org |
| Producto | Diferenciarse en EdTech B2B | Explicabilidad y auditabilidad son el moat |

---

## 3. Estado actual del producto (funcional)

### Existe hoy

- Subida y procesamiento de PDF (estado `uploaded → processing → ready|failed`).
- Generación asíncrona de exámenes/quizzes y flashcards (Celery + créditos).
- Preguntas con `explanation` y vínculo débil `source_chunk_position`.
- Intento, scoring, historial de intentos, asignación a usuarios/grupos.
- Vista de resultado: correcta/incorrecta + explicación (sin evidencia).
- Progress personal, analytics de equipo, audit de acciones administrativas.
- Multitenancy + RBAC (`owner`, `admin`, `member`, `auditor`).

### No existe hoy

| Capacidad | Gap |
|---|---|
| Evidencia documental en revisión | Sin fragmento, página, capítulo, confianza, fecha de generación de evidencia |
| Citation viewer | UI no expone chunk ni documento origen por pregunta |
| Chat con documento | Sin agente, historial ni grounding obligatorio |
| Apelaciones | Sin estados, comentarios, adjuntos ni resolución |
| Mensajería en apelación | Sin hilos profesor–alumno |
| Asistente IA para profesor | Sin análisis comparativo ni recomendación no vinculante |
| Impugnación por selección de fragmento | Sin UI de highlight / attach chunk |
| Audit de IA | Sin prompt, modelo, scores, chunk usado por decisión |

---

## 4. Requerimientos funcionales por épica

### Epic 1 — Sistema de Evidencia Documental

**Objetivo:** Al revisar una pregunta, el estudiante ve respuesta propia, correcta, justificación IA y evidencia con referencia completa.

**Debe mostrar**

- Respuesta del estudiante / respuesta correcta / explicación IA.
- Fragmento textual exacto usado.
- Documento, página, capítulo/sección (cuando exista metadata).
- Nivel de confianza de la evidencia.
- Fecha de generación de la evidencia / fuente de evaluación.

**Criterios de aceptación (alto nivel)**

1. Toda pregunta generada con documento debe poder resolver al menos una `QuestionEvidence` con chunk y metadata mínima.
2. En `AttemptRead` / UI de resultado, la evidencia es visible tras completar el intento (no durante el examen).
3. Si no hay metadata de página, el sistema muestra “página no disponible” sin inventar números.
4. Confianza se calcula o persiste de forma determinista y se muestra como porcentaje.

### Epic 2 — Chat con Documentos

**Objetivo:** Conversar con el documento origen del examen, solo con evidencia citada.

**Casos de uso:** explicar concepto, por qué fallé, dónde aparece un tema, más ejemplos, resumen de capítulo.

**Restricciones no negociables**

- Respuestas grounded en chunks recuperados.
- Siempre citar documento, página/capítulo cuando existan, y fragmento.
- Si no hay evidencia suficiente → mensaje explícito de insuficiencia (no alucinar).

### Epic 3 — Apelaciones Académicas

**Flujo:** revisar → ver evidencia → “No estoy de acuerdo” → comentario → adjuntar evidencia → enviar → notificar profesor → revisión → resolución.

**Estados:** `pending` | `in_review` | `needs_info` | `accepted` | `rejected` | `closed`.

### Epic 4 — Comunicación Profesor–Alumno

Hilo ligado a `AppealCase`: comentarios, adjuntos, evidencias, notificaciones, historial auditable.

### Epic 5 — Asistente IA para Profesores

Analiza apelación + pregunta + documento + ambas evidencias; detecta ambigüedad / múltiples interpretaciones válidas; recomienda resolución **no vinculante** con confianza y justificación.

### Epic 6 — Auditoría y Explainability

Registro obligatorio de: documento, chunk, página, evidencia, prompt, modelo, usuario, fecha, resultado, confidence, relevance.

---

## 5. Experiencia de usuario (objetivos)

### Estudiante

- Vista de evidencia en resultado de intento.
- Chat contextual al documento del examen.
- Crear / seguir / historial de apelaciones.
- Selector de fragmento para impugnar.

### Profesor / admin

- Bandeja de apelaciones filtrable por estado.
- Centro de revisión con evidencia comparada (sistema vs estudiante).
- Panel de recomendación IA (aceptar / rechazar / needs_info) + confianza.
- Estadísticas de apelaciones y auditoría de decisiones.

### Principios UX (alineados al design system existente)

- Extender el flujo de resultado de examen actual; no inventar un segundo producto.
- Evidencia como bloque claro bajo cada pregunta incorrecta (y opcional en correctas).
- Chat como panel lateral o ruta hija del documento/examen, no chat genérico sin contexto.
- Apelación: wizard corto (3 pasos) para reducir fricción.
- Profesor: bandeja tipo “inbox”, no dashboard sobrecargado.

---

## 6. Reglas pedagógicas

1. La evidencia debe ser **literalmente recuperable** del documento (substring o chunk id).
2. La explicación IA no sustituye la cita; es interpretación anclada.
3. Apelación aceptada no implica “IA equivocada” siempre: puede haber múltiples lecturas válidas.
4. El profesor es autoridad final; la IA es copiloto.
5. En B2C personal, el “profesor” puede ser el dueño del workspace o un revisor designado; el modelo de apelación debe funcionar también en org B2B con roles.

---

## 7. Alcance B2C vs B2B

| Capacidad | B2C | B2B |
|---|---|---|
| Evidencia en resultados | Sí | Sí |
| Chat documental | Sí (créditos) | Sí (política org) |
| Apelaciones | Opcional / self-review | Core compliance |
| Mensajería | Menor valor | Core |
| Asistente IA profesor | Nice-to-have | Differentiator |
| Audit AI | Básico | Obligatorio / exportable |

Un solo modelo de tenancy: `organization_id` en todas las entidades nuevas.

---

## 8. Dependencias funcionales

```
RAG metadata + semantic retrieve
        ↓
Evidencia en preguntas / intentos
        ↓
Chat grounded + Apelaciones + Impugnación
        ↓
Mensajería + Asistente IA profesor
        ↓
Audit / Explainability completo
```

Sin infraestructura RAG enriquecida, evidencia y chat serán frágiles.

---

## 9. Riesgos de producto

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Expectativa de “página exacta” en PDFs mal parseados | Confianza del usuario | Metadata honestidad + UX de degradación |
| Chat que alucina a pesar de grounding | Integridad académica | Fail-closed + citas obligatorias + tests |
| Apelaciones masivas / abuso | Carga docente | Rate limits, créditos, umbral de apelación |
| Profesor ignora recomendación IA (o al revés) | UX / liability | Copy claro: “sugerencia no vinculante” |
| Complejidad UX en resultado de examen | Abandono | Progressive disclosure |

---

## 10. Oportunidades

- Moat B2B: evaluación auditable para compliance / onboarding.
- Upsell: chat y apelaciones con IA como features de planes superiores.
- Mejora de calidad de generación: forzar grounding reduce preguntas “inventadas”.
- Datos de apelaciones → feedback loop para mejorar blueprints y prompts.

---

## 11. Definición de “listo” del assessment funcional

- [x] Personas y JTBD claros
- [x] Gaps vs estado actual
- [x] Épicas y criterios de alto nivel
- [x] UX objectives
- [x] Reglas pedagógicas
- [x] Riesgos y oportunidades
- [ ] Implementación — **bloqueada hasta completar plan + ADRs**

**Veredicto:** el producto actual es una base sólida de assessment generation; la iniciativa es un **cambio de categoría** (explicable + auditable), no un parche UI.
