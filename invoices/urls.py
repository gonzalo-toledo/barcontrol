from django.urls import path
from .views import upload_invoice, preview_invoice, list_invoices, invoice_detail, invoice_view_original, confirm_invoice

urlpatterns = [
    path('', upload_invoice, name='upload_invoice'),
    path('preview/', preview_invoice, name='preview_invoice'),
    path('confirmar/', confirm_invoice, name='confirm_invoice'),
    path('confirmar/', confirm_invoice, name='confirm_invoice'),
    path('facturas/', list_invoices, name='list_invoices'),
    path('facturas/<int:pk>/', invoice_detail, name='invoice_detail'),
    path('facturas/<int:pk>/ver-original/', invoice_view_original, name='invoice_view_original'),
]
