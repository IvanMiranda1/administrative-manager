"""
AdministrativeItem: aggregate root del dominio.

Invariantes que este archivo hace cumplir:
1. No existe sin un Source.
2. No existe sin InvoiceReference cuando el tipo de item lo requiere.
3. El estado inicial depende de la confianza de la clasificación O de que
   matchee una obligación recurrente ya configurada por un humano.
4. Los datos de negocio confirmados no se sobreescriben sin evidencia nueva
   explícita + revisión humana; se guarda un snapshot del dato anterior
   hasta que se confirme el cambio.
5. Ninguna acción con efecto real (ej. pago) se ejecuta sin confirmación
   humana, sin importar la confianza.
6. Los cálculos derivados (antigüedad, urgencia) no son estado: se calculan
   al mostrar, no se guardan como transición.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import ItemStatus
from app.domain.exceptions import (
    ConfirmedDataOverwriteError,
    InvalidTransitionError,
    UnsafeActionError,
)
from app.domain.value_objects import ConfidenceLevel, Deadline, InvoiceReference, Source

# Tipos de item que necesariamente requieren poder correlacionarse con una
# obligación de negocio (para poder detectar "esto ya existe" o "esto lo
# corrige"). Se puede ampliar a medida que aparezcan más tipos.
TYPES_REQUIRING_CORRELATION = {"invoice"}

# Transiciones válidas: estado actual -> conjunto de estados a los que puede ir.
_ALLOWED_TRANSITIONS: dict[ItemStatus, set[ItemStatus]] = {
    ItemStatus.NEEDS_REVIEW: {ItemStatus.PENDING, ItemStatus.CANCELLED},
    ItemStatus.PENDING: {
        ItemStatus.WAITING,
        ItemStatus.NEEDS_REVIEW,
        ItemStatus.COMPLETED,
        ItemStatus.CANCELLED,
    },
    ItemStatus.WAITING: {ItemStatus.PENDING, ItemStatus.CANCELLED},
    ItemStatus.COMPLETED: set(),
    ItemStatus.CANCELLED: set(),
}


@dataclass
class AdministrativeItem:
    id: str
    source: Source
    item_type: str
    confidence: ConfidenceLevel
    status: ItemStatus
    invoice_reference: InvoiceReference | None = None
    deadline: Deadline | None = None

    # Datos de negocio ya confirmados por un humano (o aceptados de alta
    # confianza). Una vez presentes, no se pisan salvo por el flujo de
    # nueva evidencia.
    confirmed_data: dict = field(default_factory=dict)

    # Snapshot del dato viejo mientras se espera confirmación de un cambio
    # traído por nueva evidencia. Se descarta al confirmar.
    pending_evidence_snapshot: dict | None = None

    # -----------------------------------------------------------------
    # Creación
    # -----------------------------------------------------------------
    @classmethod
    def create(
        cls,
        *,
        source: Source,
        item_type: str,
        confidence: ConfidenceLevel,
        proposed_data: dict,
        invoice_reference: InvoiceReference | None = None,
        deadline: Deadline | None = None,
        matches_configured_recurring_obligation: bool = False,
    ) -> "AdministrativeItem":
        # Invariante 1: Source obligatorio (el tipo ya lo exige, pero
        # validamos explícitamente por si alguien pasa None a propósito).
        if source is None:
            raise ValueError("AdministrativeItem no puede crearse sin Source")

        # Invariante 2: correlación de negocio obligatoria para ciertos tipos.
        if item_type in TYPES_REQUIRING_CORRELATION and invoice_reference is None:
            raise ValueError(
                f"Los items de tipo '{item_type}' requieren un InvoiceReference"
            )

        # Invariante 3: estado inicial según confianza de IA o match con
        # obligación recurrente ya configurada por un humano.
        starts_actionable = confidence.is_high or matches_configured_recurring_obligation
        initial_status = ItemStatus.PENDING if starts_actionable else ItemStatus.NEEDS_REVIEW

        return cls(
            id=str(uuid.uuid4()),
            source=source,
            item_type=item_type,
            confidence=confidence,
            status=initial_status,
            invoice_reference=invoice_reference,
            deadline=deadline,
            # Si nace directamente accionable, los datos propuestos ya se
            # consideran confirmados (por la config recurrente o la alta
            # confianza); si no, quedan afuera de confirmed_data hasta que
            # un humano los revise.
            confirmed_data=dict(proposed_data) if starts_actionable else {},
        )

    # -----------------------------------------------------------------
    # Transiciones
    # -----------------------------------------------------------------
    def _transition_to(self, new_status: ItemStatus) -> None:
        allowed = _ALLOWED_TRANSITIONS[self.status]
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"No se puede pasar de {self.status.value} a {new_status.value}"
            )
        self.status = new_status

    def confirm(self, confirmed_data: dict) -> None:
        """Un humano revisa NEEDS_REVIEW y confirma (o corrige) los datos."""
        if self.status != ItemStatus.NEEDS_REVIEW:
            raise InvalidTransitionError(
                "Solo se puede confirmar un item en estado NEEDS_REVIEW"
            )
        self.confirmed_data = dict(confirmed_data)
        self._transition_to(ItemStatus.PENDING)

    def mark_waiting(self) -> None:
        """Marca manual: este item depende de que otra persona actúe."""
        self._transition_to(ItemStatus.WAITING)

    def resume_from_waiting(self) -> None:
        self._transition_to(ItemStatus.PENDING)

    def receive_new_evidence(self, new_data: dict) -> None:
        """
        Llega evidencia nueva y explícita (ej. nota de crédito) que
        contradice datos ya confirmados. Invariante 4: no se pisa
        directamente -- se guarda un snapshot y el item vuelve a revisión.
        """
        if self.status != ItemStatus.PENDING:
            raise InvalidTransitionError(
                "Solo se puede recibir evidencia nueva sobre un item PENDING"
            )
        self.pending_evidence_snapshot = dict(self.confirmed_data)
        self.confirmed_data = dict(new_data)
        self._transition_to(ItemStatus.NEEDS_REVIEW)

    def confirm_evidence_update(self, confirmed_data: dict) -> None:
        """
        Un humano revisa el cambio traído por evidencia nueva y lo
        confirma. Recién acá se descarta el snapshot del dato viejo.
        """
        if self.pending_evidence_snapshot is None:
            raise ConfirmedDataOverwriteError(
                "No hay un cambio de evidencia pendiente de confirmar"
            )
        self.confirmed_data = dict(confirmed_data)
        self.pending_evidence_snapshot = None
        self._transition_to(ItemStatus.PENDING)

    def complete(self) -> None:
        self._transition_to(ItemStatus.COMPLETED)

    def cancel(self) -> None:
        self._transition_to(ItemStatus.CANCELLED)

    # -----------------------------------------------------------------
    # Invariante 5: acciones con efecto real
    # -----------------------------------------------------------------
    def execute_action_with_real_effect(self) -> None:
        """
        Punto único por el que debería pasar cualquier acción irreversible
        (pagar, enviar dinero, aprobar algo definitivo). Nunca se salta la
        confirmación humana, sin importar cuán alta sea la confianza.
        """
        if self.status != ItemStatus.PENDING:
            raise UnsafeActionError(
                "Solo se pueden ejecutar acciones reales sobre items PENDING"
            )
        if not self.confirmed_data:
            raise UnsafeActionError(
                "No se puede ejecutar una acción real sin datos confirmados "
                "por un humano, sin importar la confianza"
            )

    # -----------------------------------------------------------------
    # Invariante 6: cálculos derivados (no son estado, no se guardan)
    # -----------------------------------------------------------------
    def is_overdue(self, as_of: datetime | None = None) -> bool:
        if self.deadline is None:
            return False
        reference_date = as_of.date() if as_of else None
        return self.deadline.is_overdue(reference_date)
