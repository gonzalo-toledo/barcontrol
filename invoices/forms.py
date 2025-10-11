from django import forms

class UploadInvoiceForm(forms.Form):
    file = forms.FileField(
        label="Factura (PDF/JPG/PNG)",
        allow_empty_file=False
    )
    # use_bytes = forms.BooleanField(
    #     required=False, initial=True,
    #     label="Procesar enviando bytes (sin URL SAS)"
    # )

class PreviewInvoiceForm(forms.Form):
    proveedor = forms.CharField(label="Proveedor", max_length=255)
    numero = forms.CharField(label="Número de Factura", max_length=128)
    fecha = forms.DateField(label="Fecha", required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    subtotal = forms.DecimalField(label="Subtotal", required=False, decimal_places=2, max_digits=12)
    total_impuestos = forms.DecimalField(label="Impuestos", required=False, decimal_places=2, max_digits=12)
    total = forms.DecimalField(label="Total", required=False, decimal_places=2, max_digits=12)
