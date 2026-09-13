"""
AIClassification: entidad separada del AdministrativeItem, con su propio
ciclo de vida. Guarda qué propuso la clasificación automática y qué
confirmó/corrigió finalmente un humano, junto con el texto original --
sin el texto original, no hay con qué reentrenar después (falta la
entrada, no solo la etiqueta).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AIClassification:
    id: str
    administrative_item_id: str
    source_subject: str
    source_body: str
    proposed_item_type: str
    proposed_confidence: float
    proposed_data: dict  # invoice_provider_name, invoice_number, deadline_due_date, etc.
    created_at: datetime
    corrected: bool = False
    corrected_data: dict | None = None
    confirmed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        administrative_item_id: str,
        source_subject: str,
        source_body: str,
        proposed_item_type: str,
        proposed_confidence: float,
        proposed_data: dict,
    ) -> "AIClassification":
        if not administrative_item_id:
            raise ValueError("AIClassification no puede existir sin administrative_item_id")
        return cls(
            id=str(uuid.uuid4()),
            administrative_item_id=administrative_item_id,
            source_subject=source_subject,
            source_body=source_body,
            proposed_item_type=proposed_item_type,
            proposed_confidence=proposed_confidence,
            proposed_data=dict(proposed_data),
            created_at=datetime.now(),
        )

    def confirm(self, confirmed_data: dict) -> None:
        """Un humano revisa la propuesta y confirma (o corrige) los datos."""
        self.corrected_data = dict(confirmed_data)
        self.corrected = self.corrected_data != self.proposed_data
        self.confirmed_at = datetime.now()
