from datetime import date

from app.services.rule_based_classifier import RuleBasedEmailClassifier

classifier = RuleBasedEmailClassifier()


def test_dos_keywords_de_factura_dan_alta_confianza():
    proposal = classifier.classify(
        subject="Factura N° A-0001",
        body="Vencimiento el 15/09.",
        sender_domain="camuzzi.com.ar",
    )
    assert proposal.item_type == "invoice"
    assert proposal.confidence == 0.9
    assert proposal.invoice_provider_name == "Camuzzi"
    assert proposal.invoice_number == "A-0001"
    assert proposal.deadline_due_date == date(date.today().year, 9, 15)


def test_una_sola_keyword_da_baja_confianza():
    proposal = classifier.classify(subject="Factura", body="...", sender_domain="proveedor.com")
    assert proposal.item_type == "invoice"
    assert proposal.confidence == 0.4


def test_sin_keywords_relevantes_es_request_baja_confianza():
    proposal = classifier.classify(subject="Hola", body="Como estas", sender_domain="a.com")
    assert proposal.item_type == "request"
    assert proposal.confidence == 0.4


def test_dos_keywords_de_request_dan_alta_confianza():
    proposal = classifier.classify(
        subject="Necesito que revisar el presupuesto",
        body="Por favor aprobar antes del viernes",
        sender_domain="gerencia@empresa.com",
    )
    assert proposal.item_type == "request"
    assert proposal.confidence == 0.9


def test_sin_sender_domain_no_hay_provider_name():
    proposal = classifier.classify(subject="Factura y vencimiento", body="...", sender_domain=None)
    assert proposal.invoice_provider_name is None


def test_sin_numero_extraible_invoice_number_es_none():
    proposal = classifier.classify(
        subject="Factura del mes", body="gracias por su pago", sender_domain="camuzzi.com.ar"
    )
    assert proposal.item_type == "invoice"
    assert proposal.invoice_number is None
