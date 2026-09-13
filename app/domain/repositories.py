"""
Puerto del repository. El dominio define QUÉ necesita (guardar, buscar
por id, buscar por source_reference para detectar duplicados) sin saber
CÓMO se implementa. La implementación concreta vive en infrastructure/.
"""
from typing import Protocol

from app.domain.administrative_item import AdministrativeItem
from app.domain.ai_classification import AIClassification
from app.domain.recurring_obligation import RecurringObligationConfig


class AdministrativeItemRepository(Protocol):
    def add(self, item: AdministrativeItem) -> None: ...

    def save(self, item: AdministrativeItem) -> None:
        """Persiste cambios sobre un item ya existente (upsert)."""
        ...

    def get_by_id(self, item_id: str) -> AdministrativeItem | None: ...

    def get_by_source_reference(self, reference: str) -> AdministrativeItem | None: ...

    def list_all(self) -> list[AdministrativeItem]: ...


class AIClassificationRepository(Protocol):
    def add(self, classification: AIClassification) -> None: ...

    def save(self, classification: AIClassification) -> None: ...

    def get_by_item_id(self, item_id: str) -> AIClassification | None: ...


class RecurringObligationConfigRepository(Protocol):
    def add(self, config: RecurringObligationConfig) -> None: ...

    def find_match(self, provider_name: str, item_type: str) -> RecurringObligationConfig | None: ...

    def list_all(self) -> list[RecurringObligationConfig]: ...
