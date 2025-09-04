from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils.http import urlencode

from .forms import UploadInvoiceForm
from .models import Invoice, InvoiceItem, Supplier
from .services import azure_blob
from .services.azure_blob import normalize_filename
from .services.azure_di import analyze_invoice_auto, debug_invoice_fields
from .services.mapping import map_invoice_result

def _d(s):  # parsea ISO a date o None
    if not s:
        return None
    if isinstance(s, date):
        return s
    return parse_date(str(s))

def upload_invoice(request):
    """
    Sube una factura a Blob, la analiza con Document Intelligence usando política automática
    (SAS preferente + fallback a bytes según umbral/tipo de error), mapea los datos y
    persiste en DB. Si algo falla al guardar, muestra previsualización con el error.
    """
    if request.method == "POST":
        form = UploadInvoiceForm(request.POST, request.FILES)
        if form.is_valid():
            upfile = form.cleaned_data["file"]

            # --- leer bytes una sola vez ---
            data = upfile.read()
            filename = upfile.name
            content_type = getattr(upfile, "content_type", "application/octet-stream")

            # 1) Subir a Blob (conservar original)
            try:
                
                safe_filename = normalize_filename(upfile.name)

                blob_url = azure_blob.upload_bytes(
                    settings.AZURE_BLOB_CONTAINER, data, safe_filename, content_type
                )
            except Exception as ex:
                return render(request, "invoices/preview.html", {
                    "error": f"Upload a Blob falló: {ex}",
                })

            # 2) Analizar con DI (automático: SAS preferente + fallback a bytes)
            try:
                di_result = analyze_invoice_auto(data, blob_url)
                # opcional para inspección en consola
                debug_invoice_fields(di_result)
            except Exception as ex:
                return render(request, "invoices/preview.html", {
                    "error": f"Análisis falló: {ex}",
                    "blob_url": blob_url
                })

            # 2.5) Mapear a estructura liviana (solo tipos JSON-friendly)
            mapped = map_invoice_result(di_result)
            request.session["last_blob_url"] = blob_url
            request.session["last_result"] = mapped

            # 3) Guardar en DB (sin pantalla de corrección por ahora)
            try:
                with transaction.atomic():
                    header = mapped.get("header", {}) or {}

                    # Supplier (catálogo)
                    supplier, created = Supplier.objects.get_or_create(
                        name=(header.get("vendor_name") or "SIN PROVEEDOR").strip(),
                        tax_id=(header.get("vendor_tax_id") or None),
                    )
                    # actualizar datos del proveedor (address) si disponemos
                    sup_addr = header.get("vendor_address")
                    fields_to_update = []
                    if sup_addr and supplier.address != sup_addr:
                        supplier.address = sup_addr
                        fields_to_update.append("address")

                    if fields_to_update:
                        supplier.save(update_fields=fields_to_update)

                    # Factura (cabecera)
                    inv = Invoice.objects.create(
                        supplier=supplier,
                        invoice_number=header.get("invoice_id") or filename,
                        invoice_date=_d(header.get("invoice_date")),
                        currency="ARS",
                        subtotal=header.get("subtotal") or None,
                        total_tax=header.get("total_tax") or None,
                        total=header.get("invoice_total") or None,
                        blob_url=blob_url,

                        # Extras que incorporaste
                        customer_name=header.get("customer_name"),
                        customer_tax_id=header.get("customer_tax_id"),
                        customer_address=header.get("customer_address"),

                        payment_term=header.get("payment_term"),
                        due_date=_d(header.get("due_date")),
                        service_start_date=_d(header.get("service_start_date")),
                        service_end_date=_d(header.get("service_end_date")),
                    )

                    # Ítems (si vienen)
                    for it in mapped.get("items", []):
                        InvoiceItem.objects.create(
                            invoice=inv,
                            product_name=it.get("description") or "(sin descripción)",
                            quantity=it.get("quantity"),
                            unit=(str(it.get("unit")) if it.get("unit") is not None else None),
                            unit_price=it.get("unit_price"),
                            line_total=it.get("amount"),
                            product_code=it.get("product_code"),
                            item_date=_d(it.get("date")),
                        )

                return redirect("invoice_detail", pk=inv.pk)

            except Exception as ex:
                # Si algo falla al guardar, mostramos preview con info extraída
                return render(request, "invoices/preview.html", {
                    "blob_url": blob_url,
                    "header": mapped.get("header"),
                    "items": mapped.get("items"),
                    "error": f"Guardado falló: {ex}",
                })
    else:
        form = UploadInvoiceForm()

    return render(request, "invoices/upload.html", {"form": form})


def preview_invoice(request):
    ctx = {
        "blob_url": request.session.get("last_blob_url"),
        "header": None,
        "items": None,
        "error": None
    }
    mapped = request.session.get("last_result")
    if not mapped:
        ctx["error"] = "No hay un resultado reciente para mostrar."
        return render(request, "invoices/preview.html", ctx)

    ctx["header"] = mapped.get("header")
    ctx["items"] = mapped.get("items", [])
    return render(request, "invoices/preview.html", ctx)


def _parse_date(s):
    if not s:
        return None
    # acepta "YYYY-MM-DD" (ej: 2025-08-14)
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal(s):
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, TypeError):
        return None


# --- nuevo: listado ---
def list_invoices(request):
    # params de filtro
    supplier_q = (request.GET.get("supplier") or "").strip()
    number_q   = (request.GET.get("number") or "").strip()
    date_from  = _parse_date(request.GET.get("date_from"))
    date_to    = _parse_date(request.GET.get("date_to"))
    total_min  = _parse_decimal(request.GET.get("total_min"))
    total_max  = _parse_decimal(request.GET.get("total_max"))
    item_q     = (request.GET.get("item") or "").strip()

    qs = Invoice.objects.select_related("supplier").all()

    if supplier_q:
        qs = qs.filter(supplier__name__icontains=supplier_q)
    if number_q:
        qs = qs.filter(invoice_number__icontains=number_q)
    if date_from:
        qs = qs.filter(invoice_date__gte=date_from)
    if date_to:
        qs = qs.filter(invoice_date__lte=date_to)
    if total_min is not None:
        qs = qs.filter(total__gte=total_min)
    if total_max is not None:
        qs = qs.filter(total__lte=total_max)

    # 🔎 filtro por ítems (descripción y/o código)
    if item_q:
        qs = qs.filter(
            Q(items__product_name__icontains=item_q) |
            Q(items__product_code__icontains=item_q)
        ).distinct()

    qs = qs.order_by("-invoice_date", "-id")

    # paginación
    page_number = request.GET.get("page") or 1
    paginator = Paginator(qs, 15)  # 15 filas por página
    page_obj = paginator.get_page(page_number)

    # para el selector de proveedor (opcional)
    suppliers = Supplier.objects.order_by("name").values_list("name", flat=True).distinct()

    # conservar los parámetros sin "page" para la paginación
    params_without_page = request.GET.dict()
    params_without_page.pop("page", None)
    base_qs = urlencode(params_without_page)

    ctx = {
        "page_obj": page_obj,
        "paginator": paginator,
        "current_params": request.GET,
        "base_qs": f"&{base_qs}" if base_qs else "",
        "suppliers": suppliers,
    }
    return render(request, "invoices/list.html", ctx)

# --- nuevo: detalle ---
def invoice_detail(request, pk: int):
    inv = get_object_or_404(Invoice.objects.select_related('supplier').prefetch_related('items'), pk=pk)
    return render(request, "invoices/detail.html", {"inv": inv})

# --- nuevo: ver original (SAS redirect) ---
def invoice_view_original(request, pk: int):
    inv = get_object_or_404(Invoice, pk=pk)
    blob_name = azure_blob.to_blob_name_from_url(inv.blob_url)
    sas = azure_blob.make_sas_url(settings.AZURE_BLOB_CONTAINER, blob_name, minutes=10)
    if not sas:
        # Fallback: servir desde Django (no ideal para archivos grandes)
        data = azure_blob.download_bytes(settings.AZURE_BLOB_CONTAINER, blob_name)
        from django.http import StreamingHttpResponse
        ct = "application/pdf" if inv.blob_url.lower().endswith(".pdf") else "application/octet-stream"
        resp = StreamingHttpResponse(iter([data]), content_type=ct)
        resp["Content-Disposition"] = f'inline; filename="{blob_name}"'
        return resp
    return redirect(sas)