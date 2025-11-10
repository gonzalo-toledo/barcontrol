from django.db import models
import numpy as np
import json


# Create your models here.
class Producto(models.Model):
    nombre = models.CharField(max_length=255)
    codigo_interno = models.CharField(max_length=64, null=True, blank=True)   # tu SKU interno
    codigo_proveedor = models.CharField(max_length=64, null=True, blank=True) # código que viene en la factura
    codigo_barras = models.CharField(max_length=64, null=True, blank=True)
    categoria = models.CharField(max_length=128, null=True, blank=True)
    marca = models.CharField(max_length=128, null=True, blank=True)
    unidad_base = models.CharField(max_length=20, null=True, blank=True)      # ej: un, kg, lt
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        indexes = [
            models.Index(fields=["codigo_interno"]),
            models.Index(fields=["codigo_proveedor"]),
            models.Index(fields=["codigo_barras"]),
            models.Index(fields=["nombre"]),
        ]
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
    

# --- PRODUCTO EMBEDDING ---
class ProductoEmbedding(models.Model):
    """
    Guarda el embedding (vector numérico) asociado a un producto.
    Permite busqueda semántica sin recalcular embeddings cada vez.
    """
    producto = models.OneToOneField(Producto, on_delete=models.CASCADE, related_name="embedding")
    vector = models.JSONField(null=True, blank=True) #guardamos como lista de floats
    modelo = models.CharField(max_length=100, default="MiniLM-L6-v2")
    actualizado = models.DateTimeField(auto_now=True)
    
    def set_vector(self, np_array):
        """
        convierte el numpy array a lista para guardar en JSONField
        """
        self.vector =np_array.tolist()
        
    def get_vector(self):
        """
        Devuelve el vector como numpy array
        """
        return np.array(self.vector, dtype=float)
        
    def __str__(self):
        return f"Embedding de {self.producto.nombre}"
    
    
# --- SEÑAL POST SAVE ---
# (se define DESPUÉS de los modelos para evitar import circular)
from django.db.models.signals import post_save 
from django.dispatch import receiver
from productos.services.embedding_service import embedding_service

@receiver(post_save, sender=Producto)
def update_producto_embedding(sender, instance, **kwargs):
    """
    Actualiza automáticamente el embedding cada vez que se crea o edita un producto.
    """
    try:
        embedding_service.ensure_embedding(instance)
    except Exception as ex:
        print(f"⚠️ No se pudo generar el embedding para {instance.nombre}: {ex}")