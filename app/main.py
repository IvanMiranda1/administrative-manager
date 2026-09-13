from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.api.email_adapter import build_administrative_item_from_email
from app.api.schemas import AdministrativeItemResponse, ConfirmItemPayload, IncomingEmailPayload
from app.domain.exceptions import DomainError, DuplicateSourceError, InvalidTransitionError
from app.domain.recurring_obligation import RecurringObligationConfig
from app.infrastructure.ai_classification_repository import SqliteAIClassificationRepository
from app.infrastructure.database import engine, get_db_session
from app.infrastructure.orm_models import Base
from app.infrastructure.recurring_obligation_repository import SqliteRecurringObligationConfigRepository
from app.infrastructure.sqlite_repository import SqliteAdministrativeItemRepository
from app.services.rule_based_classifier import RuleBasedEmailClassifier

app = FastAPI(title="Sistema de responsabilidades administrativas")

# Crea las tablas si no existen. Para un proyecto real usaríamos
# migraciones (Alembic), pero para la v1 esto alcanza.
Base.metadata.create_all(bind=engine)

# Instancia única del clasificador. Cambiar RuleBasedEmailClassifier por
# un GeminiEmailClassifier el día de mañana es la única línea que
# debería tocarse en todo este archivo.
classifier = RuleBasedEmailClassifier()


def _to_response(item) -> AdministrativeItemResponse:
    return AdministrativeItemResponse(
        id=item.id,
        item_type=item.item_type,
        status=item.status.value,
        source_reference=item.source.reference,
        confidence=item.confidence.value,
        invoice_provider_name=item.invoice_reference.provider_name if item.invoice_reference else None,
        invoice_number=item.invoice_reference.invoice_number if item.invoice_reference else None,
        deadline_due_date=item.deadline.due_date if item.deadline else None,
        confirmed_data=item.confirmed_data,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/emails", response_model=AdministrativeItemResponse, status_code=201)
def receive_email(
    payload: IncomingEmailPayload,
    db: Session = Depends(get_db_session),
) -> AdministrativeItemResponse:
    item_repository = SqliteAdministrativeItemRepository(db)
    classification_repository = SqliteAIClassificationRepository(db)
    recurring_repository = SqliteRecurringObligationConfigRepository(db)

    try:
        item, classification = build_administrative_item_from_email(
            payload, classifier, recurring_repository
        )
        item_repository.add(item)
        classification_repository.add(classification)
    except DuplicateSourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, DomainError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _to_response(item)


@app.get("/items", response_model=list[AdministrativeItemResponse])
def list_items(db: Session = Depends(get_db_session)) -> list[AdministrativeItemResponse]:
    repository = SqliteAdministrativeItemRepository(db)
    return [_to_response(item) for item in repository.list_all()]


@app.get("/items/{item_id}", response_model=AdministrativeItemResponse)
def get_item(item_id: str, db: Session = Depends(get_db_session)) -> AdministrativeItemResponse:
    repository = SqliteAdministrativeItemRepository(db)
    item = repository.get_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    return _to_response(item)


@app.patch("/items/{item_id}/confirm", response_model=AdministrativeItemResponse)
def confirm_item(
    item_id: str,
    payload: ConfirmItemPayload,
    db: Session = Depends(get_db_session),
) -> AdministrativeItemResponse:
    """
    Un humano revisa un item en NEEDS_REVIEW y confirma o corrige los
    datos que propuso la clasificación. Esto también actualiza la
    AIClassification asociada, marcando si hubo corrección -- ese dato
    es justo el que sirve para reentrenar después.
    """
    item_repository = SqliteAdministrativeItemRepository(db)
    classification_repository = SqliteAIClassificationRepository(db)

    item = item_repository.get_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item no encontrado")

    try:
        item.confirm(payload.confirmed_data)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    item_repository.save(item)

    classification = classification_repository.get_by_item_id(item_id)
    if classification is not None:
        classification.confirm(payload.confirmed_data)
        classification_repository.save(classification)

    return _to_response(item)


@app.post("/recurring-obligations", status_code=201)
def create_recurring_obligation(
    provider_name: str,
    item_type: str,
    db: Session = Depends(get_db_session),
) -> dict:
    repository = SqliteRecurringObligationConfigRepository(db)
    config = RecurringObligationConfig.create(provider_name=provider_name, item_type=item_type)
    repository.add(config)
    return {"id": config.id, "provider_name": config.provider_name, "item_type": config.item_type}


@app.get("/recurring-obligations")
def list_recurring_obligations(db: Session = Depends(get_db_session)) -> list[dict]:
    repository = SqliteRecurringObligationConfigRepository(db)
    return [
        {"id": c.id, "provider_name": c.provider_name, "item_type": c.item_type, "active": c.active}
        for c in repository.list_all()
    ]
