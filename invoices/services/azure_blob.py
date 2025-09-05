import uuid
from datetime import datetime, timedelta

from django.conf import settings
from azure.storage.blob import (
    BlobServiceClient, ContentSettings,
    generate_blob_sas, BlobSasPermissions, BlobClient
)

import re
import unicodedata

def normalize_filename(filename: str) -> str:
    """
    Normaliza el nombre de archivo para usarlo en Azure Blob:
    - convierte a minúsculas
    - elimina tildes y caracteres especiales
    - reemplaza espacios por guiones bajos
    - permite solo letras, números, guiones, guiones bajos y punto
    - conserva la extensión original
    - agrega un UUID corto para evitar colisiones
    """
    # separar extensión
    parts = filename.rsplit('.', 1)
    name = parts[0]
    ext = parts[1].lower() if len(parts) == 2 else ""

    # quitar tildes y normalizar
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")

    # minúsculas
    name = name.lower()

    # reemplazar espacios por guiones bajos
    name = name.replace(" ", "_")

    # solo caracteres permitidos
    name = re.sub(r"[^a-z0-9._-]", "_", name)

    # evitar que quede vacío
    if not name:
        name = "file"

    # agregar uuid corto para unicidad
    uid = uuid.uuid4().hex[:8]
    safe_name = f"{name}_{uid}"
    if ext:
        safe_name += f".{ext}"

    return safe_name

def _svc() -> BlobServiceClient:
    """
    Crea un BlobServiceClient usando account_url + account_key.
    """
    account = settings.AZURE_STORAGE_ACCOUNT
    key = settings.AZURE_STORAGE_KEY
    if not account or not key:
        raise RuntimeError("Faltan AZURE_STORAGE_ACCOUNT o AZURE_STORAGE_KEY")
    account_url = f"https://{account}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=key)

def ensure_container(name: str):
    svc = _svc()
    try:
        svc.create_container(name)
    except Exception:
        # ya existe o no tenemos permiso para crear (ignorar en MVP)
        pass

def upload_bytes(container: str, content: bytes, filename: str, content_type: str) -> str:
    ensure_container(container)
    svc = _svc()
    blob_name = f"{uuid.uuid4()}-{filename}"
    blob = svc.get_blob_client(container=container, blob=blob_name)
    blob.upload_blob(
        content,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type or "application/octet-stream")
    )
    return blob.url  # sin SAS

def make_sas_url(container: str, blob_name: str, minutes: int = 15) -> str | None:
    account = settings.AZURE_STORAGE_ACCOUNT
    key = settings.AZURE_STORAGE_KEY
    if not account or not key:
        # sin credenciales no se puede firmar
        return None

    expiry = datetime.utcnow() + timedelta(minutes=minutes)

    sas = generate_blob_sas(
        account_name=account,
        container_name=container,
        blob_name=blob_name,
        permission=BlobSasPermissions(read=True),
        expiry=expiry,
        # 👇 **ESTO ES CLAVE**: pasar la access key explícitamente
        account_key=key,
    )
    return f"https://{account}.blob.core.windows.net/{container}/{blob_name}?{sas}"

def to_blob_name_from_url(url: str) -> str:
    return url.split('/')[-1].split('?')[0]

def download_bytes(container: str, blob_name: str) -> bytes:
    """
    Descarga el blob (útil como fallback).
    """
    account = settings.AZURE_STORAGE_ACCOUNT
    key = settings.AZURE_STORAGE_KEY
    account_url = f"https://{account}.blob.core.windows.net"
    bc = BlobClient(account_url=account_url, container_name=container, blob_name=blob_name, credential=key)
    return bc.download_blob().readall()
