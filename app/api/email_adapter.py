"""
Este módulo es el "adapter de entrada": el dominio no sabe que existe un
email, un subject o un sender_domain -- solo recibe un Source y datos ya
traducidos.

Semana 3: la clasificación ahora viene de un EmailClassifier real (hoy
RuleBasedEmailClassifier, mañana podría ser GeminiEmailClassifier) en vez
de leer overrides manuales del payload. Si mañana cambiás la
implementación del clasificador, este archivo no debería cambiar.
"""
from app.api.schemas import IncomingEmailPayload
from app.domain.administrative_item import AdministrativeItem
from app.domain.ai_classification import AIClassification
from app.domain.repositories import RecurringObligationConfigRepository
from app.domain.value_objects import ConfidenceLevel, Deadline, InvoiceReference, Source, SourceType
from app.services.email_classifier import ClassificationProposal, EmailClassifier


def _extract_sender_domain(sender: str) -> str | None:
    if "@" not in sender:
        return None
    return sender.split("@", 1)[1].strip().lower() or None


def _proposal_to_dict(proposal: ClassificationProposal) -> dict:
    return {
        "item_type": proposal.item_type,
        "invoice_provider_name": proposal.invoice_provider_name,
        "invoice_number": proposal.invoice_number,
        "deadline_due_date": proposal.deadline_due_date.isoformat() if proposal.deadline_due_date else None,
    }


def build_administrative_item_from_email(
    payload: IncomingEmailPayload,
    classifier: EmailClassifier,
    recurring_repo: RecurringObligationConfigRepository,
) -> tuple[AdministrativeItem, AIClassification]:
    sender_domain = _extract_sender_domain(payload.sender)

    proposal = classifier.classify(subject=payload.subject, body=payload.body, sender_domain=sender_domain)

    source = Source(
        type=SourceType.EMAIL,
        reference=payload.message_id,
        received_at=payload.received_at,
        sender_domain=sender_domain,
    )

    invoice_reference = None
    if proposal.invoice_provider_name and proposal.invoice_number:
        invoice_reference = InvoiceReference(
            provider_name=proposal.invoice_provider_name,
            invoice_number=proposal.invoice_number,
        )

    deadline = Deadline(due_date=proposal.deadline_due_date) if proposal.deadline_due_date else None

    # Invariante 3: confiar en el dato porque una configuración humana
    # previa ya reconoce a este proveedor + tipo como obligación recurrente.
    matches_recurring = False
    if proposal.invoice_provider_name:
        matches_recurring = (
            recurring_repo.find_match(proposal.invoice_provider_name, proposal.item_type) is not None
        )

    item = AdministrativeItem.create(
        source=source,
        item_type=proposal.item_type,
        confidence=ConfidenceLevel(proposal.confidence),
        proposed_data={"subject": payload.subject, "body": payload.body},
        invoice_reference=invoice_reference,
        deadline=deadline,
        matches_configured_recurring_obligation=matches_recurring,
    )

    classification = AIClassification.create(
        administrative_item_id=item.id,
        source_subject=payload.subject,
        source_body=payload.body,
        proposed_item_type=proposal.item_type,
        proposed_confidence=proposal.confidence,
        proposed_data=_proposal_to_dict(proposal),
    )

    return item, classification
