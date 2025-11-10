"""
ia_helper.py
----------------------------------------
Módulo de soporte para "inteligencia semántica" del sistema.

Usa embeddings (representaciones vectoriales del texto) para comparar
descripciones de productos detectadas en facturas con los productos
ya registrados en la base de datos.
"""

from typing import Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from productos.models import Producto


class IAHelper:
    """
    Clase encargada de manejar el modelo de lenguaje y calcular similitudes
    entre textos (por ejemplo, entre una descripción de factura y un producto).
    """

    def __init__(self):
        # Carga el modelo pre-entrenado (MiniLM)
        # Este modelo transforma texto en vectores de 384 dimensiones aprox.
        print("🧠 Cargando modelo de embeddings MiniLM...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    # -----------------------------------------------------------
    # CONVERSIÓN DE TEXTO A VECTOR
    # -----------------------------------------------------------
    def get_embedding(self, text: str) -> np.ndarray:
        """
        Convierte una cadena de texto en un vector numérico (embedding).
        Si el texto está vacío, devuelve un vector de ceros.
        """
        if not text:
            return np.zeros((1, 384))
        embedding = self.model.encode([text], normalize_embeddings=True)
        return embedding

    # -----------------------------------------------------------
    # CÁLCULO DE SIMILITUD ENTRE DOS TEXTOS
    # -----------------------------------------------------------
    def similarity(self, text1: str, text2: str) -> float:
        """
        Calcula la similitud (coseno) entre dos textos.
        Devuelve un valor entre 0 y 1:
          - 1 significa idéntico
          - 0 significa sin relación
        """
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        sim = cosine_similarity(emb1, emb2)[0][0]
        return float(sim)

    # -----------------------------------------------------------
    # IDENTIFICACIÓN DE PRODUCTO EXISTENTE
    # -----------------------------------------------------------
    def find_best_product(self, description: str, threshold: float = 0.75) -> Optional[Tuple[Producto, float]]:
        """
        Busca el producto más similar según la descripción dada.
        Retorna (producto, similitud) si supera el umbral, o None si no hay coincidencias fuertes.
        """

        if not description:
            return None

        # Embedding del texto a analizar (ej. "Aceite Natura 1 litro")
        desc_emb = self.get_embedding(description)

        best_match = None
        best_score = 0.0

        # Recorre todos los productos activos en la base
        for prod in Producto.objects.filter(activo=True):
            prod_text = f"{prod.nombre} {prod.marca or ''} {prod.categoria or ''}".strip()
            prod_emb = self.get_embedding(prod_text)
            score = cosine_similarity(desc_emb, prod_emb)[0][0]

            if score > best_score:
                best_score = score
                best_match = prod

        if best_match and best_score >= threshold:
            print(f"✅ Coincidencia encontrada: {best_match.nombre} (similitud={best_score:.2f})")
            return best_match, best_score

        print(f"⚠️ Ninguna coincidencia relevante para '{description}' (mejor similitud={best_score:.2f})")
        return None
