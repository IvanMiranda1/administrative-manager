"""
Value objects del dominio administrativo.

Un value object no tiene identidad propia: dos instancias con los mismos
datos son intercambiables. Por eso son inmutables (frozen=True) y validan
sus propias reglas al crearse, en vez de dejar que un dato "crudo" (str,
float, datetime) circule sin garantías por el resto del sistema.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class SourceType(str, Enum):
    EMAIL = "email"
    MANUAL = "manual"
    RECURRING_RULE = "recurring_rule"
    EXTERNAL_SYSTEM = "external_system"


@dataclass(frozen=True)
class Source:
    """De dónde vino la información. Todo AdministrativeItem debe tener uno."""

    type: SourceType
    reference: str  # ej: message-id del email, nombre de la regla recurrente
    received_at: datetime
    sender_domain: str | None = None  # útil para chequeos de verificación futuros

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("Source.reference no puede estar vacío")


@dataclass(frozen=True)
class InvoiceReference:
    """
    Identifica una obligación de negocio de forma estable, independiente
    de por qué canal haya llegado la información. Permite correlacionar
    "el mismo" reclamo/factura aunque llegue por distintas vías o dos veces.
    """

    provider_name: str
    invoice_number: str

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError("InvoiceReference.provider_name no puede estar vacío")
        if not self.invoice_number.strip():
            raise ValueError("InvoiceReference.invoice_number no puede estar vacío")

    def matches(self, other: "InvoiceReference") -> bool:
        return (
            self.provider_name.strip().lower() == other.provider_name.strip().lower()
            and self.invoice_number.strip().lower() == other.invoice_number.strip().lower()
        )


@dataclass(frozen=True)
class ConfidenceLevel:
    """
    Qué tan segura está la clasificación automática (IA o matching de regla
    recurrente) de haber interpretado bien el dato. NO mide si es seguro
    actuar en base a él -- eso es una decisión de negocio aparte.
    """

    value: float  # 0.0 a 1.0
    HIGH_THRESHOLD: float = 0.85

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("ConfidenceLevel debe estar entre 0.0 y 1.0")

    @property
    def is_high(self) -> bool:
        return self.value >= self.HIGH_THRESHOLD


@dataclass(frozen=True)
class Deadline:
    """Fecha límite de una obligación administrativa."""

    due_date: date

    def is_overdue(self, as_of: date | None = None) -> bool:
        reference_date = as_of or date.today()
        return self.due_date < reference_date

    def days_remaining(self, as_of: date | None = None) -> int:
        reference_date = as_of or date.today()
        return (self.due_date - reference_date).days
