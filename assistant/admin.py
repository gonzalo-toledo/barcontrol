from django.contrib import admin
from django.utils.html import format_html
from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("user_display", "short_message", "role", "created_at", "colored_role")
    list_filter = ("role", "created_at")
    search_fields = ("message", "user__username")
    ordering = ("-created_at",)
    list_per_page = 25

    def short_message(self, obj):
        text = obj.message
        return (text[:70] + "...") if len(text) > 70 else text
    short_message.short_description = "Mensaje"

    def user_display(self, obj):
        if obj.user:
            return obj.user.username
        return "Anónimo"
    user_display.short_description = "Usuario"

    def colored_role(self, obj):
        """Muestra el rol con color (IA = azul, Usuario = verde)."""
        color = "#0d6efd" if obj.role == "assistant" else "#198754"
        label = "🤖 Asistente" if obj.role == "assistant" else "🧍 Usuario"
        return format_html(f"<b style='color:{color}'>{label}</b>")
    colored_role.short_description = "Rol"
