from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from invoices.models import Proveedor

class ProveedorListView(LoginRequiredMixin, ListView):
    model = Proveedor
    template_name = "proveedores/list.html"
    context_object_name = "proveedores"

class ProveedorCreateView(LoginRequiredMixin, CreateView):
    model = Proveedor
    fields = ["nombre", "id_fiscal", "condicion_iva", "direccion", "email", "telefono"]
    template_name = "proveedores/form.html"
    success_url = reverse_lazy("proveedores_list")

    def form_valid(self, form):
        messages.success(self.request, "Proveedor creado correctamente.")
        return super().form_valid(form)

class ProveedorUpdateView(LoginRequiredMixin, UpdateView):
    model = Proveedor
    fields = ["nombre", "id_fiscal", "condicion_iva", "direccion", "email", "telefono"]
    template_name = "proveedores/form.html"
    success_url = reverse_lazy("proveedores_list")

    def form_valid(self, form):
        messages.success(self.request, "Proveedor actualizado correctamente.")
        return super().form_valid(form)

class ProveedorDeleteView(LoginRequiredMixin, DeleteView):
    model = Proveedor
    template_name = "proveedores/confirm_delete.html"
    success_url = reverse_lazy("proveedores_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Proveedor eliminado correctamente.")
        return super().delete(request, *args, **kwargs)
