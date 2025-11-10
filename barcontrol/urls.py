from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('invoices.urls')),
    path('productos/', include('productos.urls')),
    path("proveedores/", include("proveedores.urls")),
    path("accounts/", include("accounts.urls")),
]
