from django.core.management.base import BaseCommand
from productos.services.embedding_service import embedding_service

class Command(BaseCommand):
    help = "Genera o actualiza embeddings para todos los productos activos."

    def handle(self, *args, **options):
        embedding_service.bulk_generate_all()
        self.stdout.write(self.style.SUCCESS("Embeddings generados exitosamente."))
