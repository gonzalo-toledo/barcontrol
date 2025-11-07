from typing import Any, Dict, List
from datetime import date, datetime


# --- Funciones auxiliares ---
def _to_iso(d):
    if isinstance(d, (date, datetime)):
        return d.isoformat()
    return d


def _address_to_str(addr):
    if not addr:
        return None
    parts = [
        getattr(addr, "house_number", None),
        getattr(addr, "road", None),
        getattr(addr, "city", None),
        getattr(addr, "unit", None),
    ]
    s = " ".join([p for p in parts if p]).strip()
    return s or getattr(addr, "street_address", None) or None


def _field_value(fields: dict, name: str, kind: str):
    f = fields.get(name)
    if not f:
        return None, None
    try:
        if kind == "value_currency":
            amt = getattr(f.value_currency, "amount", None) if f.value_currency else None
            return amt, f.confidence
        elif kind == "value_address":
            return _address_to_str(f.value_address), f.confidence
        elif kind == "value_date":
            return _to_iso(getattr(f, kind, None)), f.confidence
        else:
            return getattr(f, kind, None), f.confidence
    except Exception:
        return None, None


# --- Calificador de tipo de ítem ---
def calificar_item(descripcion: str) -> str:
    """
    Detecta si el ítem es un producto, impuesto o subtotal/total
    """
    if not descripcion:
        return "producto"
    desc = descripcion.lower()
    if any(p in desc for p in ["iva", "impuesto", "retención", "retencion", "percepción", "percepcion"]):
        return "impuesto"
    if any(p in desc for p in ["subtotal", "total", "saldo"]):
        return "resumen"
    return "producto"


# --- Mapeo general ---
def map_invoice_result(di_result) -> Dict[str, Any]:
    if not di_result or not di_result.documents:
        return {"header": {}, "items": []}

    inv = di_result.documents[0]
    fields = inv.fields or {}

    # --- CABECERA ---
    vendor_name, vendor_name_c = _field_value(fields, "VendorName", "value_string")
    vendor_tax_id, _ = _field_value(fields, "VendorTaxId", "value_string")
    vendor_address, _ = _field_value(fields, "VendorAddress", "value_address")
    vendor_address_recipient, _ = _field_value(fields, "VendorAddressRecipient", "value_string")

    customer_name, _ = _field_value(fields, "CustomerName", "value_string")
    customer_tax_id, _ = _field_value(fields, "CustomerTaxId", "value_string")
    customer_address, _ = _field_value(fields, "CustomerAddress", "value_address")
    customer_address_recipient, _ = _field_value(fields, "CustomerAddressRecipient", "value_string")

    invoice_id, _ = _field_value(fields, "InvoiceId", "value_string")
    invoice_date, _ = _field_value(fields, "InvoiceDate", "value_date")
    due_date, _ = _field_value(fields, "DueDate", "value_date")
    subtotal, _ = _field_value(fields, "SubTotal", "value_currency")
    total_tax, _ = _field_value(fields, "TotalTax", "value_currency")
    invoice_total, invoice_total_c = _field_value(fields, "InvoiceTotal", "value_currency")
    payment_term, _ = _field_value(fields, "PaymentTerm", "value_string")
    service_start_date, _ = _field_value(fields, "ServiceStartDate", "value_date")
    service_end_date, _ = _field_value(fields, "ServiceEndDate", "value_date")

    # --- CAMPOS ESPECÍFICOS (si los encuentra) ---
    tipo_comprobante, _ = _field_value(fields, "InvoiceType", "value_string")
    punto_venta, _ = _field_value(fields, "PointOfSale", "value_string")
    cae, _ = _field_value(fields, "CAE", "value_string")
    vto_cae, _ = _field_value(fields, "CAEDueDate", "value_date")
    moneda, _ = _field_value(fields, "Currency", "value_string")
    tipo_cambio, _ = _field_value(fields, "ExchangeRate", "value_currency")

    # --- ITEMS ---
    items_list: List[Dict[str, Any]] = []
    items_field = fields.get("Items")
    if items_field and getattr(items_field, "value_array", None):
        for it in items_field.value_array:
            obj = getattr(it, "value_object", None) or {}

            def gv(key, attr):
                field = obj.get(key)
                if not field:
                    return None
                try:
                    if attr == "value_currency":
                        return field.value_currency.amount if field.value_currency else None
                    val = getattr(field, attr, None)
                    if attr == "value_date":
                        return _to_iso(val)
                    return val
                except Exception:
                    return None

            desc = gv("Description", "value_string")
            tipo_item = calificar_item(desc)

            items_list.append({
                "description": desc,
                "quantity": gv("Quantity", "value_number"),
                "unit": gv("Unit", "value_string") or gv("Unit", "value_number"),
                "unit_price": gv("UnitPrice", "value_currency"),
                "amount": gv("Amount", "value_currency"),
                "product_code": gv("ProductCode", "value_string"),
                "date": gv("Date", "value_date"),
                "tax": gv("Tax", "value_string"),
                "tipo_item": tipo_item,
            })

    # --- RETORNO FINAL ---
    return {
        "header": {
            "vendor_name": vendor_name,
            "vendor_name_confidence": vendor_name_c,
            "vendor_tax_id": vendor_tax_id,
            "vendor_address": vendor_address,
            "vendor_address_recipient": vendor_address_recipient,
            "customer_name": customer_name,
            "customer_tax_id": customer_tax_id,
            "customer_address": customer_address,
            "customer_address_recipient": customer_address_recipient,
            "invoice_id": invoice_id,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "subtotal": subtotal,
            "total_tax": total_tax,
            "invoice_total": invoice_total,
            "invoice_total_confidence": invoice_total_c,
            "payment_term": payment_term,
            "service_start_date": service_start_date,
            "service_end_date": service_end_date,
            # Nuevos campos
            "tipo_comprobante": tipo_comprobante,
            "punto_venta": punto_venta,
            "cae": cae,
            "vto_cae": vto_cae,
            "moneda": moneda,
            "tipo_cambio": tipo_cambio,
        },
        "items": items_list,
    }
