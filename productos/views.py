from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Producto

class ProductoListView(ListView):
    model = Producto
    template_name = "productos/list.html"
    context_object_name = "productos"

class ProductoCreateView(CreateView):
    model = Producto
    fields = ["nombre", "codigo_interno", "codigo_proveedor", "codigo_barras", "categoria", "marca", "unidad_base", "activo"]
    template_name = "productos/form.html"
    success_url = reverse_lazy("productos_list")

    def form_valid(self, form):
        messages.success(self.request, "Producto creado correctamente.")
        return super().form_valid(form)

class ProductoUpdateView(UpdateView):
    model = Producto
    fields = ["nombre", "codigo_interno", "codigo_proveedor", "codigo_barras", "categoria", "marca", "unidad_base", "activo"]
    template_name = "productos/form.html"
    success_url = reverse_lazy("productos_list")

    def form_valid(self, form):
        messages.success(self.request, "Producto actualizado correctamente.")
        return super().form_valid(form)

class ProductoDeleteView(DeleteView):
    model = Producto
    template_name = "productos/confirm_delete.html"
    success_url = reverse_lazy("productos_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Producto eliminado correctamente.")
        return super().delete(request, *args, **kwargs)
