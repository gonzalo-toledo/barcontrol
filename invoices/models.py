from django.db import models

class Supplier(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    tax_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    address = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('name', 'tax_id')

    def __str__(self):
        return f"{self.name} ({self.tax_id})" if self.tax_id else self.name

class Invoice(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='invoices')
    invoice_number = models.CharField(max_length=128, db_index=True)
    invoice_date = models.DateField(null=True, blank=True, db_index=True)
    currency = models.CharField(max_length=8, default='ARS')
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    total_tax = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    blob_url = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # NEW: campos extraídos que no guardábamos aún
    # Customer
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    customer_tax_id = models.CharField(max_length=64, blank=True, null=True)
    payment_term = models.CharField(max_length=100, blank=True, null=True)
    customer_address = models.TextField(blank=True, null=True)
    
    # Invoice Dates
    
    due_date = models.DateField(blank=True, null=True)
    service_start_date = models.DateField(blank=True, null=True)
    service_end_date = models.DateField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=['invoice_date'])]
        unique_together = ('supplier', 'invoice_number')

    def __str__(self):
        return f"{self.invoice_number} - {self.supplier.name}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=512, db_index=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    unit = models.CharField(max_length=32, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    line_total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    product_code = models.CharField(max_length=128, blank=True, null=True)
    item_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.product_name} ({self.quantity} {self.unit or ''})"
