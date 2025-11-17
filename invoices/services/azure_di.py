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
    """
    Ejecuta prebuilt-invoice pasando una URL (idealmente con SAS).
    Devuelve el objeto 'result' del poller.
    """
    client = _di_client()
    model_id = settings.AZ_DOCINT_MODEL or "prebuilt-invoice"
    poller = client.begin_analyze_document(model_id, AnalyzeDocumentRequest(url_source=file_url))
    return poller.result()

def analyze_invoice_from_bytes(data: bytes):
    """
    Ejecuta prebuilt-invoice enviando bytes (no necesita SAS).
    content_type se ignora para DI; solo es útil para tu control.
    """
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
    
    # -------------------------------------------------------------
    # MODO SIMULACIÓN
    # -------------------------------------------------------------
    # --- MODO SIMULACIÓN (actualizado con campos argentinos) ---
    if getattr(settings, "USE_AZURE_SIMULATION", False):
        print("⚙️  MODO SIMULACIÓN ACTIVADO - Azure DI no está siendo usado.")
        from types import SimpleNamespace
        import datetime

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
                self.value_number = float(value_number) if value_number is not None else None
                self.value_currency = (
                    SimpleNamespace(amount=float(value_currency))
                    if value_currency is not None
                    else None
                )
                self.value_date = value_date
                self.value_address = value_address
                self.confidence = 0.99

        # --- Ítems simulados (sin IVA) ---
        fake_items = [
            SimpleNamespace(
                value_object={
                    "Description": FakeField(value_string="Aceite Natura 1L"),
                    "Quantity": FakeField(value_number=6),
                    "UnitPrice": FakeField(value_currency=1300.0),
                    "Amount": FakeField(value_currency=7800.0),
                }
            ),
            SimpleNamespace(
                value_object={
                    "Description": FakeField(value_string="Yerba M. Playadito 1kg"),
                    "Quantity": FakeField(value_number=3),
                    "UnitPrice": FakeField(value_currency=2100.0),
                    "Amount": FakeField(value_currency=6300.0),
                }
            ),
            SimpleNamespace(
                value_object={
                    "Description": FakeField(value_string="Harina Pureza 000"),
                    "Quantity": FakeField(value_number=10),
                    "UnitPrice": FakeField(value_currency=950.0),
                    "Amount": FakeField(value_currency=9500.0),
                }
            ),
            SimpleNamespace(
                value_object={
                    "Description": FakeField(value_string="Spaghetti Lucchetti 500g"),
                    "Quantity": FakeField(value_number=12),
                    "UnitPrice": FakeField(value_currency=750.0),
                    "Amount": FakeField(value_currency=9000.0),
                }
            ),
            SimpleNamespace(
                value_object={
                    "Description": FakeField(value_string="Coca Cola 1.5L"),
                    "Quantity": FakeField(value_number=8),
                    "UnitPrice": FakeField(value_currency=1800.0),
                    "Amount": FakeField(value_currency=14400.0),
                }
            ),
        ]

        # --- Totales coherentes ---
        subtotal = sum(it.value_object["Amount"].value_currency.amount for it in fake_items)
        total_tax = round(subtotal * 0.21, 2)
        total = subtotal + total_tax

        # --- Campos principales simulados ---
        fake_fields = {
            "VendorName": FakeField(value_string="Distribuidora Río Cuarto SRL"),
            "VendorTaxId": FakeField(value_string="30-87654321-0"),
            "VendorAddress": FakeField(value_address="Av. Italia 950"),
            "InvoiceId": FakeField(value_string="000456"),
            "InvoiceDate": FakeField(value_date=datetime.date(2025, 10, 12)),
            "SubTotal": FakeField(value_currency=subtotal),
            "TotalTax": FakeField(value_currency=total_tax),
            "InvoiceTotal": FakeField(value_currency=total),
            "PaymentTerm": FakeField(value_string="Cuenta Corriente 30 días"),

            # --- Campos argentinos / fiscales ---
            "InvoiceType": FakeField(value_string="B"),  # tipo comprobante
            "PointOfSale": FakeField(value_string="0002"),
            "CAE": FakeField(value_string="67891234567891"),
            "CAEDueDate": FakeField(value_date=datetime.date(2025, 11, 12)),
            "Currency": FakeField(value_string="ARS"),
            "ExchangeRate": FakeField(value_currency=1.0),

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

