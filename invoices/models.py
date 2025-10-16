from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# -------------------------------------------------------------
# PRODUCTO
# -------------------------------------------------------------
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


# -------------------------------------------------------------
# CATÁLOGOS ARCA / REFERENCIAS FIJAS
# -------------------------------------------------------------
class TipoComprobante(models.Model):
    codigo = models.CharField(max_length=3, unique=True)  # A, B, C, M, NC, ND...
    descripcion = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tipo de comprobante"
        verbose_name_plural = "Tipos de comprobante"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"


class CondicionIVA(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Condición frente al IVA"
        verbose_name_plural = "Condiciones frente al IVA"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class CondicionPago(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    dias = models.PositiveIntegerField(default=0, help_text="Días de crédito (0 = contado)")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Condición de pago"
        verbose_name_plural = "Condiciones de pago"
        ordering = ["dias", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.dias} días)"


# -------------------------------------------------------------
# PROVEEDOR
# -------------------------------------------------------------
class Proveedor(models.Model):
    nombre = models.CharField(max_length=255)
    id_fiscal = models.CharField("CUIT / ID Fiscal", max_length=20, null=True, blank=True)
    condicion_iva = models.ForeignKey(
        "CondicionIVA", null=True, blank=True, on_delete=models.SET_NULL
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


# -------------------------------------------------------------
# FACTURA
# -------------------------------------------------------------
class Factura(models.Model):
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name="facturas")

    tipo_comprobante = models.ForeignKey(
        "TipoComprobante", null=True, blank=True, on_delete=models.SET_NULL
    )
    condicion_pago = models.ForeignKey(
        "CondicionPago", null=True, blank=True, on_delete=models.SET_NULL
    )

    punto_venta = models.CharField(max_length=5, null=True, blank=True)
    numero = models.CharField(max_length=128, null=True, blank=True)

    cae = models.CharField("Código de autorización fiscal (ARCA)", max_length=20, null=True, blank=True)
    vto_cae = models.DateField("Vencimiento CAE", null=True, blank=True)

    fecha = models.DateField(null=True, blank=True)
    moneda = models.CharField(max_length=10, default="ARS")
    tipo_cambio = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_impuestos = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)

    cliente_nombre = models.CharField(max_length=255, null=True, blank=True)
    cliente_id_fiscal = models.CharField(max_length=20, null=True, blank=True)
    cliente_direccion = models.CharField(max_length=255, null=True, blank=True)

    servicio_desde = models.DateField(null=True, blank=True)
    servicio_hasta = models.DateField(null=True, blank=True)
    vencimiento = models.DateField(null=True, blank=True)

    url_blob = models.URLField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="facturas_creadas")
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="facturas_editadas")

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["fecha"]),
            models.Index(fields=["numero"]),
            models.Index(fields=["tipo_comprobante", "punto_venta"]),
        ]

    def __str__(self):
        tipo = self.tipo_comprobante.codigo if self.tipo_comprobante else "-"
        return f"{tipo} {self.punto_venta or ''}-{self.numero or ''} ({self.proveedor.nombre})"


# -------------------------------------------------------------
# ÍTEM FACTURA
# -------------------------------------------------------------
class ItemFactura(models.Model):
    TIPO_CHOICES = [
        ("producto", "producto/servicio"),
        ("impuesto", "Impuesto/Retención"),
        ("resumen", "Subtotal/Total"),
    ]
    
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey("Producto", null=True, blank=True, on_delete=models.SET_NULL)

    descripcion = models.CharField(max_length=255, null=True, blank=True)
    codigo_producto = models.CharField(max_length=64, null=True, blank=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    unidad = models.CharField(max_length=20, null=True, blank=True)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    importe = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    alic_iva = models.DecimalField("Alicuota IVA (%)", max_digits=5, decimal_places=2, null=True, blank=True)
    codigo_fiscal = models.CharField("Código ARCA / fiscal", max_length=10, null=True, blank=True)
    
    tipo_item = models.CharField(
        max_length=20, 
        choices=TIPO_CHOICES,
        default="producto",
    )

    class Meta:
        verbose_name = "Ítem de factura"
        verbose_name_plural = "Ítems de factura"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["codigo_producto"]),
            models.Index(fields=["descripcion"]),
        ]

    def __str__(self):
        return self.descripcion or "(ítem)"
