from django.contrib import admin

# Register your models here.
from invoices.models import Factura, ItemFactura

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'proveedor', 'tipo_comprobante', 'condicion_pago', 'punto_venta','fecha', 'subtotal', 'total_impuestos', 'total')
    search_fields = ('proveedor',)


@admin.register(ItemFactura)
class ItemFacturaAdmin(admin.ModelAdmin):
    list_display = ('factura', 'producto', 'cantidad', 'precio_unitario', 'importe')  
    search_fields = ('factura', 'producto')