from django.urls import path
from .views import (
    ProductoListView,
    ProductoCreateView,
    ProductoUpdateView,
    ProductoDeleteView,
)

urlpatterns = [
    path("", ProductoListView.as_view(), name="productos_list"),
    path("nuevo/", ProductoCreateView.as_view(), name="productos_create"),
    path("<int:pk>/editar/", ProductoUpdateView.as_view(), name="productos_update"),
    path("<int:pk>/eliminar/", ProductoDeleteView.as_view(), name="productos_delete"),
]
