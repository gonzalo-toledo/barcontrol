"""
Servicio para generar y mantener embeddings de productos.
Usa el mismo modelo de IA que el helper principal (MiniLM).
"""

import numpy as np
from sentence_transformers import SentenceTransformer
from productos.models import Producto, ProductoEmbedding
from invoices.services.ia_helper import normalize_text  # reutilizamos la función de normalización


class ProductEmbeddingService:
    def __init__(self):
        """
        Carga el modelo de embeddings.
        Solo se carga una vez (evita recargar en cada producto).
        """
        print("🧠 Cargando modelo de embeddings para productos...")
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def generate_embedding(self, text: str):
        """
        Convierte una descripción de producto en vector numérico (embedding).
        """
        clean_text = normalize_text(text)
        return self.model.encode([clean_text])[0]  # devuelve np.array

    def ensure_embedding(self, producto: Producto):
        """
        Crea o actualiza el embedding para un producto.
        """
        text = f"{producto.nombre} {producto.marca or ''} {producto.categoria or ''}"
        vec = self.generate_embedding(text)

        emb, created = ProductoEmbedding.objects.get_or_create(producto=producto)
        emb.set_vector(vec)
        emb.save()

        status = "creado" if created else "actualizado"
        print(f"✅ Embedding {status} para '{producto.nombre}'")

    def bulk_generate_all(self):
        """
        Genera embeddings para todos los productos activos sin embedding.
        Ideal para comando 'generate_product_embeddings'.
        """
        productos = Producto.objects.filter(activo=True)
        for p in productos:
            self.ensure_embedding(p)
        print(f"🧩 Se actualizaron {productos.count()} embeddings de productos.")


# Instancia global (singleton)
embedding_service = ProductEmbeddingService()
