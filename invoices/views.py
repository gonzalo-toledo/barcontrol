from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
# from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils.http import urlencode

from .forms import UploadInvoiceForm, PreviewInvoiceForm
from .models import Factura, ItemFactura, Proveedor
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

# Conversión a tipos seguros para JSON (floats y strings)
def convert_to_json_safe(obj):
    if isinstance(obj, dict):
        return {k: convert_to_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_safe(v) for v in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj

            
# @login_required
def upload_invoice(request):
    """
    Sube una factura a Blob, la analiza con Document Intelligence usando política automática
    (SAS preferente + fallback a bytes según umbral/tipo de error) y muestra previsualización ANTES de guardar.
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
                
                safe_filename = normalize_filename(filename)

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
            mapped_safe = convert_to_json_safe(mapped)

            # Guardar resultados en sesión (modo simulación o Azure indistinto)
            request.session["preview_blob_url"] = blob_url
            request.session["preview_data"] = mapped_safe

            return redirect("preview_invoice")

    else:
        form = UploadInvoiceForm()

    return render(request, "invoices/upload.html", {"form": form})


# @login_required
def preview_invoice(request):
    """
    Muestra los datos detectados por la IA antes de guardar la factura
    """
    
    blob_url = request.session.get("preview_blob_url")
    mapped = request.session.get("preview_data")
    
    if not mapped:
        return render (
            request,
            "invoices/preview.html",
            {"error": "No hay resultados para mostrar. Subí una factura nuevamente."},  
        )
        
    header = mapped.get("header", {})
    items = mapped.get("items", [])
    
    # Si el usuario confirma, redirigue a confirm_invoice    
    if request.method == "POST":
        form = PreviewInvoiceForm(request.POST)
        if form.is_valid():
            # Reemplaza los valores detectados por los corregidos del usuario
            header["vendor_name"] = form.cleaned_data["proveedor"]
            header["invoice_id"] = form.cleaned_data["numero"]
            header["invoice_date"] = form.cleaned_data["fecha"].isoformat() if form.cleaned_data["fecha"] else None
            header["subtotal"] = form.cleaned_data["subtotal"]
            header["total_impuestos"] = form.cleaned_data["total_impuestos"]
            header["invoice_total"] = form.cleaned_data["total"]

            # Guardar correcciones en la sesión antes de confirmar
            mapped["header"] = header
            
            # converetir a JSON-safe antes de guardar
            mapped_safe = convert_to_json_safe(mapped)
            request.session["preview_data"] = mapped_safe

            return redirect("confirm_invoice")
    else:
        form = PreviewInvoiceForm(initial={
            "proveedor": header.get("vendor_name"),
            "numero": header.get("invoice_id"),
            "fecha": header.get("invoice_date"),
            "subtotal": header.get("subtotal"),
            "total_impuestos": header.get("total_tax"),
            "total": header.get("invoice_total"),
        })
    
    return render(
        request,
        "invoices/preview.html",
        {"form": form, "items": items, "blob_url": blob_url},
    )
    

# @login_required
def confirm_invoice(request):
    """
    Crea la factura y sus items en la base de datos usando los datos analizados
    """

    blob_url = request.session.get("preview_blob_url")
    mapped = request.session.get("preview_data")

    if not mapped:
        return redirect("upload_invoice")
    
    header = mapped.get("header", {})
    items = mapped.get("items", [])
    
    with transaction.atomic():
        proveedor, _ = Proveedor.objects.get_or_create(
            nombre=header.get("vendor_name") or "SIN PROVEEDOR",
            id_fiscal=header.get("vendor_tax_id") or None,
        )

        factura = Factura.objects.create(
            proveedor=proveedor,
            numero=header.get("invoice_id") or "SIN NÚMERO",
            fecha=parse_date(header.get("invoice_date")) if header.get("invoice_date") else None,
            subtotal=header.get("subtotal") or 0,
            total_impuestos=header.get("total_tax") or 0,
            total=header.get("invoice_total") or 0,
            url_blob=blob_url,
        )

        for it in items:
            ItemFactura.objects.create(
                factura=factura,
                descripcion=it.get("description"),
                cantidad=it.get("quantity") or 0,
                unidad=it.get("unit"),
                precio_unitario=it.get("unit_price") or 0,
                importe=it.get("amount") or 0,
                codigo_producto=it.get("product_code"),
            )

    # limpiar sesión
    request.session.pop("preview_data", None)
    request.session.pop("preview_blob_url", None)

    return redirect("invoice_detail", pk=factura.pk) 


def _parse_date(s):
    if not s:
        return None
    # acepta "YYYY-MM-DD" (ej: 2025-08-14)
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal(s):
    """
    Convierte una cadena en Decimal o None.
    - Devuelve None si está vacía, es inválida o si el tipo no es compatible.
    """
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

    # QuerySet base
    qs = Factura.objects.select_related("proveedor").all()

    # Filtros
    if supplier_q:
        qs = qs.filter(proveedor__nombre__icontains=supplier_q)
    if number_q:
        qs = qs.filter(numero__icontains=number_q)
    if date_from:
        qs = qs.filter(fecha__gte=date_from)
    if date_to:
        qs = qs.filter(fecha__lte=date_to)
    if total_min is not None:
        qs = qs.filter(total__gte=total_min)
    if total_max is not None:
        qs = qs.filter(total__lte=total_max)

    # 🔎 búsqueda por ítems (descripción / código)
    if item_q:
        qs = qs.filter(
            Q(items__descripcion__icontains=item_q) |
            Q(items__codigo_producto__icontains=item_q)
        ).distinct()

    qs = qs.order_by("-fecha", "-id")

    # proveedores para selector
    suppliers = Proveedor.objects.order_by("nombre").values_list("nombre", flat=True).distinct()

    # paginación
    page_number = request.GET.get("page") or 1
    paginator = Paginator(qs, 15)  # 15 filas por página
    page_obj = paginator.get_page(page_number)

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
    inv = get_object_or_404(Factura.objects.select_related('proveedor').prefetch_related('items'), pk=pk)
    return render(request, "invoices/detail.html", {"inv": inv})

# --- nuevo: ver original (SAS redirect) ---
def invoice_view_original(request, pk: int):
    inv = get_object_or_404(Factura, pk=pk)
    blob_name = azure_blob.to_blob_name_from_url(inv.url_blob)
    sas = azure_blob.make_sas_url(settings.AZURE_BLOB_CONTAINER, blob_name, minutes=10)
    if not sas:
        # Fallback: servir desde Django (no ideal para archivos grandes)
        data = azure_blob.download_bytes(settings.AZURE_BLOB_CONTAINER, blob_name)
        from django.http import StreamingHttpResponse
        ct = "application/pdf" if inv.url_blob.lower().endswith(".pdf") else "application/octet-stream"
        resp = StreamingHttpResponse(iter([data]), content_type=ct)
        resp["Content-Disposition"] = f'inline; filename="{blob_name}"'
        return resp
    return redirect(sas)