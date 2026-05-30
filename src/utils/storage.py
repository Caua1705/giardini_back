from src.core import config as settings


def build_receipt_url(comprovante_path: str | None) -> str | None:
    if not comprovante_path:
        return None

    if comprovante_path.startswith(("http://", "https://")):
        return comprovante_path

    base_url = settings.SUPABASE_STORAGE_BASE_URL.rstrip("/")
    path = comprovante_path.lstrip("/")

    return f"{base_url}/{path}"


def build_image_url(
    image_path: str | None,
    bucket: str,
) -> str | None:
    if not image_path:
        return None

    return f"{settings.SUPABASE_STORAGE_BASE_URL}/{bucket}/{image_path}"
