from sqlalchemy.orm import Session

from app.domain.administrative_item import AdministrativeItem
from app.domain.enums import ItemStatus
from app.domain.exceptions import DuplicateSourceError
from app.domain.value_objects import ConfidenceLevel, Deadline, InvoiceReference, Source, SourceType
from app.infrastructure.orm_models import AdministrativeItemORM


class SqliteAdministrativeItemRepository:
    """Implementa el puerto AdministrativeItemRepository usando SQLAlchemy."""

    def __init__(self, session: Session):
        self._session = session

    # -----------------------------------------------------------------
    # Escritura
    # -----------------------------------------------------------------
    def add(self, item: AdministrativeItem) -> None:
        # Invariante nuevo de esta semana: no se duplica el mismo Source.
        existing = self.get_by_source_reference(item.source.reference)
        if existing is not None:
            raise DuplicateSourceError(
                f"Ya existe un item para el source '{item.source.reference}' "
                f"(id existente: {existing.id})"
            )
        orm_obj = self._to_orm(item)
        self._session.add(orm_obj)
        self._session.commit()

    def save(self, item: AdministrativeItem) -> None:
        orm_obj = self._session.get(AdministrativeItemORM, item.id)
        if orm_obj is None:
            raise ValueError(f"No existe un item con id {item.id} para actualizar")
        self._apply_domain_to_orm(item, orm_obj)
        self._session.commit()

    # -----------------------------------------------------------------
    # Lectura
    # -----------------------------------------------------------------
    def get_by_id(self, item_id: str) -> AdministrativeItem | None:
        orm_obj = self._session.get(AdministrativeItemORM, item_id)
        return self._to_domain(orm_obj) if orm_obj else None

    def get_by_source_reference(self, reference: str) -> AdministrativeItem | None:
        orm_obj = (
            self._session.query(AdministrativeItemORM)
            .filter(AdministrativeItemORM.source_reference == reference)
            .first()
        )
        return self._to_domain(orm_obj) if orm_obj else None

    def list_all(self) -> list[AdministrativeItem]:
        orm_objs = self._session.query(AdministrativeItemORM).all()
        return [self._to_domain(obj) for obj in orm_objs]

    # -----------------------------------------------------------------
    # Traducción dominio -> fila SQL
    # -----------------------------------------------------------------
    def _to_orm(self, item: AdministrativeItem) -> AdministrativeItemORM:
        orm_obj = AdministrativeItemORM(id=item.id)
        self._apply_domain_to_orm(item, orm_obj)
        return orm_obj

    def _apply_domain_to_orm(self, item: AdministrativeItem, orm_obj: AdministrativeItemORM) -> None:
        orm_obj.item_type = item.item_type
        orm_obj.status = item.status.value

        orm_obj.source_type = item.source.type.value
        orm_obj.source_reference = item.source.reference
        orm_obj.source_received_at = item.source.received_at
        orm_obj.source_sender_domain = item.source.sender_domain

        if item.invoice_reference is not None:
            orm_obj.invoice_provider_name = item.invoice_reference.provider_name
            orm_obj.invoice_number = item.invoice_reference.invoice_number
        else:
            orm_obj.invoice_provider_name = None
            orm_obj.invoice_number = None

        orm_obj.confidence_value = item.confidence.value

        orm_obj.deadline_due_date = (
            item.deadline.due_date if item.deadline is not None else None
        )

        orm_obj.confirmed_data_json = AdministrativeItemORM.dump_json(item.confirmed_data)
        orm_obj.pending_evidence_snapshot_json = AdministrativeItemORM.dump_json(
            item.pending_evidence_snapshot
        )

    # -----------------------------------------------------------------
    # Traducción fila SQL -> dominio
    # -----------------------------------------------------------------
    def _to_domain(self, orm_obj: AdministrativeItemORM) -> AdministrativeItem:
        source = Source(
            type=SourceType(orm_obj.source_type),
            reference=orm_obj.source_reference,
            received_at=orm_obj.source_received_at,
            sender_domain=orm_obj.source_sender_domain,
        )

        invoice_reference = None
        if orm_obj.invoice_provider_name and orm_obj.invoice_number:
            invoice_reference = InvoiceReference(
                provider_name=orm_obj.invoice_provider_name,
                invoice_number=orm_obj.invoice_number,
            )

        deadline = (
            Deadline(due_date=orm_obj.deadline_due_date.date())
            if orm_obj.deadline_due_date is not None
            else None
        )

        return AdministrativeItem(
            id=orm_obj.id,
            source=source,
            item_type=orm_obj.item_type,
            confidence=ConfidenceLevel(orm_obj.confidence_value),
            status=ItemStatus(orm_obj.status),
            invoice_reference=invoice_reference,
            deadline=deadline,
            confirmed_data=AdministrativeItemORM.load_json(orm_obj.confirmed_data_json),
            pending_evidence_snapshot=(
                AdministrativeItemORM.load_json(orm_obj.pending_evidence_snapshot_json)
                if orm_obj.pending_evidence_snapshot_json
                else None
            ),
        )
