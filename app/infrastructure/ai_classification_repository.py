import json

from sqlalchemy.orm import Session

from app.domain.ai_classification import AIClassification
from app.infrastructure.orm_models import AIClassificationORM


class SqliteAIClassificationRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, classification: AIClassification) -> None:
        orm_obj = self._to_orm(classification)
        self._session.add(orm_obj)
        self._session.commit()

    def save(self, classification: AIClassification) -> None:
        orm_obj = self._session.get(AIClassificationORM, classification.id)
        if orm_obj is None:
            raise ValueError(f"No existe AIClassification con id {classification.id}")
        self._apply_domain_to_orm(classification, orm_obj)
        self._session.commit()

    def get_by_item_id(self, item_id: str) -> AIClassification | None:
        orm_obj = (
            self._session.query(AIClassificationORM)
            .filter(AIClassificationORM.administrative_item_id == item_id)
            .first()
        )
        return self._to_domain(orm_obj) if orm_obj else None

    def _to_orm(self, classification: AIClassification) -> AIClassificationORM:
        orm_obj = AIClassificationORM(id=classification.id)
        self._apply_domain_to_orm(classification, orm_obj)
        return orm_obj

    def _apply_domain_to_orm(self, classification: AIClassification, orm_obj: AIClassificationORM) -> None:
        orm_obj.administrative_item_id = classification.administrative_item_id
        orm_obj.source_subject = classification.source_subject
        orm_obj.source_body = classification.source_body
        orm_obj.proposed_item_type = classification.proposed_item_type
        orm_obj.proposed_confidence = classification.proposed_confidence
        orm_obj.proposed_data_json = json.dumps(classification.proposed_data)
        orm_obj.corrected = classification.corrected
        orm_obj.corrected_data_json = (
            json.dumps(classification.corrected_data)
            if classification.corrected_data is not None
            else None
        )
        orm_obj.created_at = classification.created_at
        orm_obj.confirmed_at = classification.confirmed_at

    def _to_domain(self, orm_obj: AIClassificationORM) -> AIClassification:
        return AIClassification(
            id=orm_obj.id,
            administrative_item_id=orm_obj.administrative_item_id,
            source_subject=orm_obj.source_subject,
            source_body=orm_obj.source_body,
            proposed_item_type=orm_obj.proposed_item_type,
            proposed_confidence=orm_obj.proposed_confidence,
            proposed_data=json.loads(orm_obj.proposed_data_json),
            created_at=orm_obj.created_at,
            corrected=orm_obj.corrected,
            corrected_data=(
                json.loads(orm_obj.corrected_data_json) if orm_obj.corrected_data_json else None
            ),
            confirmed_at=orm_obj.confirmed_at,
        )
