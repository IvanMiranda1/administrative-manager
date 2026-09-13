import pytest

from app.domain.ai_classification import AIClassification
from app.domain.recurring_obligation import RecurringObligationConfig


def test_no_puede_crearse_sin_administrative_item_id():
    with pytest.raises(ValueError):
        AIClassification.create(
            administrative_item_id="",
            source_subject="Factura",
            source_body="...",
            proposed_item_type="invoice",
            proposed_confidence=0.9,
            proposed_data={},
        )


def test_confirmar_sin_cambios_no_marca_corrected():
    classification = AIClassification.create(
        administrative_item_id="item-1",
        source_subject="Factura",
        source_body="...",
        proposed_item_type="invoice",
        proposed_confidence=0.9,
        proposed_data={"invoice_number": "A-0001"},
    )
    classification.confirm({"invoice_number": "A-0001"})
    assert classification.corrected is False
    assert classification.confirmed_at is not None


def test_confirmar_con_cambios_marca_corrected():
    classification = AIClassification.create(
        administrative_item_id="item-1",
        source_subject="Factura",
        source_body="...",
        proposed_item_type="invoice",
        proposed_confidence=0.4,
        proposed_data={"invoice_number": "A-0001"},
    )
    classification.confirm({"invoice_number": "A-0002"})  # el humano corrigió el número
    assert classification.corrected is True


def test_recurring_obligation_matches_case_insensitive():
    config = RecurringObligationConfig.create(provider_name="Camuzzi", item_type="invoice")
    assert config.matches("camuzzi", "invoice") is True
    assert config.matches("Camuzzi", "invoice") is True


def test_recurring_obligation_no_matches_distinto_tipo():
    config = RecurringObligationConfig.create(provider_name="Camuzzi", item_type="invoice")
    assert config.matches("Camuzzi", "request") is False


def test_recurring_obligation_inactiva_no_matchea():
    config = RecurringObligationConfig.create(provider_name="Camuzzi", item_type="invoice")
    config.active = False
    assert config.matches("Camuzzi", "invoice") is False
