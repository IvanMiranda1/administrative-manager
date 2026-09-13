from sqlalchemy.orm import Session

from app.domain.recurring_obligation import RecurringObligationConfig
from app.infrastructure.orm_models import RecurringObligationConfigORM


class SqliteRecurringObligationConfigRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, config: RecurringObligationConfig) -> None:
        orm_obj = RecurringObligationConfigORM(
            id=config.id,
            provider_name=config.provider_name,
            item_type=config.item_type,
            active=config.active,
            created_at=config.created_at,
        )
        self._session.add(orm_obj)
        self._session.commit()

    def find_match(self, provider_name: str, item_type: str) -> RecurringObligationConfig | None:
        candidates = (
            self._session.query(RecurringObligationConfigORM)
            .filter(RecurringObligationConfigORM.active == True)  # noqa: E712
            .all()
        )
        for orm_obj in candidates:
            config = self._to_domain(orm_obj)
            if config.matches(provider_name, item_type):
                return config
        return None

    def list_all(self) -> list[RecurringObligationConfig]:
        return [self._to_domain(o) for o in self._session.query(RecurringObligationConfigORM).all()]

    def _to_domain(self, orm_obj: RecurringObligationConfigORM) -> RecurringObligationConfig:
        return RecurringObligationConfig(
            id=orm_obj.id,
            provider_name=orm_obj.provider_name,
            item_type=orm_obj.item_type,
            active=orm_obj.active,
            created_at=orm_obj.created_at,
        )
