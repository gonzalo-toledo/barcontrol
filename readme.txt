python manage.py shell


from invoices.models import TipoComprobante, CondicionIVA, CondicionPago

TipoComprobante.objects.bulk_create([
    TipoComprobante(codigo="A", descripcion="Factura A"),
    TipoComprobante(codigo="B", descripcion="Factura B"),
    TipoComprobante(codigo="C", descripcion="Factura C"),
    TipoComprobante(codigo="M", descripcion="Factura M"),
    TipoComprobante(codigo="NC", descripcion="Nota de crédito"),
    TipoComprobante(codigo="ND", descripcion="Nota de débito"),
])

CondicionIVA.objects.bulk_create([
    CondicionIVA(nombre="Responsable Inscripto"),
    CondicionIVA(nombre="Monotributista"),
    CondicionIVA(nombre="Exento"),
    CondicionIVA(nombre="Consumidor Final"),
])

CondicionPago.objects.bulk_create([
    CondicionPago(nombre="Contado", dias=0),
    CondicionPago(nombre="15 días", dias=15),
    CondicionPago(nombre="30 días", dias=30),
    CondicionPago(nombre="Transferencia inmediata", dias=0),
])
