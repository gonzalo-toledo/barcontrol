📘 README — Sistema de Gestión + IA (MiniLM)
🚀 Configuración inicial del entorno

Crear entorno virtual e instalar dependencias:

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt


Realizar las migraciones iniciales:

python manage.py makemigrations
python manage.py migrate


Crear superusuario:

python manage.py createsuperuser


------------------------------------------------------------------------------------------


🧾 Cargar datos básicos (fixtures)

Los datos iniciales del sistema (Tipos de Comprobante, Condiciones de IVA y de Pago)
se cargan desde los JSON que están en la carpeta fixtures.

python manage.py loaddata fixtures/tipo_comprobante.json
python manage.py loaddata fixtures/condicion_iva.json
python manage.py loaddata fixtures/condicion_pago.json


✅ Esto crea registros base compatibles con AFIP/ARCA para uso general.


------------------------------------------------------------------------------------------


🧠 Embeddings de Productos (IA Semántica)
1️⃣ ¿Qué son los embeddings?

Los embeddings son vectores numéricos que representan el significado de un texto (por ejemplo, el nombre de un producto).
Esto permite que la IA reconozca similitudes aunque las palabras no coincidan exactamente,
por ejemplo:

“Coca-Cola 1.5L” ≈ “Coca Cola 1500 ml” → similitud alta.

El modelo usado es MiniLM-L6-v2, rápido y gratuito.

2️⃣ Creación automática de embeddings

Cada vez que se crea o edita un producto, se genera su embedding automáticamente.

Esto lo hace el signal:

@receiver(post_save, sender=Producto)
def update_producto_embedding(sender, instance, **kwargs):
    embedding_service.ensure_embedding(instance)


Verás en consola:

✅ Embedding creado para 'Coca Cola'

3️⃣ Comando de mantenimiento (regenerar embeddings)

Podés regenerar embeddings de todos los productos activos (por ejemplo, si cambiaste el modelo IA):

python manage.py generate_producto_embeddings


Verás algo así:

🧠 Cargando modelo de embeddings para productos...
✅ Embedding creado para 'Aceite Natura 1L'
✅ Embedding actualizado para 'Yerba Mate Playadito 1kg'
🧩 Se actualizaron 25 embeddings de productos.


------------------------------------------------------------------------------------------


⚙️ Ajuste de sensibilidad de MiniLM

Cuando se compara una descripción de factura con los productos existentes,
la IA calcula una similitud entre 0 y 1.

1.0 = coincidencia perfecta

0.0 = sin relación

En el código de búsqueda (por ejemplo, ia_helper.py) hay un umbral de similitud:

THRESHOLD = 0.80  # sensibilidad actual


Podés ajustar este valor:

Umbral	Resultado	Recomendado para
0.70	Más tolerante (acepta más coincidencias, aunque algunas incorrectas)	OCRs confusos o productos mal escritos
0.80	Equilibrado (por defecto)	Facturas estándar
0.90	Más estricto (solo coincidencias casi exactas)	Productos con nombres bien definidos

Después de modificarlo, no hace falta regenerar embeddings.
Solo reiniciá el servidor de Django.


------------------------------------------------------------------------------------------


🧩 Cómo probar la IA de reconocimiento de productos

Subí una factura simulada (modo Azure Simulation activo).

Si el sistema detecta productos similares, los asigna automáticamente.

Si no los encuentra, verás un aviso en la consola:

⚠️ Ninguna coincidencia relevante para 'Coca-Cola 1.5L' (mejor similitud=0.71)


👉 En ese caso, podés ajustar el umbral de similitud o mejorar el nombre en la base de productos.


------------------------------------------------------------------------------------------


🧹 Limpieza y mantenimiento general

Si querés reiniciar el sistema desde cero (sin borrar fixtures):

rm db.sqlite3
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
python manage.py makemigrations
python manage.py migrate
python manage.py loaddata fixtures/tipo_comprobante.json
python manage.py loaddata fixtures/condicion_iva.json
python manage.py loaddata fixtures/condicion_pago.json
python manage.py createsuperuser


------------------------------------------------------------------------------------------


🧭 Flujo general del sistema

Subir factura → Azure (o modo simulado) extrae los datos.

Vista previa → IA intenta reconocer productos y proveedores.

Confirmar factura → Se guarda en BD con sus ítems.

Consulta IA futura (chat) → Usa embeddings de productos y facturas.