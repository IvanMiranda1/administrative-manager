import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database import get_db_session
from app.infrastructure.orm_models import Base
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db_session():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_email_de_factura_con_numero_se_clasifica_como_invoice(client):
    payload = {
        "message_id": "msg-100",
        "sender": "facturacion@camuzzi.com.ar",
        "subject": "Factura N° A-0001",
        "body": "Adjuntamos la factura correspondiente. Vencimiento 15/09.",
    }
    response = client.post("/emails", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["item_type"] == "invoice"
    assert body["invoice_provider_name"] == "Camuzzi"
    assert body["invoice_number"] == "A-0001"
    assert body["deadline_due_date"] == "2026-09-15"
    # Dos o más palabras clave de factura ("factura" + "vencimiento") -> alta confianza -> nace PENDING
    assert body["status"] == "pending"


def test_email_ambiguo_nace_needs_review(client):
    payload = {
        "message_id": "msg-101",
        "sender": "alguien@empresa.com",
        "subject": "Consulta",
        "body": "Tengo una duda sobre un tema.",
    }
    response = client.post("/emails", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "needs_review"


def test_email_factura_sin_numero_extraible_devuelve_422(client):
    payload = {
        "message_id": "msg-102",
        "sender": "facturacion@camuzzi.com.ar",
        "subject": "Factura del mes",
        "body": "Le recordamos el vencimiento próximo, gracias por su pago.",
    }
    response = client.post("/emails", json=payload)
    # El clasificador detecta "invoice" por keywords, pero no logra
    # extraer un número de factura -> viola el invariante 2 -> 422.
    assert response.status_code == 422


def test_email_duplicado_devuelve_409(client):
    payload = {
        "message_id": "msg-duplicado",
        "sender": "a@empresa.com",
        "subject": "Consulta",
        "body": "Test",
    }
    first = client.post("/emails", json=payload)
    assert first.status_code == 201

    second = client.post("/emails", json=payload)
    assert second.status_code == 409


def test_get_items_lista_lo_creado(client):
    client.post(
        "/emails",
        json={"message_id": "msg-200", "sender": "a@empresa.com", "subject": "Algo", "body": "..."},
    )
    response = client.get("/items")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_item_por_id(client):
    created = client.post(
        "/emails",
        json={"message_id": "msg-300", "sender": "a@empresa.com", "subject": "Algo", "body": "..."},
    ).json()

    response = client.get(f"/items/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_item_inexistente_devuelve_404(client):
    response = client.get("/items/no-existe")
    assert response.status_code == 404


def test_confirmar_item_needs_review_lo_pasa_a_pending(client):
    created = client.post(
        "/emails",
        json={
            "message_id": "msg-400",
            "sender": "alguien@empresa.com",
            "subject": "Consulta",
            "body": "Duda sobre un tema",
        },
    ).json()
    assert created["status"] == "needs_review"

    response = client.patch(
        f"/items/{created['id']}/confirm",
        json={"confirmed_data": {"detalle": "corregido por un humano"}},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["confirmed_data"] == {"detalle": "corregido por un humano"}


def test_confirmar_item_que_no_esta_en_needs_review_devuelve_409(client):
    created = client.post(
        "/emails",
        json={
            "message_id": "msg-500",
            "sender": "facturacion@camuzzi.com.ar",
            "subject": "Factura N° A-0002",
            "body": "Factura y vencimiento adjunto.",
        },
    ).json()
    assert created["status"] == "pending"  # ya nació accionable

    response = client.patch(
        f"/items/{created['id']}/confirm",
        json={"confirmed_data": {"algo": "distinto"}},
    )
    assert response.status_code == 409


def test_confirmar_item_inexistente_devuelve_404(client):
    response = client.patch("/items/no-existe/confirm", json={"confirmed_data": {}})
    assert response.status_code == 404


def test_recurring_obligation_hace_que_nazca_pending_sin_revision(client):
    # Configuramos que Camuzzi + invoice es una obligación recurrente conocida.
    config_response = client.post(
        "/recurring-obligations", params={"provider_name": "Camuzzi", "item_type": "invoice"}
    )
    assert config_response.status_code == 201

    # Mandamos un email con solo UNA palabra clave (confianza baja por sí sola)
    # pero que matchea la obligación recurrente configurada.
    payload = {
        "message_id": "msg-600",
        "sender": "facturacion@camuzzi.com.ar",
        "subject": "Factura N° A-0003",
        "body": "Le enviamos el comprobante correspondiente.",
    }
    response = client.post("/emails", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_listar_recurring_obligations(client):
    client.post("/recurring-obligations", params={"provider_name": "Edenor", "item_type": "invoice"})
    response = client.get("/recurring-obligations")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["provider_name"] == "Edenor"
