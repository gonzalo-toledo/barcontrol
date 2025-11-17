"""
Servicio de chat conectado a OpenAI (nueva API 2025).
Usa el cliente moderno `OpenAI()` y el endpoint `responses.create`.
"""

from openai import OpenAI
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class ChatService:
    """
    Servicio central para comunicación con el modelo de OpenAI.
    """

    def __init__(self, model="gpt-4o-mini"):
        # Crea cliente oficial con API key segura desde settings
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model

    def ask(self, message: str) -> str:
        """
        Envía un mensaje al modelo y devuelve su respuesta textual.
        """
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Sos un asistente experto en gestión de facturas, productos y proveedores. "
                            "Respondé siempre en español y de forma clara y breve."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                temperature=0.4,
                max_output_tokens=400,
            )

            reply = response.output_text
            logger.info(f"[CHAT] {message[:40]}... → {reply[:40]}...")
            return reply

        except Exception as ex:
            logger.error(f"Error al consultar OpenAI: {ex}")
            return f"⚠️ Error al comunicar con OpenAI: {ex}"

# Instancia global reutilizable
chat_service = ChatService()
