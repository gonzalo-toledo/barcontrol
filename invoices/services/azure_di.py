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
    - DI_ANALYZE_MODE = 'sas': intenta SAS -> fallback bytes
    - DI_ANALYZE_MODE = 'bytes': bytes directo
    - DI_ANALYZE_MODE = 'auto' (default):
        * si len(data) <= DI_INLINE_BYTES_MAX_MB -> bytes
        * si > umbral -> intenta SAS -> fallback bytes
    """
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

