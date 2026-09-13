# Sistema de responsabilidades administrativas — Semana 3

Dominio (Semana 1) + persistencia SQLite (Semana 2) + clasificación
automática y confirmación humana (Semana 3). El clasificador es
"falso" (reglas por palabras clave, sin costo ni API keys) pero
implementa el mismo puerto (`EmailClassifier`) que va a usar un
clasificador real con Gemini más adelante, sin tocar el resto del
sistema.

## Cómo correrlo

```bash
python3 -m venv venv
source venv/bin/activate       # en Windows: venv\Scripts\activate
pip install -r requirements.txt

# Correr los tests del dominio
pytest tests/ -v

# Levantar el servidor
uvicorn app.main:app --reload
# Probar en el navegador: http://localhost:8000/health
```

## Qué hay hasta ahora

- `app/domain/value_objects.py` — `Source`, `InvoiceReference`,
  `ConfidenceLevel`, `Deadline`.
- `app/domain/enums.py` — estados del item (`ItemStatus`).
- `app/domain/exceptions.py` — errores de dominio, uno por invariante.
- `app/domain/administrative_item.py` — el aggregate root, con las 6
  invariantes y las transiciones de estado documentadas en el docstring
  del archivo.
- `tests/test_administrative_item.py` — 20 tests, uno o más por cada
  invariante y transición.
- `app/services/email_classifier.py` — puerto `EmailClassifier` (Protocol)
  + `ClassificationProposal`. La interfaz que cualquier clasificador real
  (Gemini, OpenAI, lo que sea) tiene que cumplir.
- `app/services/rule_based_classifier.py` — implementación falsa por
  palabras clave. Sin costo, sin API key, prueba toda la arquitectura.
- `app/domain/ai_classification.py` — entidad `AIClassification`: guarda
  qué propuso el clasificador vs. qué confirmó/corrigió un humano, junto
  con el texto original del email (necesario para reentrenar después).
- `app/domain/recurring_obligation.py` — entidad `RecurringObligationConfig`:
  decisión humana previa que permite que un item nazca `PENDING` sin
  revisión, aunque la confianza de la clasificación sea baja.
- `app/main.py` — nuevos endpoints: `PATCH /items/{id}/confirm`,
  `POST /recurring-obligations`, `GET /recurring-obligations`.
- `tests/test_rule_based_classifier.py`, `tests/test_ai_classification.py`
  — 17 tests nuevos, 50 en total.

## Bug real que encontramos esta semana (dejado documentado a propósito)

La regex original de número de factura matcheaba la letra "n" suelta
dentro de cualquier palabra (ej. "**ve*n*cimiento**"), generando números
de factura falsos. Se corrigió exigiendo marcadores completos (`N°`,
`Nº`, `Nro`, `numero`). El test que lo detectó:
`test_email_factura_sin_numero_extraible_devuelve_422`.

## Limitación conocida de esta semana (a propósito, no es scope creep)

`PATCH /items/{id}/confirm` solo permite corregir `confirmed_data`
(los datos de negocio). No permite cambiar `item_type` ni
`invoice_reference` después de creado -- si la IA clasificó mal el tipo,
hoy no hay forma de corregirlo sin crear el item de nuevo. Queda en el
backlog.

## Invariante nuevo de la Semana 2

**No se duplica un `AdministrativeItem` para el mismo `Source.reference`.**
`source_reference` tiene constraint `unique` en la base, y el repository
chequea antes de insertar. Si llega dos veces el mismo `message_id`,
`POST /emails` devuelve `409 Conflict`.

## Invariantes del aggregate (resumen)

1. No existe sin `Source`.
2. No existe sin `InvoiceReference` cuando el tipo de item lo requiere
   (por ahora solo `"invoice"`).
3. Estado inicial: `PENDING` si alta confianza o matchea una obligación
   recurrente configurada; si no, `NEEDS_REVIEW`.
4. Los datos confirmados no se pisan solos: evidencia nueva guarda un
   snapshot y vuelve a `NEEDS_REVIEW` hasta que un humano confirma.
5. Ninguna acción con efecto real corre sin datos confirmados por un
   humano, sin importar la confianza.
6. Cosas como "está vencido" son cálculos, no estados guardados.

## Explícitamente afuera de esta v1 (backlog)

- Multi-departamento / asignación de responsables.
- Sub-tareas dentro de una responsabilidad (ej. proceso de sueldos).
- Java, en cualquier forma.
- Verificación anti-fraude del remitente (dominio del email, etc.) —
  hoy `Source.sender_domain` solo guarda el dato, no lo valida.
- Persistencia (Semana 2), clasificación con IA (Semana 3), dashboard
  (Semana 4).

## Próximo paso (Semana 4)

Dashboard: un `GET /items` más rico (agrupado por estado, con
antigüedad/urgencia calculada, no guardada) para responder "¿qué necesita
mi atención hoy?".

## Cómo conectar Gemini más adelante (no es de esta semana)

Cuando saques la API key gratis en Google AI Studio, el cambio es
acotado: crear `app/services/gemini_classifier.py` implementando el
mismo `EmailClassifier` Protocol, y cambiar una sola línea en
`app/main.py` (`classifier = RuleBasedEmailClassifier()` →
`classifier = GeminiEmailClassifier(api_key=...)`). Nada más debería
necesitar cambiar -- si necesitás tocar otra cosa, es una señal de que
el puerto no quedó bien diseñado.
