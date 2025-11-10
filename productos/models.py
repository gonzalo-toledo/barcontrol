from django.db import models

# Create your models here.
class Producto(models.Model):
    nombre = models.CharField(max_length=255)
    codigo_interno = models.CharField(max_length=64, null=True, blank=True)   # tu SKU interno
    codigo_proveedor = models.CharField(max_length=64, null=True, blank=True) # código que viene en la factura
    codigo_barras = models.CharField(max_length=64, null=True, blank=True)
    categoria = models.CharField(max_length=128, null=True, blank=True)
    marca = models.CharField(max_length=128, null=True, blank=True)
    unidad_base = models.CharField(max_length=20, null=True, blank=True)      # ej: un, kg, lt
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        indexes = [
            models.Index(fields=["codigo_interno"]),
            models.Index(fields=["codigo_proveedor"]),
            models.Index(fields=["codigo_barras"]),
            models.Index(fields=["nombre"]),
        ]
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre