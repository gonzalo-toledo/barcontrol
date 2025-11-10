from django.db import models

# Create your models here.
class Proveedor(models.Model):
    nombre = models.CharField(max_length=255)
    id_fiscal = models.CharField("CUIT / ID Fiscal", max_length=20, null=True, blank=True)
    condicion_iva = models.ForeignKey(
        "invoices.CondicionIVA", null=True, blank=True, on_delete=models.SET_NULL
    )
    direccion = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    telefono = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        unique_together = [("nombre", "id_fiscal")]
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.id_fiscal or 's/ID'})"
