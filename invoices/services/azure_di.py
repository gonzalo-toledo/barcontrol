from django.conf import settings

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from .azure_blob import to_blob_name_from_url, make_sas_url


def _di_client() -> DocumentIntelligenceClient:
    if not settings.AZ_DOCINT_ENDPOINT or not settings.AZ_DOCINT_KEY:
        raise RuntimeError("Faltan AZ_DOCINT_ENDPOINT o AZ_DOCINT_KEY")
    return DocumentIntelligenceClient(
        endpoint=settings.AZ_DOCINT_ENDPOINT,
        credential=AzureKeyCredential(settings.AZ_DOCINT_KEY)
    )

def analyze_invoice_from_url(file_url: str):
    client = _di_client()
    model_id = settings.AZ_DOCINT_MODEL or "prebuilt-invoice"
    poller = client.begin_analyze_document(model_id, AnalyzeDocumentRequest(url_source=file_url))
    return poller.result()

def analyze_invoice_from_bytes(data: bytes):
    client = _di_client()
    model_id = settings.AZ_DOCINT_MODEL or "prebuilt-invoice"
    poller = client.begin_analyze_document(model_id, data)
    return poller.result()


def analyze_invoice_auto(data: bytes, blob_url: str):
    """
    Política:
    - Si USE_AZURE_SIMULATION está activo, devuelve datos simulados.
    - Si no, se conecta normalmente a Azure:
        - DI_ANALYZE_MODE = 'sas': intenta SAS -> fallback bytes
        - DI_ANALYZE_MODE = 'bytes': bytes directo
        - DI_ANALYZE_MODE = 'auto' (default):
            * si len(data) <= DI_INLINE_BYTES_MAX_MB -> bytes
            * si > umbral -> intenta SAS -> fallback bytes
    """
    
    # Modo simulación:
    if getattr(settings, "USE_AZURE_SIMULATION", False):
        print("MODO SIMULACIÓN ACTIVADO - Azure DI no está siendo usado.")
        from types import SimpleNamespace
        import datetime

        # Estructura simulada compatible con map_invoice_result
        class FakeValue:
            def __init__(self, content=None, value=None):
                self.content = content or value
                self.value = value or content
                self.confidence = 0.99

        # Clase que imita exactamente los campos de Azure
    class FakeField:
        def __init__(
            self,
            value_string=None,
            value_number=None,
            value_currency=None,
            value_date=None,
            value_address=None,
        ):
            self.value_string = value_string
            self.value_number = value_number
            self.value_currency = (
                SimpleNamespace(amount=value_currency) if value_currency else None
            )
            self.value_date = value_date
            self.value_address = value_address
            self.confidence = 0.99

    # Ítems simulados
    fake_items = [
        SimpleNamespace(
            value_object={
                "Description": FakeField(value_string="Producto Demo A"),
                "Quantity": FakeField(value_number=2),
                "UnitPrice": FakeField(value_currency=5000.0),
                "Amount": FakeField(value_currency=10000.0),
            }
        ),
        SimpleNamespace(
            value_object={
                "Description": FakeField(value_string="IVA 21%"),
                "Quantity": FakeField(value_number=1),
                "UnitPrice": FakeField(value_currency=2100.0),
                "Amount": FakeField(value_currency=2100.0),
            }
        ),
    ]

    # Campos principales simulados
    fake_fields = {
        "VendorName": FakeField(value_string="Proveedor Demo SRL"),
        "VendorTaxId": FakeField(value_string="30-12345678-9"),
        "VendorAddress": FakeField(value_address="Calle Falsa 123"),
        "InvoiceId": FakeField(value_string="F0001-000123"),
        "InvoiceDate": FakeField(value_date=datetime.date(2025, 9, 15)),
        "SubTotal": FakeField(value_currency=10000.0),
        "TotalTax": FakeField(value_currency=2100.0),
        "InvoiceTotal": FakeField(value_currency=12100.0),
        "PaymentTerm": FakeField(value_string="Contado"),
        "Items": SimpleNamespace(value_array=fake_items),
    }

    fake_doc = SimpleNamespace(
        documents=[SimpleNamespace(fields=fake_fields)]
    )
    return fake_doc
    # --- FIN SIMULACIÓN ---

    # --- FLUJO NORMAL CON AZURE ---
    
    mode = getattr(settings, "DI_ANALYZE_MODE", "auto")
    mb = len(data) / (1024 * 1024)
    threshold = float(getattr(settings, "DI_INLINE_BYTES_MAX_MB", 5.0))

    def _try_sas_then_bytes():
        try:
            blob_name = to_blob_name_from_url(blob_url)
            sas_url = make_sas_url(settings.AZURE_BLOB_CONTAINER, blob_name, minutes=15)
            if sas_url:
                return analyze_invoice_from_url(sas_url)
        except Exception:
            pass
        # fallback
        return analyze_invoice_from_bytes(data)

    if mode == "bytes":
        return analyze_invoice_from_bytes(data)
    if mode == "sas":
        return _try_sas_then_bytes()
    # auto
    if mb <= threshold:
        # pequeño → bytes
        return analyze_invoice_from_bytes(data)
    # grande → SAS preferente
    return _try_sas_then_bytes()

def debug_invoice_fields(di_result):
    if not di_result or not di_result.documents:
        print("⚠️ No hay documentos en el resultado")
        return
    inv = di_result.documents[0]
    print("\n====== CAMPOS DETECTADOS POR DOCUMENT INTELLIGENCE ======")
    for key, field in inv.fields.items():
        try:
            val = (
                field.value_string or
                getattr(field, "value_date", None) or
                (field.value_currency.amount if field.value_currency else None) or
                getattr(field, "value_address", None) or
                getattr(field, "value_number", None)
            )
            print(f"{key}: {val} (confianza={field.confidence})")
        except Exception as e:
            print(f"{key}: (no se pudo leer) error={e}")
    print("==========================================================\n")

