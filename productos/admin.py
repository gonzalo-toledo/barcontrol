from django.contrib import admin

# Register your models here.

from productos.models import Producto, ProductoEmbedding

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_interno', 'codigo_proveedor', 'codigo_barras', 'categoria', 'marca', 'unidad_base', 'activo')
    list_filter = ('categoria', 'marca', 'unidad_base', 'activo')
    search_fields = ('nombre', 'codigo_interno', 'codigo_proveedor', 'codigo_barras')
    
    
@admin.register(ProductoEmbedding)
class ProductoEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('producto', 'vector', 'modelo', 'actualizado')