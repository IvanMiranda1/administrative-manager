from datetime import date, datetime

from pydantic import BaseModel, Field


class IncomingEmailPayload(BaseModel):
    """Lo que realmente llega de un email: nada de esto es negocio todavía."""

    message_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime = Field(default_factory=datetime.now)


class ConfirmItemPayload(BaseModel):
    """Lo que un humano confirma o corrige sobre un item en NEEDS_REVIEW."""

    confirmed_data: dict


class AdministrativeItemResponse(BaseModel):
    id: str
    item_type: str
    status: str
    source_reference: str
    confidence: float
    invoice_provider_name: str | None = None
    invoice_number: str | None = None
    deadline_due_date: date | None = None
    confirmed_data: dict
