from datetime import date, datetime, timedelta

import pytest

from app.domain.administrative_item import AdministrativeItem
from app.domain.enums import ItemStatus
from app.domain.exceptions import (
    ConfirmedDataOverwriteError,
    InvalidTransitionError,
    UnsafeActionError,
)
from app.domain.value_objects import ConfidenceLevel, Deadline, InvoiceReference, Source, SourceType


def make_source(**overrides) -> Source:
    defaults = dict(
        type=SourceType.EMAIL,
        reference="msg-123",
        received_at=datetime.now(),
        sender_domain="proveedor.com",
    )
    defaults.update(overrides)
    return Source(**defaults)


def make_invoice_ref(**overrides) -> InvoiceReference:
    defaults = dict(provider_name="Camuzzi", invoice_number="A-0001")
    defaults.update(overrides)
    return InvoiceReference(**defaults)


# ---------------------------------------------------------------------
# Invariante 1: no existe sin Source
# ---------------------------------------------------------------------
def test_no_puede_crearse_sin_source():
    with pytest.raises(ValueError):
        AdministrativeItem.create(
            source=None,
            item_type="request",
            confidence=ConfidenceLevel(0.5),
            proposed_data={"detalle": "revisar presupuesto"},
        )


# ---------------------------------------------------------------------
# Invariante 2: correlación de negocio obligatoria para ciertos tipos
# ---------------------------------------------------------------------
def test_invoice_requiere_invoice_reference():
    with pytest.raises(ValueError):
        AdministrativeItem.create(
            source=make_source(),
            item_type="invoice",
            confidence=ConfidenceLevel(0.9),
            proposed_data={"monto": 1000},
            invoice_reference=None,
        )


def test_invoice_con_reference_se_crea_ok():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.9),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
    )
    assert item.invoice_reference is not None


def test_request_no_requiere_invoice_reference():
    # "request" no está en TYPES_REQUIRING_CORRELATION, así que no explota.
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="request",
        confidence=ConfidenceLevel(0.5),
        proposed_data={"detalle": "revisar presupuesto"},
    )
    assert item.invoice_reference is None


# ---------------------------------------------------------------------
# Invariante 3: estado inicial según confianza o match recurrente
# ---------------------------------------------------------------------
def test_alta_confianza_nace_pending():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
    )
    assert item.status == ItemStatus.PENDING
    assert item.confirmed_data == {"monto": 1000}


def test_baja_confianza_nace_needs_review():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.3),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
    )
    assert item.status == ItemStatus.NEEDS_REVIEW
    # Ojo: con baja confianza, el dato propuesto NO se confirma solo.
    assert item.confirmed_data == {}


def test_baja_confianza_pero_match_recurrente_nace_pending():
    item = AdministrativeItem.create(
        source=make_source(type=SourceType.RECURRING_RULE, reference="regla-camuzzi"),
        item_type="invoice",
        confidence=ConfidenceLevel(0.3),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
        matches_configured_recurring_obligation=True,
    )
    assert item.status == ItemStatus.PENDING


# ---------------------------------------------------------------------
# Transiciones básicas
# ---------------------------------------------------------------------
def test_confirmar_needs_review_pasa_a_pending():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="request",
        confidence=ConfidenceLevel(0.2),
        proposed_data={"detalle": "algo"},
    )
    assert item.status == ItemStatus.NEEDS_REVIEW

    item.confirm({"detalle": "algo corregido"})

    assert item.status == ItemStatus.PENDING
    assert item.confirmed_data == {"detalle": "algo corregido"}


def test_no_se_puede_confirmar_si_no_esta_en_needs_review():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="request",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"detalle": "algo"},
    )
    assert item.status == ItemStatus.PENDING

    with pytest.raises(InvalidTransitionError):
        item.confirm({"detalle": "otra cosa"})


def test_pending_a_waiting_y_de_vuelta():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="request",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"detalle": "algo"},
    )
    item.mark_waiting()
    assert item.status == ItemStatus.WAITING

    item.resume_from_waiting()
    assert item.status == ItemStatus.PENDING


def test_transicion_invalida_lanza_excepcion():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="request",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"detalle": "algo"},
    )
    item.complete()
    with pytest.raises(InvalidTransitionError):
        item.mark_waiting()  # COMPLETED es terminal


# ---------------------------------------------------------------------
# Invariante 4: evidencia nueva -> snapshot, no se pisa directo
# ---------------------------------------------------------------------
def test_nueva_evidencia_guarda_snapshot_y_vuelve_a_revision():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
    )
    assert item.status == ItemStatus.PENDING

    item.receive_new_evidence({"monto": 1500})

    assert item.status == ItemStatus.NEEDS_REVIEW
    assert item.pending_evidence_snapshot == {"monto": 1000}
    assert item.confirmed_data == {"monto": 1500}


def test_confirmar_evidencia_descarta_snapshot():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
    )
    item.receive_new_evidence({"monto": 1500})

    item.confirm_evidence_update({"monto": 1500})

    assert item.status == ItemStatus.PENDING
    assert item.pending_evidence_snapshot is None
    assert item.confirmed_data == {"monto": 1500}


def test_no_se_puede_confirmar_evidencia_si_no_hay_cambio_pendiente():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
    )
    with pytest.raises(ConfirmedDataOverwriteError):
        item.confirm_evidence_update({"monto": 2000})


# ---------------------------------------------------------------------
# Invariante 5: ninguna acción real sin confirmación humana
# ---------------------------------------------------------------------
def test_no_se_puede_ejecutar_accion_real_sin_datos_confirmados():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.2),  # baja confianza -> confirmed_data vacío
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
    )
    with pytest.raises(UnsafeActionError):
        item.execute_action_with_real_effect()


def test_no_se_puede_ejecutar_accion_real_si_no_esta_pending():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
    )
    item.mark_waiting()
    with pytest.raises(UnsafeActionError):
        item.execute_action_with_real_effect()


def test_ejecutar_accion_real_ok_cuando_pending_y_confirmado():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
    )
    # No debería lanzar nada.
    item.execute_action_with_real_effect()


# ---------------------------------------------------------------------
# Invariante 6: cálculos derivados, no se guardan como estado
# ---------------------------------------------------------------------
def test_is_overdue_es_calculado_no_estado():
    item = AdministrativeItem.create(
        source=make_source(),
        item_type="invoice",
        confidence=ConfidenceLevel(0.95),
        proposed_data={"monto": 1000},
        invoice_reference=make_invoice_ref(),
        deadline=Deadline(due_date=date.today() - timedelta(days=1)),
    )
    assert item.is_overdue() is True
    # El status sigue siendo PENDING: estar vencido no es un estado en sí mismo.
    assert item.status == ItemStatus.PENDING


# ---------------------------------------------------------------------
# InvoiceReference.matches
# ---------------------------------------------------------------------
def test_invoice_reference_matches_es_case_insensitive():
    ref1 = InvoiceReference(provider_name="Camuzzi", invoice_number="A-0001")
    ref2 = InvoiceReference(provider_name="camuzzi", invoice_number="a-0001")
    assert ref1.matches(ref2) is True


def test_invoice_reference_no_matches_distinto_numero():
    ref1 = InvoiceReference(provider_name="Camuzzi", invoice_number="A-0001")
    ref2 = InvoiceReference(provider_name="Camuzzi", invoice_number="A-0002")
    assert ref1.matches(ref2) is False
