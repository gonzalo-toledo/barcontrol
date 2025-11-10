from django.urls import path
from .views import (
    ProveedorListView,
    ProveedorCreateView,
    ProveedorUpdateView,
    ProveedorDeleteView,
)

urlpatterns = [
    path("", ProveedorListView.as_view(), name="proveedores_list"),
    path("nuevo/", ProveedorCreateView.as_view(), name="proveedores_create"),
    path("<int:pk>/editar/", ProveedorUpdateView.as_view(), name="proveedores_update"),
    path("<int:pk>/eliminar/", ProveedorDeleteView.as_view(), name="proveedores_delete"),
]
