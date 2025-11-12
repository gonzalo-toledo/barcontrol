from django.views import View
from django.http import JsonResponse
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import AnonymousUser
import json

from assistant.services.chat_service import chat_service
from assistant.models import ChatMessage


@method_decorator(csrf_exempt, name="dispatch")
class ChatAPIView(View):
    """
    Endpoint RESTful del chat IA.
    Guarda el historial de conversación y responde con JSON.
    """

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            text = data.get("message", "").strip()

            if not text:
                messages.warning(request, "Intento de enviar mensaje vacío.")
                return JsonResponse({"error": "Mensaje vacío."}, status=400)

            # Usuario logueado o anónimo
            user = None if isinstance(request.user, AnonymousUser) else request.user

            # Guardamos mensaje del usuario
            ChatMessage.objects.create(user=user, role="user", message=text)

            # Procesamos respuesta con OpenAI
            reply = chat_service.ask(text)

            # Guardamos respuesta del asistente
            ChatMessage.objects.create(user=user, role="assistant", message=reply)

            messages.success(request, "Respuesta de IA registrada correctamente.")
            return JsonResponse({"reply": reply})

        except Exception as ex:
            messages.error(request, f"Error en ChatAPIView: {ex}")
            return JsonResponse({"error": str(ex)}, status=500)

    def get(self, request, *args, **kwargs):
        """
        Devuelve los últimos mensajes del historial (para precargar el chat).
        """
        user = None if isinstance(request.user, AnonymousUser) else request.user
        qs = ChatMessage.objects.filter(user=user).order_by("-created_at")[:20]
        data = [
            {"role": m.role, "message": m.message, "created_at": m.created_at.isoformat()}
            for m in reversed(qs)
        ]
        return JsonResponse({"messages": data})
