from django import forms

class UploadInvoiceForm(forms.Form):
    file = forms.FileField(
        label="Factura (PDF/JPG/PNG)",
        allow_empty_file=False
    )
    use_bytes = forms.BooleanField(
        required=False, initial=True,
        label="Procesar enviando bytes (sin URL SAS)"
    )
