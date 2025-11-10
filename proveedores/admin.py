from django.contrib import admin

# Register your models here.
from proveedores.models import Proveedor

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'id_fiscal','condicion_iva','direccion', 'email', 'telefono')