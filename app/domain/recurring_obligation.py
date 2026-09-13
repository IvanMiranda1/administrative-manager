"""
RecurringObligationConfig: decisión humana previa (ej. "Camuzzi siempre
me manda una factura de gas mensual") que permite que un item nazca
directo PENDING sin pasar por revisión de clasificación -- porque la
confianza no viene de "creerle a la IA", sino de una configuración que
ya validó una persona.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RecurringObligationConfig:
    id: str
    provider_name: str
    item_type: str
    active: bool = True
    created_at: datetime = None  # type: ignore[assignment]

    @classmethod
    def create(cls, *, provider_name: str, item_type: str) -> "RecurringObligationConfig":
        if not provider_name.strip():
            raise ValueError("provider_name no puede estar vacío")
        return cls(
            id=str(uuid.uuid4()),
            provider_name=provider_name,
            item_type=item_type,
            active=True,
            created_at=datetime.now(),
        )

    def matches(self, provider_name: str, item_type: str) -> bool:
        if not self.active:
            return False
        return (
            self.provider_name.strip().lower() == provider_name.strip().lower()
            and self.item_type == item_type
        )
