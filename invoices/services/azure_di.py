from django.conf import settings
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

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

