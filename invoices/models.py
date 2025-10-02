from django.db import models

class Proveedor(models.Model):
    nombre = models.CharField("Nombre", max_length=255, db_index=True)
    id_fiscal = models.CharField("ID fiscal / CUIT", max_length=64, blank=True, null=True, db_index=True)
    direccion = models.TextField("Dirección", blank=True, null=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        unique_together = ('nombre', 'id_fiscal')

    def __str__(self):
        return f"{self.nombre} ({self.id_fiscal})" if self.id_fiscal else self.nombre


class Factura(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='facturas', verbose_name="Proveedor")
    numero = models.CharField("Número de factura", max_length=128, db_index=True)
    fecha = models.DateField("Fecha de factura", null=True, blank=True, db_index=True)
    moneda = models.CharField("Moneda", max_length=8, default='ARS')
    subtotal = models.DecimalField("Subtotal", max_digits=18, decimal_places=2, null=True, blank=True)
    total_impuestos = models.DecimalField("Total impuestos", max_digits=18, decimal_places=2, null=True, blank=True)
    total = models.DecimalField("Total", max_digits=18, decimal_places=2, null=True, blank=True)
    url_blob = models.TextField("URL del blob")
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    # Datos de cliente (extraídos, se guardan con nombres en español)
    cliente_nombre = models.CharField("Nombre del cliente", max_length=255, blank=True, null=True)
    cliente_id_fiscal = models.CharField("ID fiscal del cliente", max_length=64, blank=True, null=True)
    cliente_direccion = models.TextField("Dirección del cliente", blank=True, null=True)

    condicion_pago = models.CharField("Condición de pago", max_length=100, blank=True, null=True)

    # Fechas extra
    vencimiento = models.DateField("Vencimiento", blank=True, null=True)
    servicio_desde = models.DateField("Servicio desde", blank=True, null=True)
    servicio_hasta = models.DateField("Servicio hasta", blank=True, null=True)

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        indexes = [models.Index(fields=['fecha'])]
        unique_together = ('proveedor', 'numero')

    def __str__(self):
        return f"{self.numero} - {self.proveedor.nombre}"


class ItemFactura(models.Model):
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='items', verbose_name="Factura")
    descripcion = models.CharField("Descripción del producto/servicio", max_length=512, db_index=True)
    cantidad = models.DecimalField("Cantidad", max_digits=18, decimal_places=3, null=True, blank=True)
    unidad = models.CharField("Unidad", max_length=32, blank=True, null=True)
    precio_unitario = models.DecimalField("Precio unitario", max_digits=18, decimal_places=4, null=True, blank=True)
    importe = models.DecimalField("Importe (línea)", max_digits=18, decimal_places=2, null=True, blank=True)
    codigo_producto = models.CharField("Código de producto", max_length=128, blank=True, null=True)
    fecha_item = models.DateField("Fecha del ítem", null=True, blank=True)

    class Meta:
        verbose_name = "Ítem de factura"
        verbose_name_plural = "Ítems de factura"

    def __str__(self):
        return f"{self.descripcion} ({self.cantidad} {self.unidad or ''})"
