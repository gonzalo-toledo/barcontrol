"""
ia_helper.py
----------------------------------------
Módulo de soporte para "inteligencia semántica" del sistema.

Usa embeddings (representaciones vectoriales del texto) para comparar
descripciones de productos detectadas en facturas con los productos
ya registrados en la base de datos.
"""

import numpy as np
from sentence_transformers import SentenceTransformer
from productos.models import Producto
import re

def normalize_text(text: str) -> str:
    """
    Limpia y normaliza un texto para mejorar las coincidencias semánticas.
    Ej: 'Coca-Cola 1.5L' -> 'coca cola 1.5 l'
    """
    text = text.lower()
    text = re.sub(r'[^a-z0-9áéíóúñ\s]', ' ', text)  # elimina símbolos como '-', '.'
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class IAHelper:
    """
    Clase encargada de manejar el modelo de lenguaje y calcular similitudes entre descripciones de factura y productos registrados.

    Utiliza los embeddings ya guardados en BD (ProductoEmbedding) para acelerar las búsquedas.
    """

    def __init__(self):
        print("🧠 Inicializando IA Helper con embeddings precalculados...")
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        # Cargar productos activos con embeddings
        productos = (
            Producto.objects.filter(activo=True, embedding__isnull=False)
            .select_related("embedding")
        )

        self.productos = []
        self.embeddings = []

        for p in productos:
            try:
                vec = np.array(p.embedding.vector, dtype=float)
                self.productos.append(p)
                self.embeddings.append(vec)
            except Exception as ex:
                print(f"⚠️ Error leyendo embedding de {p.nombre}: {ex}")

        if self.embeddings:
            self.embeddings = np.vstack(self.embeddings)
        else:
            # En caso de que no haya embeddings cargados
            self.embeddings = np.empty((0, 384))

        print(f"✅ {len(self.productos)} embeddings cargados en memoria.")


    # -----------------------------------------------------------
    # CÁLCULO DE SIMILITUD SEMÁNTICA
    # -----------------------------------------------------------
    def find_best_product(self, description: str, threshold: float = 0.70):
        """
        Busca el producto más similar semánticamente a la descripción dada.
        Usa los embeddings precalculados (no recalcula cada vez).
        """

        if not description:
            return None

        if not self.embeddings.size:
            print("⚠️ No hay embeddings cargados en memoria para comparar.")
            return None

        desc = normalize_text(description)
        desc_emb = self.model.encode([desc])[0]

        # Calcular similitud por producto (coseno)
        sims = np.dot(self.embeddings, desc_emb) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(desc_emb)
        )

        best_idx = np.argmax(sims)
        best_score = sims[best_idx]

        if best_score >= threshold:
            prod = self.productos[best_idx]
            print(f"✅ Coincidencia encontrada: {prod.nombre} (similitud={best_score:.2f})")
            return prod, float(best_score)

        print(f"⚠️ Ninguna coincidencia relevante para '{description}' (mejor similitud={best_score:.2f})")
        return None

# -----------------------------------------------------------
# SINGLETON CON CARGA LAZY
# -----------------------------------------------------------
_ia_helper_instance = None


def get_ia_helper():
    """
    Devuelve la instancia global de IAHelper, inicializándola solo una vez.
    Evita problemas de carga de modelos durante el arranque de Django.
    """
    global _ia_helper_instance
    if _ia_helper_instance is None:
        from django.apps import apps

        if not apps.ready:
            # retrasa la creación hasta que Django esté totalmente inicializado
            apps.lazy_model_operation(lambda: get_ia_helper(), "productos", "Producto")
            return None

        _ia_helper_instance = IAHelper()

    return _ia_helper_instance
    
    #instancia global (singleton) para que el helper no inicialice en cada llamada a preview_invoice (en la view importo get_ia_helper y result = get_ia_helper.find_best_product(desc))
