from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Producto

class ProductoListView(LoginRequiredMixin, ListView):
    model = Producto
    template_name = "productos/list.html"
    context_object_name = "productos"

class ProductoCreateView(LoginRequiredMixin,CreateView):
    model = Producto
    fields = ["nombre", "codigo_interno", "codigo_proveedor", "codigo_barras", "categoria", "marca", "unidad_base", "activo"]
    template_name = "productos/form.html"
    
    def get_success_url(self):
        # si vino desde previiew_invoice -> volver a preview_invoice
        next_url = self.request.GET.get("next") or self.request.POST.get("next")
        if next_url == "preview_invoice":
            messages.success(self.request, "Producto creado correctamente.")
            return reverse_lazy("preview_invoice")
        
        #comportamiento normal
        messages.success(self.request, "Producto creado correctamente.")
        return reverse_lazy("productos_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context
    
    # def form_valid(self, form):
    #     messages.success(self.request, "Producto creado correctamente.")
    #     return super().form_valid(form)

class ProductoUpdateView(LoginRequiredMixin, UpdateView):
    model = Producto
    fields = ["nombre", "codigo_interno", "codigo_proveedor", "codigo_barras", "categoria", "marca", "unidad_base", "activo"]
    template_name = "productos/form.html"
    success_url = reverse_lazy("productos_list")

    def form_valid(self, form):
        messages.success(self.request, "Producto actualizado correctamente.")
        return super().form_valid(form)

class ProductoDeleteView(LoginRequiredMixin, DeleteView):
    model = Producto
    template_name = "productos/confirm_delete.html"
    success_url = reverse_lazy("productos_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Producto eliminado correctamente.")
        return super().delete(request, *args, **kwargs)
