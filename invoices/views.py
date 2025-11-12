from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
# from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils.http import urlencode

from .forms import UploadInvoiceForm, PreviewInvoiceForm
from .models import Factura, ItemFactura, TipoComprobante
from productos.models import Producto
from proveedores.models import Proveedor 
from .services import azure_blob
from .services.azure_blob import normalize_filename
from .services.azure_di import analyze_invoice_auto, debug_invoice_fields
from .services.mapping import map_invoice_result
from .services.ia_helper import get_ia_helper
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
    Muestra los datos detectados por la IA antes de guardar la factura.

    Incluye:
      - Verificación de proveedor existente
      - Validación de duplicados (proveedor + tipo comprobante + punto venta + número)
      - Asignación automática de productos reconocidos
      - Confirmación manual si algún producto no fue identificado
    """
    blob_url = request.session.get("preview_blob_url")
    mapped = request.session.get("preview_data")

    # Si no hay datos cargados → vuelve a la pantalla de carga
    if not mapped:
        return render(request, "invoices/preview.html", {
            "error": "No hay resultados para mostrar. Subí una factura nuevamente.",
        })

    header = mapped.get("header", {}) or {}
    items = mapped.get("items", []) or []

    # Diccionario de avisos para la vista
    avisos = {
        "proveedor_nuevo": False,
        "factura_duplicada": False,
        "productos_sin_match": [],  # [(idx, descripción)]
    }

    # --- 1️⃣ Validar proveedor ---
    prov_name = (header.get("vendor_name") or "").strip()
    prov_cuit = (header.get("vendor_tax_id") or "").replace("-", "").strip()

    proveedor = Proveedor.objects.filter(
        Q(nombre__iexact=prov_name) | Q(id_fiscal__iexact=prov_cuit)
    ).first()
    if not proveedor:
        avisos["proveedor_nuevo"] = True

    # --- 2️⃣ Validar duplicado con los datos del OCR (solo informativo, no bloqueante aún) ---
    tipo_codigo = header.get("tipo_comprobante")
    pto_vta = (header.get("punto_venta") or "").zfill(4)
    nro = header.get("invoice_id") or header.get("numero")

    tipo_comprobante = None
    if tipo_codigo:
        tipo_comprobante = TipoComprobante.objects.filter(codigo__iexact=tipo_codigo).first()

    if proveedor and tipo_comprobante and nro:
        duplicada = Factura.objects.filter(
            proveedor=proveedor,
            tipo_comprobante=tipo_comprobante,
            punto_venta=pto_vta,
            numero=nro,
        ).exists()
        avisos["factura_duplicada"] = duplicada

    # --- 3️⃣ Intentar asignar productos automáticamente con IA ---
    productos_existentes = Producto.objects.filter(activo=True).order_by("nombre")
    auto_products = []
    ia = get_ia_helper()
    
    for it in items:
        desc = (it.get("description") or "").strip()
        code = (it.get("product_code") or "").strip()

        prod = None
        #intentar por cód interno o proveedor (exacto)
        if code:
            prod = Producto.objects.filter(
                Q(codigo_interno__iexact=code) | Q(codigo_proveedor__iexact=code)
            ).first()

        #intentar por nombre (exacto)
        if not prod and desc:
            prod = Producto.objects.filter(nombre__iexact=desc).first()

        #intentar por similitud de semántica con IA (usando el singleton global)
        if not prod and desc:
            result = ia.find_best_product(desc)
            if result:
                prod, score = result
                print(f"🤖 IA asignó automáticamente '{desc}' → '{prod.nombre}' (similitud={score:.2f})")

        #Guardar el resultado o maracar como pendiente
        if prod:
            auto_products.append(prod.id)
        else:
            auto_products.append(None)
            avisos["productos_sin_match"].append(desc)

    # --- 4️⃣ Procesar envío del formulario (POST) ---
    if request.method == "POST":
        form = PreviewInvoiceForm(request.POST)

        # Mantiene los productos automáticos y agrega los manuales seleccionados
        selected_products = []
        for idx, it in enumerate(items):
            prod_id = auto_products[idx]
            if not prod_id:
                prod_id = request.POST.get(f"producto_{idx}")
            selected_products.append(prod_id)

        if form.is_valid():
            # Actualiza los valores de cabecera editados por el usuario
            header["vendor_name"] = form.cleaned_data["proveedor"]
            header["invoice_id"] = form.cleaned_data["numero"]
            header["invoice_date"] = (
                form.cleaned_data["fecha"].isoformat() if form.cleaned_data["fecha"] else None
            )
            header["subtotal"] = form.cleaned_data["subtotal"]
            header["total_tax"] = form.cleaned_data["total_impuestos"]
            header["invoice_total"] = form.cleaned_data["total"]

            # Guarda el mapeo actualizado en sesión (en formato JSON-safe)
            mapped["header"] = header
            mapped_safe = convert_to_json_safe(mapped)
            request.session["preview_data"] = mapped_safe
            
            # revalidar duplicado con los datos actualizados del formulario
            tipo = header.get("tipo_comprobante")
            pto_vta = (header.get("punto_venta") or "").zfill(4)
            nro = header.get("invoice_id") or header.get("numero")
            
            prov_name = (header.get("vendor_name") or "").strip()
            prov_cuit = (header.get("vendor_tax_id") or "").replace("-", "").strip()
            
            print("=== REVALIDANDO DUPLICADO CON DATOS ACTUALIZADOS ===")
            print("Proveedor:", prov_name)
            print("Tipo comprobante:", tipo)
            print("Punto de venta:", repr(pto_vta))
            print("Número:", repr(nro))
            
            if proveedor and tipo and nro:
                tipo_comprobante = TipoComprobante.objects.filter(codigo__iexact=tipo).first()
                duplicada = Factura.objects.filter(
                    proveedor=proveedor,
                    tipo_comprobante=tipo_comprobante,
                    punto_venta=pto_vta,
                    numero=nro,
                ).exists()
                
                print("¿Factura existente (revalidación)?", duplicada)

            if duplicada:
                messages.error(request, "⚠️ Esta factura ya existe en el sistema.")
                return render(request, "invoices/preview.html", {
                    "form": form,
                    "items": items,
                    "blob_url": blob_url,
                    "avisos": avisos,
                    "productos": productos_existentes,
                    "auto_products": auto_products,
                })

            # --- Verificar que no queden productos sin asignar ---
            pendientes = [p for p in selected_products if not p]
            if pendientes:
                messages.warning(request, "⚠️ Faltan asignar productos. Creá o seleccioná los que falten.")
                return render(request, "invoices/preview.html", {
                    "form": form,
                    "items": items,
                    "blob_url": blob_url,
                    "avisos": avisos,
                    "productos": productos_existentes,
                    "auto_products": auto_products,
                })

            # Guarda los productos seleccionados para confirmación final
            request.session["preview_selected_products"] = selected_products
            return redirect("confirm_invoice")

    else:
        # --- 5️⃣ Inicializa el formulario en modo lectura ---
        form = PreviewInvoiceForm(initial={
            "proveedor": header.get("vendor_name"),
            "numero": header.get("invoice_id"),
            "fecha": header.get("invoice_date"),
            "subtotal": header.get("subtotal"),
            "total_impuestos": header.get("total_tax"),
            "total": header.get("invoice_total"),
        })

    # --- 6️⃣ Combina ítems con su producto (si ya fue reconocido) ---
    paired_items = []
    for idx, it in enumerate(items):
        prod_id = auto_products[idx]
        prod_obj = Producto.objects.filter(id=prod_id).first() if prod_id else None
        paired_items.append({
            "data": it,
            "producto": prod_obj,
            "index": idx,
        })

    # --- 7️⃣ Render final ---
    return render(request, "invoices/preview.html", {
        "form": form,
        "items": paired_items,
        "blob_url": blob_url,
        "avisos": avisos,
        "productos": productos_existentes,
    })




# @login_required
def confirm_invoice(request):
    """
    Crea la factura y sus ítems en la base de datos usando los datos analizados.
    Incluye:
      - Validación de duplicados (proveedor + tipo comprobante + punto venta + número)
      - Asignación automática de productos
      - Manejo de transacciones atómicas (rollback si falla algo)
    """

    # Recupera de sesión los datos procesados por Azure o simulación
    blob_url = request.session.get("preview_blob_url")
    mapped = request.session.get("preview_data")

    # Si no hay datos previos en sesión → redirige a carga
    if not mapped:
        return redirect("upload_invoice")

    # Separa cabecera e ítems
    header = mapped.get("header", {})
    items = mapped.get("items", [])

    # --- 1️⃣ Buscar o crear proveedor ---
    proveedor, _ = Proveedor.objects.get_or_create(
        nombre=header.get("vendor_name") or "SIN PROVEEDOR",
        id_fiscal=header.get("vendor_tax_id") or None,
    )

    # --- 2️⃣ Datos básicos para validar duplicado ---
    tipo_codigo = header.get("tipo_comprobante")       # ej: "B"
    pto_vta = (header.get("punto_venta") or "").zfill(4)  # ej: "0002"
    nro = header.get("invoice_id") or header.get("numero")

    print("=== DEBUG FACTURA DUPLICADA ===")
    print("Proveedor:", proveedor.nombre)
    print("Tipo comprobante:", tipo_codigo)
    print("Punto de venta:", repr(pto_vta))
    print("Número:", repr(nro))

    # Busca el tipo de comprobante existente (Factura A, B, etc.)
    tipo_comprobante = None
    if tipo_codigo:
        tipo_comprobante = TipoComprobante.objects.filter(codigo__iexact=tipo_codigo).first()

    # --- 3️⃣ Verificación de duplicados ---
    if proveedor and tipo_comprobante and nro:
        existe = Factura.objects.filter(
            proveedor=proveedor,
            tipo_comprobante=tipo_comprobante,
            punto_venta=pto_vta,
            numero=nro
        ).exists()

        print("¿Factura existente?", existe)

        if existe:
            # Si ya existe → muestra mensaje y vuelve a la vista previa
            messages.error(request, "⚠️ Esta factura ya existe en el sistema.")
            return redirect("preview_invoice")

    # --- 4️⃣ Crear la factura (dentro de una transacción atómica) ---
    with transaction.atomic():
        factura = Factura.objects.create(
            proveedor=proveedor,
            tipo_comprobante=tipo_comprobante,
            punto_venta=pto_vta,
            numero=header.get("invoice_id") or "SIN NÚMERO",
            fecha=parse_date(header.get("invoice_date")) if header.get("invoice_date") else None,
            subtotal=header.get("subtotal") or 0,
            total_impuestos=header.get("total_tax") or 0,
            total=header.get("invoice_total") or 0,
            url_blob=blob_url,
        )

        # --- 5️⃣ Asignar productos a los ítems ---
        selected_products = request.session.get("preview_selected_products", [])

        for idx, it in enumerate(items):
            prod_id = selected_products[idx] if idx < len(selected_products) else None
            try:
                prod_id = int(prod_id)
            except (ValueError, TypeError):
                prod_id = None

            prod = Producto.objects.filter(id=prod_id).first() if prod_id else None

            # Crear ítem de factura (producto, impuesto o resumen)
            ItemFactura.objects.create(
                factura=factura,
                producto=prod if it.get("tipo_item") == "producto" else None,
                descripcion=it.get("description"),
                cantidad=it.get("quantity") or 0,
                unidad=it.get("unit"),
                precio_unitario=it.get("unit_price") or 0,
                importe=it.get("amount") or 0,
                codigo_producto=it.get("product_code"),
                tipo_item=it.get("tipo_item", "producto"),
            )

    # --- 6️⃣ Limpieza de sesión (para evitar reenvíos) ---
    for key in ["preview_data", "preview_blob_url", "preview_selected_products"]:
        request.session.pop(key, None)

    # --- 7️⃣ Confirmación visual ---
    messages.success(request, "✅ Factura registrada correctamente.")
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