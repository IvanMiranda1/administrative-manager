from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.administrative_item import AdministrativeItem
from app.domain.enums import ItemStatus
from app.domain.exceptions import DuplicateSourceError
from app.domain.value_objects import ConfidenceLevel, Deadline, InvoiceReference, Source, SourceType
from app.infrastructure.orm_models import Base
from app.infrastructure.sqlite_repository import SqliteAdministrativeItemRepository


@pytest.fixture
def session():
    # Base en memoria, una por test, para no pisar la base real del proyecto.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def make_item(reference="msg-1", item_type="invoice", confidence=0.9, invoice_number="A-0001"):
    return AdministrativeItem.create(
        source=Source(
            type=SourceType.EMAIL,
            reference=reference,
            received_at=datetime.now(),
            sender_domain="proveedor.com",
        ),
        item_type=item_type,
        confidence=ConfidenceLevel(confidence),
        proposed_data={"monto": 1000},
        invoice_reference=InvoiceReference(provider_name="Camuzzi", invoice_number=invoice_number),
        deadline=Deadline(due_date=date(2026, 9, 15)),
    )


def test_guardar_y_leer_por_id(session):
    repo = SqliteAdministrativeItemRepository(session)
    item = make_item()

    repo.add(item)
    recovered = repo.get_by_id(item.id)

    assert recovered is not None
    assert recovered.id == item.id
    assert recovered.status == ItemStatus.PENDING
    assert recovered.invoice_reference.matches(item.invoice_reference)
    assert recovered.confirmed_data == {"monto": 1000}
    assert recovered.deadline.due_date == date(2026, 9, 15)


def test_buscar_por_source_reference(session):
    repo = SqliteAdministrativeItemRepository(session)
    item = make_item(reference="msg-especifico")
    repo.add(item)

    found = repo.get_by_source_reference("msg-especifico")
    assert found is not None
    assert found.id == item.id

    not_found = repo.get_by_source_reference("no-existe")
    assert not_found is None


def test_no_permite_duplicar_el_mismo_source_reference(session):
    repo = SqliteAdministrativeItemRepository(session)
    item1 = make_item(reference="msg-duplicado", invoice_number="A-0001")
    item2 = make_item(reference="msg-duplicado", invoice_number="A-0002")  # mismo reference

    repo.add(item1)
    with pytest.raises(DuplicateSourceError):
        repo.add(item2)


def test_save_persiste_cambio_de_estado(session):
    repo = SqliteAdministrativeItemRepository(session)
    item = make_item(confidence=0.2)  # nace en NEEDS_REVIEW
    repo.add(item)
    assert item.status == ItemStatus.NEEDS_REVIEW

    item.confirm({"monto": 1000})
    repo.save(item)

    recovered = repo.get_by_id(item.id)
    assert recovered.status == ItemStatus.PENDING
    assert recovered.confirmed_data == {"monto": 1000}


def test_list_all_devuelve_todos_los_items(session):
    repo = SqliteAdministrativeItemRepository(session)
    repo.add(make_item(reference="msg-a"))
    repo.add(make_item(reference="msg-b", invoice_number="A-0002"))

    items = repo.list_all()
    assert len(items) == 2
