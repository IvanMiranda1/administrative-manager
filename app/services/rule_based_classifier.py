"""
Implementación "falsa" del EmailClassifier: reglas simples por palabras
clave. Sirve para probar toda la arquitectura (dominio, persistencia,
endpoints) sin necesitar ninguna API key. La idea es que
gemini_classifier.py (cuando lo agreguemos) implemente exactamente el
mismo Protocol y sea un reemplazo directo, sin tocar el resto.
"""
import re
from datetime import date

from app.services.email_classifier import ClassificationProposal

INVOICE_KEYWORDS = ["factura", "vencimiento", "pago", "monto", "invoice"]
REQUEST_KEYWORDS = ["revisar", "aprobar", "aprobación", "presupuesto", "solicitud"]

# Busca marcadores reales como "N°", "Nº", "Nro:", "numero" -- a
# propósito NO acepta una "n" suelta (por eso el \b y los marcadores
# completos), porque una versión más permisiva terminaba "detectando"
# un número de factura adentro de la palabra "vencimiento".
INVOICE_NUMBER_PATTERN = re.compile(
    r"\b(?:n°|nº|nro\.?|numero|n[uú]mero)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]{2,20})",
    re.IGNORECASE,
)

# Solo fechas en formato dd/mm o dd/mm/yyyy -- fechas en texto
# ("15 de septiembre") quedan fuera de esta versión simple, a propósito.
DATE_PATTERN = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")


class RuleBasedEmailClassifier:
    def classify(self, *, subject: str, body: str, sender_domain: str | None) -> ClassificationProposal:
        text = f"{subject} {body}".lower()

        invoice_matches = sum(1 for kw in INVOICE_KEYWORDS if kw in text)
        request_matches = sum(1 for kw in REQUEST_KEYWORDS if kw in text)

        if invoice_matches > 0 and invoice_matches >= request_matches:
            item_type = "invoice"
            confidence = 0.9 if invoice_matches >= 2 else 0.4
        else:
            item_type = "request"
            confidence = 0.9 if request_matches >= 2 else 0.4

        invoice_provider_name = None
        invoice_number = None
        deadline_due_date = None

        if item_type == "invoice":
            invoice_provider_name = self._provider_name_from_domain(sender_domain)
            invoice_number = self._extract_invoice_number(f"{subject} {body}")
            deadline_due_date = self._extract_deadline(f"{subject} {body}")

        return ClassificationProposal(
            item_type=item_type,
            confidence=confidence,
            invoice_provider_name=invoice_provider_name,
            invoice_number=invoice_number,
            deadline_due_date=deadline_due_date,
        )

    @staticmethod
    def _provider_name_from_domain(sender_domain: str | None) -> str | None:
        if not sender_domain:
            return None
        # "camuzzi.com.ar" -> "Camuzzi"
        first_part = sender_domain.split(".")[0]
        return first_part.capitalize() if first_part else None

    @staticmethod
    def _extract_invoice_number(text: str) -> str | None:
        match = INVOICE_NUMBER_PATTERN.search(text)
        return match.group(1) if match else None

    @staticmethod
    def _extract_deadline(text: str) -> date | None:
        match = DATE_PATTERN.search(text)
        if not match:
            return None
        day, month, year_raw = match.groups()
        year = int(year_raw) if year_raw else date.today().year
        if year < 100:
            year += 2000
        try:
            return date(year, int(month), int(day))
        except ValueError:
            return None
