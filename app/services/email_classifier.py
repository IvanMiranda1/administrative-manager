"""
Puerto del clasificador de emails. El resto del sistema (email_adapter,
el endpoint) solo conoce esta interfaz -- no sabe ni le importa si
adentro hay reglas de keywords o una llamada a Gemini. Cambiar la
implementación (ver rule_based_classifier.py -> un futuro
gemini_classifier.py) no debería requerir tocar nada fuera de este
archivo y de dónde se inyecta la instancia concreta.
"""
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass
class ClassificationProposal:
    item_type: str
    confidence: float
    invoice_provider_name: str | None = None
    invoice_number: str | None = None
    deadline_due_date: date | None = None


class EmailClassifier(Protocol):
    def classify(self, *, subject: str, body: str, sender_domain: str | None) -> ClassificationProposal: ...
