"""
Modelo de persistencia (SQLAlchemy). A propósito NO es lo mismo que
AdministrativeItem del dominio -- este archivo solo sabe de columnas y
tipos de base de datos. La traducción entre uno y otro vive en
sqlite_repository.py, no acá ni en el dominio.
"""
import json
from datetime import date, datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class AdministrativeItemORM(Base):
    __tablename__ = "administrative_items"

    id = Column(String, primary_key=True)
    item_type = Column(String, nullable=False)
    status = Column(String, nullable=False)

    # --- Source (value object) como columnas propias ---
    source_type = Column(String, nullable=False)
    # unique=True: es la restricción que impide guardar el mismo email dos veces.
    source_reference = Column(String, nullable=False, unique=True, index=True)
    source_received_at = Column(DateTime, nullable=False)
    source_sender_domain = Column(String, nullable=True)

    # --- InvoiceReference (value object), nullable porque no todos los
    # tipos de item lo requieren ---
    invoice_provider_name = Column(String, nullable=True)
    invoice_number = Column(String, nullable=True)

    # --- ConfidenceLevel ---
    confidence_value = Column(Float, nullable=False)

    # --- Deadline ---
    deadline_due_date = Column(DateTime, nullable=True)

    # --- Datos cuya forma varía según item_type: JSON como TEXT ---
    confirmed_data_json = Column(String, nullable=False, default="{}")
    pending_evidence_snapshot_json = Column(String, nullable=True)

    @staticmethod
    def dump_json(data: dict | None) -> str | None:
        if data is None:
            return None
        return json.dumps(data)

    @staticmethod
    def load_json(raw: str | None) -> dict:
        if not raw:
            return {}
        return json.loads(raw)


class AIClassificationORM(Base):
    __tablename__ = "ai_classifications"

    id = Column(String, primary_key=True)
    administrative_item_id = Column(
        String, ForeignKey("administrative_items.id"), nullable=False, index=True
    )

    source_subject = Column(String, nullable=False)
    source_body = Column(String, nullable=False)

    proposed_item_type = Column(String, nullable=False)
    proposed_confidence = Column(Float, nullable=False)
    proposed_data_json = Column(String, nullable=False, default="{}")

    corrected = Column(Boolean, nullable=False, default=False)
    corrected_data_json = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False)
    confirmed_at = Column(DateTime, nullable=True)


class RecurringObligationConfigORM(Base):
    __tablename__ = "recurring_obligation_configs"

    id = Column(String, primary_key=True)
    provider_name = Column(String, nullable=False, index=True)
    item_type = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
